"""Écussons des clubs et couleurs qui en sont tirées.

Forebet sert les logos sous `/images/icons/{id}.png`, mais Cloudflare renvoie 403
sur un téléchargement direct : on passe par `ForebetBrowser.fetch_data_uri()`,
qui va chercher l'image depuis la page elle-même.

Chaque écusson est stocké en `data:` URI — la console reste ainsi un fichier
unique, consultable hors ligne, sans requête à l'ouverture. Les couleurs
dominantes sont extraites de l'image, ce qui donne les vraies couleurs du club
sans avoir à les saisir à la main.

    python crests.py            # complète data/teams.json depuis le cache
    python crests.py --force    # retélécharge tout
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from browser import ForebetBrowser

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data" / "teams.json"


# --- couleur ---------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(v / 255) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def oklab_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """Écart perceptuel, même échelle que le validateur du skill dataviz (x100)."""
    la, aa, ba = to_oklab(a)
    lb, ab, bb = to_oklab(b)
    return 100 * ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def from_oklab(lab: tuple[float, float, float]) -> tuple[int, int, int]:
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(round(_linear_to_srgb(v) * 255) for v in (r, g, bl))


def shift_lightness(hex_colour: str, delta: float) -> str:
    """Assombrit (delta < 0) ou éclaircit une couleur en gardant sa teinte."""
    rgb = tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    L, a, b = to_oklab(rgb)
    return hexa(from_oklab((max(0.0, min(1.0, L + delta)), a, b)))


def chroma(rgb: tuple[int, int, int]) -> float:
    _, a, b = to_oklab(rgb)
    return (a * a + b * b) ** 0.5


def hexa(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def dominant_colours(png: bytes, count: int = 2) -> list[str]:
    """Couleurs dominantes d'un écusson, les plus colorées d'abord.

    On regroupe les pixels par paquets grossiers puis on classe sur
    « fréquence x chroma » : sans la pondération par le chroma, le blanc du fond
    et le noir des contours sortent systématiquement en tête et on perd les
    couleurs réelles du club.
    """
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    img.thumbnail((72, 72))

    # `tobytes()` plutôt que `getdata()` : ce dernier est déprécié en Pillow 12.
    raw = img.tobytes()
    buckets: dict[tuple[int, int, int], list] = {}
    for i in range(0, len(raw), 4):
        r, g, b, alpha = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        if alpha < 140:
            continue
        key = (r // 26, g // 26, b // 26)
        slot = buckets.setdefault(key, [0, 0, 0, 0])
        slot[0] += 1
        slot[1] += r
        slot[2] += g
        slot[3] += b

    if not buckets:
        return []

    entries = []
    for n, sr, sg, sb in buckets.values():
        rgb = (sr // n, sg // n, sb // n)
        # +0.03 pour qu'un club réellement noir ou blanc reste candidat.
        entries.append((n * (chroma(rgb) + 0.03), n, rgb))
    entries.sort(reverse=True, key=lambda e: e[0])

    chosen: list[tuple[int, int, int]] = []
    for _, _, rgb in entries:
        # Deux teintes trop proches ne feraient pas une paire lisible.
        if all(oklab_distance(rgb, other) >= 12 for other in chosen):
            chosen.append(rgb)
        if len(chosen) == count:
            break
    return [hexa(c) for c in chosen]


# --- récupération ----------------------------------------------------------

def load_store() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def save_store(store: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def collect(pages: dict[str, list[str]], force: bool = False) -> dict:
    """Complète `data/teams.json` en visitant les pages match fournies.

    `pages` associe une URL de page match aux clubs qu'elle montre. On n'ouvre
    que les pages nécessaires pour couvrir les clubs manquants.
    """
    store = load_store()

    def missing(names):
        return [n for n in names
                if force or n not in store or not store[n].get("badge")]

    todo = {url: names for url, names in pages.items() if missing(names)}
    if not todo:
        return store

    with ForebetBrowser() as browser:
        for url, names in todo.items():
            if not missing(names):
                continue  # déjà couvert par une page précédente
            grabbed = browser.grab_images(url)
            for alt, data_uri in grabbed.items():
                name = alt[:-len(" - Logo")].strip() if alt.endswith("- Logo") else alt
                if not name or not data_uri.startswith("data:image"):
                    continue
                if name in store and store[name].get("badge") and not force:
                    continue
                raw = base64.b64decode(data_uri.split(",", 1)[1])
                store[name] = {"badge": data_uri, "colors": dominant_colours(raw)}
                print(f"    {name} -> {', '.join(store[name]['colors']) or '—'}")
            save_store(store)

    save_store(store)
    return store


def pair_note(store: dict, home: str, away: str) -> dict:
    """Couleur à donner à chaque camp pour un match donné.

    Deux clubs peuvent partager la même dominante : Khaitan `#f01a24` et
    Sulaibikhat `#de1f26` jouent tous les deux en rouge, et ils se rencontrent.

    On ne bascule PAS sur la couleur secondaire dans ce cas : celle de
    Sulaibikhat est un blanc cassé, et annoncer « Sulaibikhat = blanc » serait
    faux, sa couleur est le rouge. On garde donc les deux vraies couleurs et on
    en assombrit une jusqu'à ce que l'écart perceptuel soit suffisant — la
    teinte du club est conservée, seule sa clarté bouge.
    """
    ch = (store.get(home) or {}).get("colors") or []
    ca = (store.get(away) or {}).get("colors") or []
    home_c = ch[0] if ch else None
    away_c = ca[0] if ca else None
    clash = False
    away_true = away_c

    if home_c and away_c:
        def rgb(h):
            return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

        if oklab_distance(rgb(home_c), rgb(away_c)) < 15:
            clash = True
            # On pousse le camp extérieur du côté opposé à l'équipe qui reçoit,
            # par pas successifs, jusqu'à franchir le seuil de séparation.
            direction = -1 if to_oklab(rgb(home_c))[0] > 0.5 else 1
            for step in (0.10, 0.16, 0.22, 0.28):
                candidate = shift_lightness(away_true, direction * step)
                if oklab_distance(rgb(home_c), rgb(candidate)) >= 15:
                    away_c = candidate
                    break
            else:
                away_c = shift_lightness(away_true, direction * 0.28)

    def alt(colours, used):
        second = colours[1] if len(colours) > 1 else None
        return second if second and second != used else None

    return {
        "home": home_c, "away": away_c,
        "home_alt": alt(ch, home_c), "away_alt": alt(ca, away_c),
        "home_ink": ink_on(home_c), "away_ink": ink_on(away_c),
        "clash": clash,
        "away_true": away_true if clash else None,
    }


def ink_on(hex_colour: str | None) -> str | None:
    """Couleur de texte à poser sur ce fond.

    Certaines dominantes sont quasi blanches (Yarmouk) ou très sombres
    (Al Shamiya) : sans ça, une slide au fond du club se retrouverait en blanc
    sur blanc.
    """
    if not hex_colour:
        return None
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)
    return "sombre" if lum > 0.35 else "clair"


def main() -> int:
    parser = argparse.ArgumentParser(description="Écussons et couleurs des clubs.")
    parser.add_argument("--force", action="store_true", help="tout retélécharger")
    args = parser.parse_args()

    from build_console import cached_match_pages
    from parse_match import parse_crests, parse_header
    from bs4 import BeautifulSoup

    # Chaque page match montre les écussons de ses deux clubs : en visitant les
    # pages en cache on couvre toute la division.
    pages: dict[str, list[str]] = {}
    for path in cached_match_pages():
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
        url = parse_header(soup).get("url")
        names = list(parse_crests(soup))
        if url and names:
            pages[url] = names

    clubs = sorted({n for names in pages.values() for n in names})
    print(f"{len(clubs)} club(s) repérés sur {len(pages)} page(s) en cache")
    store = collect(pages, args.force)
    for name in sorted(store):
        print(f"  {name:20} {', '.join(store[name].get('colors') or []) or '—'}")
    print(f"\nécrit : {STORE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
