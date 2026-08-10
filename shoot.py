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
    python shoot.py https://monsite.fr --login   # page derrière une connexion

Les images vont dans `captures/` par défaut, nommées
`<slug de l'URL>-<largeur>x<hauteur>-<horodatage>.png`.

Le nettoyage est automatique : bandeaux de consentement, infolettres, demandes
de notification, encarts « ouvrir dans l'appli », publicités flottantes, voiles
sombres et messageries de support sont retirés, et l'outil dit ce qu'il a
retiré. Le contenu et la navigation du site sont protégés. `--brut` pour ne rien
nettoyer.

Pour une page qui demande d'être connecté : `--login` ouvre Chrome, attend que
tu te connectes à la main, puis photographie. Le profil dédié étant persistant,
la session vaut pour toutes les captures suivantes.

⛔ Piloter le **profil Chrome habituel** est impossible depuis Chrome 136 :
`--remote-debugging-port` y est ignoré, pour qu'un programme local ne puisse pas
lire les cookies du navigateur. Le drapeau part, le port ne s'ouvre jamais.
`--user-data-dir` vers une *copie* de profil reste possible, mais `--login` est
plus simple.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from browser import (DEBUG_PORT, CdpBrowser, chrome_is_running,
                     chrome_user_data_dir, debug_port_open)

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


