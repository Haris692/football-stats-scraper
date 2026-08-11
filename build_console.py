"""Construit `console.html` — une console autonome à partir des pages en cache.

Le HTML produit ne fait aucune requête à l'ouverture : les données sont injectées
dans `console_template.html` à la place du jeton `/*__CONSOLE_DATA__*/`. La page
s'ouvre donc en `file://` et fonctionne hors ligne. (Même principe que
`build_dashboard.py` du projet `kuwait-football`.)

    python build_console.py                     # tous les matchs en cache
    python build_console.py --file cache/x.html # un fichier précis
    python build_console.py <url> [<url> ...]   # par URL (via le cache réseau)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from browser import CACHE_DIR, CdpBrowser, ForebetBrowser, cache_path
from crests import load_store, pair_note
from fetch_fixtures import load_league_html, parse_fixtures, to_iso
from fetch_flashscore import load as load_calendar, normalise
from fetch_squads import for_team as squad_for, load as load_squads
from fetch_events import for_match as event_for, key as event_key, load as load_events
from fetch_stats import fetch as fetch_stats
from hosts import arbitrate, load_verdict_source
from parse_match import parse_match

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "console_template.html"
OUTPUT = ROOT / "console.html"
TOKEN = "/*__CONSOLE_DATA__*/null"

def data_file_for(page: Path) -> Path:
    """`index.html` -> `index.data.json`, à côté de la page.

    Le nom suit celui de la page, et pas un `data.json` unique : sinon un build
    local sur `console.html` écraserait la donnée publiée à côté de
    `index.html`, et le dépôt se salirait à chaque essai. Le bouton
    « Rafraîchir » reconstruit ce nom depuis l'URL courante.
    """
    return page.parent / (page.stem + ".data.json")

# Les cinq blocs de résultats arrivent toujours dans cet ordre (voir PROGRESS.md).
# Leurs titres d'origine sont peu lisibles (« AL Les 6 derniers matchs ») : on
# les réécrit avec le nom de l'équipe concernée.
BLOCK_TITLES = [
    "Face à face",
    "{home} — toutes compétitions",
    "{away} — toutes compétitions",
    "{home} à domicile",
    "{away} à l'extérieur",
]


def decorate(match: dict) -> dict:
    blocks = match.get("result_blocks", [])
    if len(blocks) == len(BLOCK_TITLES):
        for block, pattern in zip(blocks, BLOCK_TITLES):
            block["display_title"] = pattern.format(
                home=match.get("home") or "Domicile",
                away=match.get("away") or "Extérieur",
            )
    else:
        # Structure inattendue : on garde le titre de la source plutôt que de
        # coller un mauvais libellé sur un bloc.
        for block in blocks:
            block["display_title"] = block.get("title")

    for block in blocks:
        block["subject"] = subject_of(block)

    # La console présente les relevés des deux équipes, pas une prédiction : les
    # pronostics de la source sont retirés de la charge utile. `parse_match.py`
    # continue de les extraire — ils restent disponibles dans son JSON.
    match.pop("predictions", None)
    return match


def subject_of(block: dict) -> str | None:
    """Nom de l'équipe dont le bloc dresse le bilan.

    Indispensable pour le face à face : son bilan est celui d'UNE des deux
    équipes (celle marquée `active-team` par la source), et rien dans le titre
    ne le dit. Sans ça, « 2V 0N 0D » serait spontanément attribué à l'équipe
    qui reçoit — l'inverse de la vérité dans notre match de test.
    """
    for row in block.get("matches", []):
        if row.get("subject_side") == "home":
            return row.get("home")
        if row.get("subject_side") == "away":
            return row.get("away")
    return None


def cached_match_pages() -> list[Path]:
    """Les pages match déjà en cache (la page ligue n'en est pas une)."""
    return sorted(CACHE_DIR.glob("fr-football-matches-*.html"))


def fetch_many(urls: list[str], force: bool) -> list[dict]:
    """Récupère et parse une liste de pages match, en n'ouvrant Chrome que si
    au moins une page manque au cache."""
    matches = []
    browser = None
    try:
        for url in urls:
            cached = cache_path(url)
            if cached.exists() and not force:
                html = cached.read_text(encoding="utf-8", errors="replace")
            else:
                if browser is None:
                    browser = ForebetBrowser().__enter__()
                html = browser.get(url, wait_for="#m1x2_table .rcnt", force=force)
            matches.append(decorate(parse_match(html)))
    finally:
        if browser is not None:
            browser.close()
    return matches


def collect(urls: list[str], files: list[str], force: bool) -> list[dict]:
    matches = [decorate(parse_match(Path(p).read_text(encoding="utf-8", errors="replace")))
               for p in files]
    matches += fetch_many(urls, force)

    if not matches:
        for path in cached_match_pages():
            html = path.read_text(encoding="utf-8", errors="replace")
            matches.append(decorate(parse_match(html)))

    return matches


BROADCASTS = ROOT / "data" / "broadcasts.json"


def load_broadcasts() -> dict:
    """Diffuseurs saisis à la main (aucune source automatique — voir PROGRESS)."""
    if not BROADCASTS.exists():
        return {"channels": [], "matches": {}}
    data = json.loads(BROADCASTS.read_text(encoding="utf-8"))
    return {
        "channels": data.get("channels") or [],
        # Une valeur vide veut dire « pas encore renseigné », pas « aucune ».
        "matches": {str(k): v for k, v in (data.get("matches") or {}).items() if v},
    }


def attach_broadcast(items: list[dict], broadcasts: dict) -> None:
    for item in items:
        channel = broadcasts["matches"].get(str(item.get("match_id")))
        item["broadcast"] = {
            "channel": channel,
            # Sans saisie, on ne fait qu'énoncer les chaînes habituelles, et on
            # le dit : jamais présenté comme une certitude.
            "confirmed": bool(channel),
            "usual": broadcasts["channels"],
        }


def merge_calendar(fixtures: list[dict], calendar: list[dict]) -> int:
    """Ajoute les rencontres que la page ligue Forebet ne montre pas encore.

    Forebet reste la source de référence : il apporte l'identifiant du match et
    la fiche détaillée. Flashscore ne sert qu'à prolonger l'horizon — ses
    rencontres arrivent donc sans fiche, et sont marquées comme telles.
    """
    # Les deux sources n'écrivent pas les noms pareil : on garde ceux de
    # Forebet, qui sont ceux affichés partout ailleurs dans la console.
    canonical = {}
    for fixture in fixtures:
        canonical.setdefault(normalise(fixture["home"]), fixture["home"])
        canonical.setdefault(normalise(fixture["away"]), fixture["away"])

    tag = next((f.get("competition_tag") for f in fixtures if f.get("competition_tag")), None)

    # Une affiche déjà annoncée par Forebet ne doit pas réapparaître. On
    # rapproche sur la paire d'équipes pour les matchs à venir — les deux
    # sources peuvent diverger d'un jour sur l'horaire, et une même affiche ne
    # se rejoue pas dans la fenêtre couverte.
    # Le rapprochement ignore l'ordre des deux clubs : les sources ne
    # s'accordent pas toujours sur qui reçoit (voir `hosts.py`), et une paire
    # ordonnée laisserait alors passer la même affiche deux fois.
    upcoming = {frozenset((normalise(f["home"]), normalise(f["away"])))
                for f in fixtures if not f.get("played")}
    played = {(frozenset((normalise(f["home"]), normalise(f["away"]))),
               (f.get("kickoff") or "").split(" ")[0])
              for f in fixtures if f.get("played")}

    added = 0
    for entry in calendar:
        names = (normalise(entry["home"]), normalise(entry["away"]))
        pair = frozenset(names)
        if pair in upcoming:
            continue
        if (pair, (entry.get("kickoff") or "").split(" ")[0]) in played:
            continue

        fixtures.append({
            "match_id": None,
            "url": None,
            "competition_tag": tag,
            "home": canonical.get(names[0], entry["home"]),
            "away": canonical.get(names[1], entry["away"]),
            "kickoff": entry["kickoff"],
            "kickoff_iso": entry["kickoff_iso"],
            "score": None,
            "played": False,
            "source": "flashscore",
        })
        upcoming.add(pair)
        added += 1

    fixtures.sort(key=lambda f: f.get("kickoff_iso") or "")
    return added


# Un match terminé ne bouge plus : son relevé peut rester en cache très
# longtemps. Un match à venir ou en cours, lui, se remplit minute par minute.
STATS_AGE_FINISHED = 24 * 30
STATS_AGE_LIVE = 0.2


def attach_stats(matches: list[dict], fixtures: list[dict], force: bool) -> int:
    """Accroche à chaque fiche les statistiques réellement relevées du match.

    C'est la seule partie de la console qui décrit ce qui s'est passé sur le
    terrain : tout le reste (carte d'identité, comparatif, parcours) agrège la
    saison. D'où une carte à part dans la page, et pas une ligne de plus dans le
    comparatif.
    """
    played = {f.get("match_id") for f in fixtures if f.get("played")}
    ids = [m.get("match_id") for m in matches if m.get("match_id")]
    if not ids:
        return 0

    stats = {}
    browser = CdpBrowser()
    try:
        for group, age in ((
            [i for i in ids if i in played], STATS_AGE_FINISHED), (
            [i for i in ids if i not in played], STATS_AGE_LIVE),
        ):
            if group:
                stats.update(fetch_stats(group, browser=browser, force=force,
                                         max_age_hours=age))
    finally:
        browser.close()

    for m in matches:
        m["match_stats"] = stats.get(m.get("match_id"))
    return len(stats)


def attach_events(matches: list[dict], fixtures: list[dict]) -> tuple[int, int]:
    """Accroche ce que Sofascore sait d'une rencontre et que Forebet ignore.

    Trois choses : la **chronologie nommée** (buteurs et cartons, à la minute),
    les **deux entraîneurs du soir**, et le **numéro de journée**.

    ⚠️ **À lancer après `arbitrate()`, jamais avant.** Sofascore oriente
    domicile/extérieur à l'envers de Flashscore sur 61 rencontres sur 70 : on
    compare donc son hôte au nôtre, et on retourne son `side` quand ils
    diffèrent. Accrocher avant l'arbitrage reviendrait à comparer à une
    étiquette qu'on s'apprête à changer.
    """
    store = load_events()
    if not store.get("events"):
        return 0, 0

    def hook(item: dict) -> dict | None:
        event = event_for(store, item.get("home"), item.get("away"),
                          (item.get("kickoff") or "").split(" ")[0])
        if event:
            item["round"] = event.get("round")
        return event

    timelines = 0
    for match in matches:
        event = hook(match)
        if not event:
            continue
        # Le retournement éventuel, décidé une fois pour la fiche entière.
        flipped = event.get("home_key") != event_key(match.get("home") or "")
        other = {"home": "away", "away": "home"}

        def turn(item: dict) -> dict:
            if not flipped:
                return dict(item)
            # Le score courant porté par l'événement se retourne aussi : sans
            # ça la chronologie raconterait « 1-0 » au moment où notre hôte
            # vient d'encaisser.
            score = item.get("score")
            if score and "-" in score:
                left, right = score.split("-", 1)
                score = f"{right}-{left}"
            return dict(item, side=other[item["side"]], score=score)

        line = [turn(i) for i in event.get("timeline") or []]
        if line:
            match["timeline"] = line
            timelines += 1

        bench = event.get("managers") or {}
        if bench.get("home") or bench.get("away"):
            match["managers"] = ({"home": bench["away"], "away": bench["home"]}
                                 if flipped else dict(bench))

    rounds = 0
    for fixture in fixtures:
        if hook(fixture):
            rounds += 1
    return timelines, rounds


def reconcile(fixtures: list[dict], matches: list[dict]) -> None:
    """Aligne la date d'une rencontre sur celle de sa fiche.

    Constaté le 06/08/2026 : la page ligue plaçait quatre matchs le 06/08 alors
    que deux fiches, récupérées le jour même, annonçaient le 07/08. La page ligue
    est mise en cache et vieillit ; la fiche est la source la plus fraîche pour
    un match donné, donc c'est elle qui tranche.
    """
    by_id = {m.get("match_id"): m for m in matches}
    for fixture in fixtures:
        detail = by_id.get(fixture.get("match_id"))
        if not detail or not detail.get("kickoff"):
            continue
        if detail["kickoff"] != fixture.get("kickoff"):
            fixture["kickoff_ligue"] = fixture.get("kickoff")
            fixture["kickoff"] = detail["kickoff"]
            fixture["kickoff_iso"] = to_iso(detail["kickoff"])
    fixtures.sort(key=lambda f: f["kickoff_iso"] or "")


def make_payload(matches: list[dict], fixtures: list[dict]) -> dict:
    """La charge utile que consomme la console, embarquée comme servie à chaud."""
    now = datetime.now()
    teams = load_store()
    # Couleur retenue pour chaque camp, match par match : deux clubs peuvent
    # partager la même dominante (Khaitan et Sulaibikhat sont deux rouges).
    for m in matches:
        m["palette"] = pair_note(teams, m.get("home"), m.get("away"))

    # Les effectifs sont attachés à la fiche du match, pas envoyés en bloc : la
    # console n'affiche jamais que les deux équipes qui s'affrontent, et le
    # catalogue complet pèserait pour rien dans la page.
    squads = load_squads()
    for m in matches:
        m["squads"] = {
            "home": squad_for(squads, m.get("home")),
            "away": squad_for(squads, m.get("away")),
        }

    # « Aujourd'hui » est figé à la génération : la page est un fichier statique,
    # elle ne doit pas prétendre savoir quel jour on l'ouvre.
    return {
        "generated": now.strftime("%d/%m/%Y à %H:%M"),
        "today": now.strftime("%d/%m/%Y"),
        "now_iso": now.isoformat(timespec="minutes"),
        "squads_generated": squads.get("generated"),
        "teams": teams,
        "fixtures": fixtures,
        "matches": matches,
    }


def build(matches: list[dict], fixtures: list[dict], output: Path,
          data_file: Path | None = None) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    if TOKEN not in template:
        raise RuntimeError(f"jeton {TOKEN!r} absent de {TEMPLATE.name}")

    payload = make_payload(matches, fixtures)

    # `</script>` dans une valeur fermerait la balise : on neutralise la séquence.
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    output.write_text(template.replace(TOKEN, blob), encoding="utf-8")

    # La même charge utile, à côté de la page. Elle reste **aussi** embarquée :
    # la console doit continuer de s'ouvrir seule, en file:// et hors ligne.
    # Ce fichier ne sert qu'au bouton « Rafraîchir », qui va y chercher une
    # version plus récente que celle figée dans la page.
    #
    # Les écussons en sont retirés : 387 Ko de `data:` URI sur 556, pour des
    # images que la page a déjà et qui ne changent pas d'une collecte à l'autre.
    # La console garde les siennes quand la charge utile reçue n'en apporte pas
    # (voir `applyData()`).
    if data_file is not None:
        light = {k: v for k, v in payload.items() if k != "teams"}
        data_file.write_text(json.dumps(light, ensure_ascii=False),
                             encoding="utf-8")
    return output


def add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Les options de collecte, partagées par `build_console` et `build_json`.

    Les deux sorties consomment exactement les mêmes données : elles doivent
    aussi s'alimenter de la même façon, sinon les drapeaux divergent au premier
    ajout.
    """
    parser.add_argument("urls", nargs="*", help="URLs de pages match")
    parser.add_argument("--file", action="append", default=[],
                        help="fichier HTML local (répétable)")
    parser.add_argument("--fixtures", action="store_true",
                        help="partir de la page ligue : liste les rencontres et "
                             "récupère la fiche de chacune")
    parser.add_argument("--scope", choices=["upcoming", "all", "played"],
                        default="upcoming",
                        help="avec --fixtures : quelles fiches récupérer "
                             "(défaut : les rencontres à venir)")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--no-calendar", action="store_true",
                        help="ne pas compléter avec le calendrier Flashscore")
    parser.add_argument("--no-stats", action="store_true",
                        help="ne pas récupérer les statistiques relevées des matchs")
    parser.add_argument("--no-hosts", action="store_true",
                        help="ne pas arbitrer qui reçoit : garder l'étiquette "
                             "de Forebet telle quelle")


def assemble(args) -> tuple[list[dict], list[dict]]:
    """Collecte complète : renvoie (fiches, rencontres), enrichies et alignées.

    Renvoie deux listes vides si rien n'a pu être récupéré — à l'appelant de
    décider si c'est une erreur.
    """
    fixtures: list[dict] = []
    matches: list[dict] = []

    if args.fixtures:
        fixtures = parse_fixtures(load_league_html(args.force))
        wanted = [f for f in fixtures
                  if args.scope == "all"
                  or (args.scope == "upcoming" and not f["played"])
                  or (args.scope == "played" and f["played"])]
        print(f"{len(fixtures)} rencontres sur la page ligue, "
              f"{len(wanted)} fiche(s) à récupérer ({args.scope})…")
        matches = fetch_many([f["url"] for f in wanted], args.force)

    else:
        matches = collect(args.urls, args.file, args.force)

    if not matches:
        return [], []

    # Sans page ligue, on reconstruit une liste de rencontres minimale depuis les
    # fiches elles-mêmes, pour que la console ait toujours de quoi lister.
    if not fixtures:
        fixtures = [{
            "match_id": m.get("match_id"),
            "url": m.get("url"),
            "competition_tag": m.get("competition_tag"),
            "home": m.get("home"),
            "away": m.get("away"),
            "kickoff": m.get("kickoff"),
            "kickoff_iso": to_iso(m.get("kickoff")),
            "score": None,
            "played": False,
        } for m in matches]

    reconcile(fixtures, matches)

    if not args.no_calendar:
        try:
            added = merge_calendar(fixtures, load_calendar(args.force))
            print(f"calendrier Flashscore : {added} rencontre(s) ajoutée(s) "
                  f"au-delà de la journée en cours")
        except Exception as exc:
            # Une source d'appoint ne doit jamais faire échouer le build.
            print(f"calendrier Flashscore indisponible ({exc}) — on continue "
                  f"avec les seules rencontres Forebet", file=sys.stderr)

    if not args.no_stats:
        try:
            found = attach_stats(matches, fixtures, args.force)
            print(f"statistiques relevées : {found} match(s) sur {len(matches)} "
                  f"couvert(s) par la source")
        except Exception as exc:
            # Comme le calendrier, c'est un complément : il ne fait pas échouer
            # le build s'il tombe.
            print(f"statistiques de match indisponibles ({exc}) — on continue",
                  file=sys.stderr)

    # Après les statistiques, jamais avant : la permutation emporte les
    # colonnes de `match_stats`, qui doivent donc déjà être là.
    if not args.no_hosts:
        try:
            swaps = arbitrate(fixtures, matches, load_verdict_source(args.force))
            if swaps:
                print(f"qui reçoit : {len(swaps)} rencontre(s) remises dans le "
                      f"sens de Flashscore")
                for line in swaps:
                    print(f"  {line}")
            else:
                print("qui reçoit : aucune divergence avec Flashscore")
        except Exception as exc:
            # Comme le calendrier et les stats : un arbitre absent ne fait pas
            # échouer le build, il laisse l'étiquette de Forebet.
            print(f"arbitrage de l'hôte indisponible ({exc}) — on garde "
                  f"l'étiquette Forebet", file=sys.stderr)

    # Après l'arbitrage : Sofascore n'oriente pas les camps comme nous.
    try:
        lines, rounds = attach_events(matches, fixtures)
        print(f"Sofascore : {lines} chronologie(s) accrochée(s), "
              f"{rounds} rencontre(s) datées d'une journée")
    except Exception as exc:
        print(f"rencontres Sofascore indisponibles ({exc}) — on continue",
              file=sys.stderr)

    broadcasts = load_broadcasts()
    attach_broadcast(matches, broadcasts)
    attach_broadcast(fixtures, broadcasts)
    return matches, fixtures


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit la console HTML.")
    add_source_arguments(parser)
    parser.add_argument("--out", default=str(OUTPUT), help="fichier de sortie")
    parser.add_argument("--no-data-file", action="store_true",
                        help="ne pas écrire le data.json qui alimente le bouton "
                             "« Rafraîchir »")
    args = parser.parse_args()

    matches, fixtures = assemble(args)
    if not matches:
        print("aucun match à afficher : le cache est vide et aucune URL n'a été "
              "donnée.", file=sys.stderr)
        return 1

    out = Path(args.out)
    data_file = None if args.no_data_file else data_file_for(out)
    out = build(matches, fixtures, out, data_file)
    print(f"écrit : {out}  ({len(matches)} fiche(s) sur {len(fixtures)} rencontres, "
          f"{out.stat().st_size // 1024} Ko)")
    if data_file is not None:
        print(f"écrit : {data_file}  ({data_file.stat().st_size // 1024} Ko, "
              f"pour le bouton « Rafraîchir »)")
    for m in matches:
        print(f"  · {m['home']} - {m['away']}  {m['kickoff'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
