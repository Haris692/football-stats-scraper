"""Captures d'écran d'une page web, rangées dans un dossier.

Outil autonome, sans rapport avec la collecte de statistiques : il ouvre les URL
qu'on lui donne et enregistre une image de chacune. Il s'appuie sur `browser.py`
— un vrai Chrome piloté en CDP, avec un profil dédié — donc il passe là où une
requête directe se ferait refouler, et il ne touche pas aux onglets ouverts.

Il **ne suit aucun lien** : il capture exactement les adresses demandées, rien
de plus. C'est un appareil photo, pas un robot d'exploration.

    python shoot.py https://example.com
    python shoot.py https://example.com --full --out captures/lundi
    python shoot.py https://a.com https://b.com --size 1440x900 --size 390x844
    python shoot.py https://example.com --element "main" --scale 2
    python shoot.py https://example.com --hide "#cookie-banner" --dark

Les images vont dans `captures/` par défaut, nommées
`<slug de l'URL>-<largeur>x<hauteur>-<horodatage>.png`.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from browser import CdpBrowser

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "captures"


def parse_size(value: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d{2,5})\s*[x×]\s*(\d{2,5})\s*", value)
    if not m:
        raise argparse.ArgumentTypeError(
            f"taille attendue au format LARGEURxHAUTEUR (ex. 1440x900), reçu {value!r}")
    return int(m.group(1)), int(m.group(2))


def slug(url: str) -> str:
    """Nom de fichier lisible tiré de l'URL, sans le protocole ni le www."""
    s = re.sub(r"^https?://(www\.)?", "", url.strip())
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return (s[:60] or "page")


def set_metrics(session, width: int, height: int, scale: float) -> None:
    """Impose taille de rendu et densité de pixels.

    En CDP on est attaché à une *vraie* fenêtre Chrome : sa taille et sa densité
    sont celles de l'écran de l'utilisateur, pas celles qu'on demande.
    `Emulation.setDeviceMetricsOverride` force les deux côté moteur — c'est ce
    qui rend une capture reproductible d'une machine à l'autre.

    ⚠️ À réappliquer **après** la navigation : `page.goto` remet les métriques
    de la fenêtre. Sans ça, sur un écran Windows à 150 %, un 1440x900 demandé
    ressort en 2160x1350 — la mise en page est bonne, la densité non.
    """
    session.send("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height,
        "deviceScaleFactor": scale, "mobile": height > width,
    })


def capture(session, page, args, path: Path) -> bool:
    """Déclenche, et écrit le fichier. Renvoie False si l'élément visé manque.

    ⚠️ On passe par CDP `Page.captureScreenshot` et non par `page.screenshot()`
    de Playwright : ce dernier ignore la densité imposée par l'émulation. Il ne
    sait produire que du 1x (`scale="css"`) ou la densité réelle de l'écran
    (`scale="device"`) — sur un écran à 150 %, un `--scale 2` sortait en 1,5x.
    En CDP, la consigne est respectée au pixel près.
    """
    params = {"format": args.format}
    if args.format == "jpeg":
        params["quality"] = args.quality

    if args.element:
        box = page.locator(args.element).first.bounding_box()
        if not box:
            print(f"  élément {args.element!r} introuvable ou invisible",
                  file=sys.stderr)
            return False
        # `clip` est en pixels CSS ; la densité vient de l'émulation, d'où
        # `scale: 1` — sinon les deux se multiplieraient.
        params["clip"] = {**{k: box[k] for k in ("x", "y", "width", "height")},
                          "scale": 1}
        params["captureBeyondViewport"] = True
    elif args.full:
        params["captureBeyondViewport"] = True

    data = session.send("Page.captureScreenshot", params)["data"]
    path.write_bytes(base64.b64decode(data))
    return True