# Nettoyage automatique de ce qui se pose entre le lecteur et la page.
#
# Principe de prudence : on **retire du DOM**, on ne clique jamais. Cliquer
# « Accepter » reviendrait à consentir à la place de l'utilisateur, cliquer
# « Refuser » serait aussi un choix qu'on n'a pas à faire. Supprimer l'élément
# ne consent à rien — aucun cookie optionnel n'est déposé.
#
# Deuxième principe : ne jamais toucher au contenu ni à la navigation du site.
# Un en-tête collant fait partie de la page ; une fenêtre qui la recouvre, non.
# Chaque suppression est rendue à l'appelant avec son motif, pour être vérifiable.
DECLUTTER = r"""() => {
    const removed = [];
    const vw = innerWidth, vh = innerHeight;
    const nom = n => n.tagName.toLowerCase() + (n.id ? "#" + n.id
                 : (n.classList.length ? "." + n.classList[0] : ""));
    const kill = (n, motif) => {
        if (!n || !n.isConnected || n === document.body) return;
        removed.push({ quoi: nom(n), motif });
        n.remove();
    };

    // Ce qu'on ne supprime jamais : le contenu et la navigation du site.
    const CONTENU = "main, article, [role=main], #root, #app, #__next";
    const protege = n =>
        n.matches("header, nav, [role=banner], [role=navigation]") ||
        n.querySelector(CONTENU) !== null ||
        n.querySelector("nav") !== null;

    // Un en-tête de site : collé en haut, pleine largeur, dense en liens.
    // Réservé à l'heuristique — les sélecteurs connus, eux, sont sûrs.
    //
    // ⚠️ C'est le garde-fou qui manquait : `div.fh-wrapper` du Figaro a été
    // pris pour une infolettre parce que son en-tête contient « S'abonner ».
    // Supprimer l'en-tête d'un site, c'est le rendre méconnaissable.
    const estEnTete = n => {
        const r = n.getBoundingClientRect();
        return r.top <= 4 && r.width >= vw * 0.9
               && n.querySelectorAll("a").length >= 6;
    };

    // --- 1. plateformes et widgets connus, par leur conteneur ---------------
    const CONNUS = {
      "consentement": [
        "#onetrust-consent-sdk", "#onetrust-banner-sdk", ".onetrust-pc-dark-filter",
        "#CybotCookiebotDialog", "#CybotCookiebotDialogBodyUnderlay",
        "#didomi-host", "#didomi-popup", ".didomi-popup-backdrop",
        "#usercentrics-root", "#uc-banner-container",
        ".qc-cmp2-container", ".qc-cmp-cleanslate", "#qc-cmp2-main",
        "#axeptio_overlay", "#axeptio_main_button",
        ".osano-cm-window", ".osano-cm-dialog",
        "#cmpbox", "#cmpbox2", "#cmpwrapper",
        "div[id^='sp_message_container']",
        ".cc-window", ".cookie-notice-container", "#cookie-law-info-bar",
        "#cmplz-cookiebanner-container", ".cmplz-cookiebanner",
        "#tarteaucitronRoot", "#tarteaucitronAlertBig",
        "#hs-eu-cookie-confirmation", "#gdpr-consent-tool-wrapper",
        "[id*='cookie-consent']", "[class*='cookie-consent']",
        "[aria-label*='cookie' i][role='dialog']",
      ],
      "messagerie": [
        "#intercom-container", ".intercom-lightweight-app", "#intercom-frame",
        "#crisp-chatbox", "#drift-widget-container", "#drift-frame-controller",
        ".zEWidget-launcher", "#launcher[data-testid]", "#tawkchat-container",
        "#hubspot-messages-iframe-container", "#tidio-chat", "#chat-widget-container",
        "#live-chat-loader-app", ".fb_dialog",
      ],
      "application": [
        ".smartbanner", "#smartbanner", ".branch-banner-iframe", "#branch-banner",
        ".app-download-banner", "[class*='open-in-app']",
      ],
      "publicité flottante": [
        "[id^='google_ads_iframe'][style*='fixed']", ".ad-slot--sticky",
        "[class*='sticky-ad']", "[class*='ad-sticky']", "[id*='taboola-below']",
      ],
    };
    for (const [motif, liste] of Object.entries(CONNUS)) {
      for (const sel of liste) {
        let nodes = [];
        try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
        nodes.forEach(n => { if (!protege(n)) kill(n, motif); });
      }
    }

    // --- 2. heuristique, pour tout ce que la liste ne connaît pas -----------
    // Trois conditions cumulées : posé par-dessus la page, une surface qui
    // compte, et un vocabulaire d'interruption. Les trois ensemble — sinon on
    // supprimerait un en-tête collant ou une vraie fenêtre de l'application.
    const FAMILLES = [
      ["consentement", /(cookie|consent|rgpd|gdpr|vie priv|privacy|tra(c|ç)age|tracker|donn(e|é)es personnelles)/i],
      // « abonnez » et « subscribe » seuls sont trop faibles : tous les
      // en-têtes de presse portent un bouton d'abonnement. On exige un mot qui
      // ne se trouve que dans une vraie sollicitation.
      ["infolettre",   /(newsletter|infolettre|inscrivez-vous|ne ratez (aucune|rien)|restez inform(é|e))/i],
      ["notification", /(notification|autoriser les alertes|recevoir les alertes|allow notifications)/i],
      ["application",  /(t(é|e)l(é|e)charge[rz] l'appli|ouvrir dans l'appli|open in app|get the app)/i],
      ["publicité",    /^(publicit(é|e)|advertisement|sponsoris)/i],
    ];
    for (const n of document.querySelectorAll("body *")) {
      if (!n.isConnected || protege(n) || estEnTete(n)) continue;
      const st = getComputedStyle(n);
      if (st.position !== "fixed" && st.position !== "sticky") continue;
      if (parseInt(st.zIndex || "0", 10) < 100) continue;
      const r = n.getBoundingClientRect();
      if (r.width * r.height < vw * vh * 0.03) continue;
      const txt = (n.innerText || "").trim().slice(0, 900);
      const trouve = FAMILLES.find(([, re]) => re.test(txt));
      if (trouve) kill(n, trouve[0]);
    }

    // --- 3. les voiles sombres laissés par une fenêtre disparue ------------
    for (const n of document.querySelectorAll("body *")) {
      if (!n.isConnected || protege(n)) continue;
      const st = getComputedStyle(n);
      if (st.position !== "fixed") continue;
      const r = n.getBoundingClientRect();
      if (r.width < vw * 0.9 || r.height < vh * 0.9) continue;
      if ((n.innerText || "").trim().length > 8) continue;   // il a du contenu
      const fond = st.backgroundColor || "";
      const alpha = (fond.match(/rgba?\([^)]*?([\d.]+)\)/) || [])[1];
      const opaque = fond.startsWith("rgba") ? parseFloat(alpha) > 0.05
                   : fond !== "rgba(0, 0, 0, 0)" && fond !== "transparent";
      if (opaque || parseFloat(st.backdropFilter && st.backdropFilter !== "none" ? 1 : 0))
        kill(n, "voile");
    }

    // --- 4. rendre le défilement -------------------------------------------
    // Ces fenêtres bloquent souvent le document. Une fois parties, la page doit
    // redevenir normale, sinon `--full` ne prendrait que le premier écran.
    for (const el of [document.documentElement, document.body]) {
      el.style.overflow = "";
      el.style.position = "";
      el.style.height = "";
      el.classList.remove("no-scroll", "noscroll", "modal-open", "no_scroll",
                          "overflow-hidden", "cmplz-blocked", "fixed");
    }
    return removed;
}"""


# Retirer par le TEXTE plutôt que par le sélecteur : « enlève le truc où c'est
# écrit Offre spéciale » se formule sans ouvrir les outils de développement.
HIDE_BY_TEXT = r"""(needle) => {
    const n = needle.toLowerCase();
    const hits = [];
    for (const el of document.querySelectorAll("body *")) {
        const txt = (el.innerText || "").toLowerCase();
        if (!txt.includes(n)) continue;
        // On ne garde que le plus profond : sinon <body> correspondrait aussi.
        if ([...el.children].some(c => (c.innerText || "").toLowerCase().includes(n)))
            continue;
        hits.push(el);
    }
    const removed = [];
    for (let el of hits) {
        // On remonte tant que le parent n'apporte presque rien d'autre : c'est
        // ainsi qu'on attrape le bandeau entier et pas seulement sa phrase,
        // sans jamais avaler la page.
        let box = el;
        for (let i = 0; i < 6 && box.parentElement; i++) {
            const p = box.parentElement;
            if (p === document.body) break;
            const own = (box.innerText || "").length;
            const up = (p.innerText || "").length;
            if (up > own * 1.6 + 40) break;
            box = p;
        }
        removed.push(box.tagName.toLowerCase() + (box.id ? "#" + box.id : ""));
        box.remove();
    }
    return removed;
}"""