def prepare(page, args) -> None:
    """Attentes et nettoyages avant le déclenchement."""
    if args.wait:
        page.wait_for_selector(args.wait, timeout=args.timeout * 1000)
    else:
        # Sans sélecteur, on laisse au moins le réseau se calmer : sinon on
        # photographie une page à moitié peinte.
        try:
            page.wait_for_load_state("networkidle", timeout=args.timeout * 1000)
        except Exception:
            pass
    for selector in args.hide:
        # Les bandeaux de cookies et autres surcouches gâchent une capture. On
        # les retire du DOM plutôt que de cliquer dessus : cliquer, ce serait
        # accepter quelque chose à la place de l'utilisateur.
        page.evaluate(
            """sel => document.querySelectorAll(sel).forEach(n => n.remove())""",
            selector)
    if args.delay:
        time.sleep(args.delay)


def shoot(browser: CdpBrowser, url: str, args) -> list[Path]:
    page = browser.page()
    session = page.context.new_cdp_session(page)
    written = []
    for width, height in args.size:
        # Avant la navigation : la page doit se *dessiner* à cette largeur.
        set_metrics(session, width, height, args.scale)
        page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        prepare(page, args)
        # Après : la navigation a rendu la main à la fenêtre réelle.
        set_metrics(session, width, height, args.scale)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = args.name or f"{slug(url)}-{width}x{height}-{stamp}"
        path = Path(args.out) / f"{name}.{args.format}"
        path.parent.mkdir(parents=True, exist_ok=True)

        if not capture(session, page, args, path):
            continue
        size_ko = path.stat().st_size // 1024
        print(f"  {path.name}  ({width}x{height} ×{args.scale:g}, {size_ko} Ko)")
        written.append(path)

    # On rend la fenêtre à son état normal, sinon l'onglet reste bridé.
    session.send("Emulation.clearDeviceMetricsOverride")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture d'écran d'une ou plusieurs pages web.")
    parser.add_argument("urls", nargs="+", help="adresses à photographier")
    parser.add_argument("--out", default=str(OUTPUT),
                        help="dossier de sortie (défaut : captures/)")
    parser.add_argument("--full", action="store_true",
                        help="page entière et non la seule partie visible")
    parser.add_argument("--element", metavar="SELECTEUR",
                        help="ne capturer qu'un élément (sélecteur CSS)")
    parser.add_argument("--size", type=parse_size, action="append", metavar="LxH",
                        help="taille de rendu, répétable (défaut : 1440x900)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="densité de pixels ; 2 pour un rendu retina")
    parser.add_argument("--wait", metavar="SELECTEUR",
                        help="attendre ce sélecteur avant de déclencher")
    parser.add_argument("--delay", type=float, default=0,
                        help="secondes d'attente supplémentaires")
    parser.add_argument("--hide", action="append", default=[], metavar="SELECTEUR",
                        help="retirer des éléments avant la capture (répétable)")
    parser.add_argument("--dark", action="store_true",
                        help="forcer le thème sombre de la page")
    parser.add_argument("--format", choices=["png", "jpeg"], default="png")
    parser.add_argument("--quality", type=int, default=85,
                        help="qualité JPEG (1-100)")
    parser.add_argument("--name", help="nom de fichier imposé (sans extension)")
    parser.add_argument("--timeout", type=int, default=45,
                        help="délai maximum par page, en secondes")
    parser.add_argument("--keep-open", action="store_true",
                        help="laisser Chrome ouvert à la fin")
    args = parser.parse_args()

    args.size = args.size or [(1440, 900)]
    if args.name and (len(args.urls) > 1 or len(args.size) > 1):
        parser.error("--name ne convient qu'à une seule URL et une seule taille : "
                     "sinon les images s'écraseraient entre elles")

    out = Path(args.out)
    print(f"→ {len(args.urls)} page(s) × {len(args.size)} taille(s) vers {out}")

    written = []
    with CdpBrowser(keep_open=args.keep_open) as browser:
        if args.dark:
            browser.page().emulate_media(color_scheme="dark")
        for url in args.urls:
            if not re.match(r"^https?://", url):
                url = "https://" + url
            print(url)
            try:
                written += shoot(browser, url, args)
            except Exception as exc:
                # Une page qui échoue ne doit pas emporter les suivantes.
                print(f"  échec : {str(exc).splitlines()[0]}", file=sys.stderr)

    print(f"\n{len(written)} image(s) dans {out}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