# Ce qui flotte au-dessus de la page, avec de quoi le désigner ensuite.
LIST_OVERLAYS = r"""() => {
    const out = [];
    const vw = innerWidth, vh = innerHeight;
    for (const el of document.querySelectorAll("body *")) {
        const st = getComputedStyle(el);
        if (st.position !== "fixed" && st.position !== "sticky") continue;
        const r = el.getBoundingClientRect();
        if (r.width < 60 || r.height < 20) continue;
        if (el.parentElement && getComputedStyle(el.parentElement).position === "fixed")
            continue;                       // on ne liste que le conteneur
        let sel = el.tagName.toLowerCase();
        if (el.id) sel = "#" + CSS.escape(el.id);
        else if (el.classList.length)
            sel += "." + [...el.classList].slice(0, 2).map(c => CSS.escape(c)).join(".");
        out.push({
            selector: sel,
            surface: Math.round((r.width * r.height) / (vw * vh) * 100),
            texte: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 60),
        });
    }
    return out;
}"""


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
    if not args.brut:
        gone = []
        # Deux passes : certaines plateformes réinjectent leur fenêtre juste
        # après le chargement, et un voile n'apparaît parfois qu'une fois la
        # fenêtre partie.
        for i in range(2):
            if i:
                time.sleep(0.5)
            try:
                gone += page.evaluate(DECLUTTER)
            except Exception as exc:
                print(f"  nettoyage impossible ({str(exc).splitlines()[0][:60]})",
                      file=sys.stderr)
                break
        if gone:
            par_motif = {}
            for item in gone:
                par_motif.setdefault(item["motif"], []).append(item["quoi"])
            print(f"  nettoyé : {len(gone)} élément(s)")
            for motif, quoi in par_motif.items():
                print(f"    {motif:16} {', '.join(dict.fromkeys(quoi))[:64]}")

    for selector in args.hide:
        # Retirés du DOM, jamais cliqués — cliquer reviendrait à choisir à la
        # place de l'utilisateur.
        try:
            n = page.evaluate(
                """sel => { const l = document.querySelectorAll(sel);
                            l.forEach(n => n.remove()); return l.length; }""",
                selector)
        except Exception:
            print(f"  --hide {selector!r} : sélecteur invalide", file=sys.stderr)
            continue
        print(f"  --hide {selector} : {n} élément(s) retiré(s)"
              if n else f"  --hide {selector} : rien ne correspond",
              file=sys.stderr if not n else sys.stdout)

    for needle in args.hide_text:
        gone = page.evaluate(HIDE_BY_TEXT, needle)
        print(f"  --hide-text {needle!r} : {len(gone)} bloc(s) retiré(s)"
              + (f" ({', '.join(gone)})" if gone else ""),
              file=sys.stderr if not gone else sys.stdout)

    if args.list_overlays:
        found = page.evaluate(LIST_OVERLAYS)
        print("  ce qui flotte au-dessus de la page :")
        for o in sorted(found, key=lambda x: -x["surface"]):
            print(f"    {o['selector']:38} {o['surface']:3}% de l'écran"
                  + (f"  « {o['texte']} »" if o["texte"] else ""))
        if not found:
            print("    (rien)")

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

        if args.login:
            # Le profil dédié est persistant : ce qui est fait ici — connexion,
            # réponse au bandeau cookies — vaut pour toutes les captures
            # suivantes, sans --login.
            #
            # C'est aussi la seule façon de RÉPONDRE à un bandeau de
            # consentement. Le nettoyage automatique ne fait que le retirer de
            # l'image : le choix, lui, n'appartient qu'à l'utilisateur, et
            # certains sites gardent leur contenu fermé tant qu'il n'est pas
            # fait.
            #
            # On rend la fenêtre à sa taille normale le temps de la
            # manipulation : cliquer dans une fenêtre bridée à 390 px est pénible.
            session.send("Emulation.clearDeviceMetricsOverride")
            print("\n  Chrome est ouvert sur la page. Fais ce que tu as à faire "
                  "dans la fenêtre\n  — te connecter, répondre au bandeau "
                  "cookies — puis reviens ici\n  et appuie sur Entrée.")
            try:
                input("  > ")
            except EOFError:
                print("  (pas de terminal interactif : on continue sans attendre)")
            set_metrics(session, width, height, args.scale)

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
    parser.add_argument("--hide-text", action="append", default=[], metavar="TEXTE",
                        help="retirer le bloc où figure ce texte, sans avoir à "
                             "connaître de sélecteur (répétable)")
    parser.add_argument("--list-overlays", action="store_true",
                        help="lister ce qui flotte au-dessus de la page, avec "
                             "le sélecteur à donner à --hide")
    parser.add_argument("--brut", "--keep-banners", action="store_true",
                        dest="brut",
                        help="capturer la page telle quelle, sans le nettoyage "
                             "automatique")
    parser.add_argument("--dark", action="store_true",
                        help="forcer le thème sombre de la page")
    parser.add_argument("--format", choices=["png", "jpeg"], default="png")
    parser.add_argument("--quality", type=int, default=85,
                        help="qualité JPEG (1-100)")
    parser.add_argument("--name", help="nom de fichier imposé (sans extension)")
    parser.add_argument("--timeout", type=int, default=45,
                        help="délai maximum par page, en secondes")
    parser.add_argument("--login", "--pause", action="store_true", dest="login",
                        help="ouvrir la page et attendre que tu agisses à la "
                             "main — te connecter, répondre au bandeau cookies "
                             "— avant de photographier ; le profil dédié garde "
                             "le choix pour les fois suivantes")
    parser.add_argument("--profile", nargs="?", const="Default", metavar="NOM",
                        help="utiliser TON profil Chrome (sessions et cookies) "
                             "au lieu du profil dédié ; « Default » par défaut, "
                             "sinon « Profile 1 », « Profile 2 »…")
    parser.add_argument("--user-data-dir", metavar="DOSSIER",
                        help="dossier de profils Chrome, si le tien n'est pas "
                             "à l'emplacement habituel")
    parser.add_argument("--keep-open", action="store_true",
                        help="laisser Chrome ouvert à la fin")
    args = parser.parse_args()

    args.size = args.size or [(1440, 900)]
    if args.name and (len(args.urls) > 1 or len(args.size) > 1):
        parser.error("--name ne convient qu'à une seule URL et une seule taille : "
                     "sinon les images s'écraseraient entre elles")

    out = Path(args.out)
    print(f"→ {len(args.urls)} page(s) × {len(args.size)} taille(s) vers {out}")

    # Profil réel : les pages sont vues comme par toi, sessions ouvertes
    # comprises. C'est l'intérêt, et c'est aussi pourquoi une capture peut
    # contenir des informations personnelles — regarde ce que tu partages.
    user_dir = None
    if args.profile or args.user_data_dir:
        user_dir = Path(args.user_data_dir) if args.user_data_dir else chrome_user_data_dir()
        if not user_dir.exists():
            print(f"profil Chrome introuvable : {user_dir}\n"
                  f"  → indique-le avec --user-data-dir", file=sys.stderr)
            return 1
        # ⚠️ Depuis Chrome 136, `--remote-debugging-port` est IGNORÉ sur le
        # profil par défaut : durcissement voulu par Google, pour qu'un
        # programme local ne puisse pas lire les cookies du navigateur. Le
        # drapeau est bien passé, le port ne s'ouvre simplement jamais. Aucune
        # manipulation n'en vient à bout — autant le dire tout de suite.
        if user_dir == chrome_user_data_dir():
            print(
                "\nLe profil Chrome par défaut ne peut pas être piloté : depuis "
                "Chrome 136, --remote-debugging-port y est ignoré (Google a fermé\n"
                "cette porte pour qu'un programme local ne puisse pas lire tes "
                "cookies). Le drapeau part bien, le port ne s'ouvre jamais.\n\n"
                "Deux voies qui marchent :\n"
                "  1. --login : connecte-toi UNE fois dans le profil dédié de "
                "l'outil, il garde la session ensuite.\n"
                f"       python shoot.py {args.urls[0]} --login\n"
                "  2. --user-data-dir vers une COPIE de ton profil (Chrome "
                "accepte le pilotage hors dossier par défaut).",
                file=sys.stderr)
            return 1
        print(f"profil : {user_dir}\\{args.profile or 'Default'}")
        # Un `--user-data-dir` distinct démarre sa propre instance, même si
        # Chrome tourne par ailleurs — mais pas si le port est déjà pris.
        if chrome_is_running() and not debug_port_open():
            print("  (Chrome est ouvert par ailleurs ; ce profil-ci démarrera "
                  "sa propre instance)")

    written = []
    with CdpBrowser(keep_open=args.keep_open, user_data_dir=user_dir,
                    profile_name=(args.profile or "Default") if user_dir else None) as browser:
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
