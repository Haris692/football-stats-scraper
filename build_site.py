"""Le site public : une charge utile normalisée pour des pages statiques.

`build_console.py` fabrique **un outil** — un fichier unique, autonome, qui
s'ouvre hors ligne. Ce script-ci fabrique **un site** : plusieurs pages, des
feuilles de style et des modules séparés, et les données dans un JSON à part.

La différence est assumée : un site multi-pages charge ses données par `fetch`,
donc il lui faut un serveur (GitHub Pages, ou `python serve.py`). Il ne
s'ouvrira pas en double-cliquant un fichier. En échange, on peut y naviguer.

    python build_site.py                 # depuis le cache
    python build_site.py --force         # tout retélécharger

Deux fichiers en sortie, chargés **en parallèle** par le site :

- `data/site.json`  — tout sauf les images (~250 Ko)
- `data/crests.json` — les écussons en `data:` URI (~390 Ko)

Les séparer évite que la page attende 390 Ko d'images pour afficher un score.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from build_console import (add_source_arguments, assemble, load_broadcasts,
                           attach_broadcast)
from crests import load_store
from fetch_events import load as load_events
from fetch_flashscore import normalise
from fetch_squads import ALIASES, load as load_squads
from hosts import verdicts as host_verdicts, load_verdict_source

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "data" / "site.json"
CRESTS = ROOT / "data" / "crests.json"


def key(name: str) -> str:
    k = normalise(name or "")
    return ALIASES.get(k, k)


def freshest_standings(matches: list[dict]) -> list[dict]:
    """Le classement le plus récent parmi toutes les fiches.

    ⚠️ Chaque page match de Forebet embarque le classement **à sa date**. Prendre
    la première fiche venue affichait donc une table périmée de plusieurs
    journées — constaté le 11/08/2026, Yarmouk 1er à 35 pts alors que Sahel
    menait à 37. On retient celle dont les équipes ont disputé le plus de
    rencontres.
    """
    best, best_played = [], -1
    for match in matches:
        table = match.get("standings") or []
        if not table:
            continue
        total = sum(row.get("played") or 0 for row in table)
        if total > best_played:
            best, best_played = table, total
    return best


def team_directory(matches: list[dict], fixtures: list[dict]) -> dict:
    """Un annuaire des clubs, monté une fois pour tout le site.

    La console n'avait jamais besoin de ça : elle n'affichait que les deux
    équipes d'une rencontre. Un site a une page « clubs », une page par club et
    un classement — il lui faut le catalogue, pas deux fiches.
    """
    squads = load_squads().get("teams") or {}
    store = load_store()

    # Le nom canonique est celui de Forebet : c'est lui qui est écrit partout
    # ailleurs, et celui auquel les écussons sont indexés.
    names: dict[str, str] = {}
    for fixture in fixtures:
        for side in ("home", "away"):
            if fixture.get(side):
                names.setdefault(key(fixture[side]), fixture[side])

    standings = freshest_standings(matches)
    ranked = {key(row["team"]): row for row in standings}

    out = {}
    for k, name in sorted(names.items(), key=lambda x: x[1]):
        squad = squads.get(k) or {}
        entry = store.get(name) or {}
        out[k] = {
            "key": k,
            "name": name,
            "sofascore_name": squad.get("sofascore_name"),
            "manager": squad.get("manager"),
            "city": squad.get("city"),
            "colors": entry.get("colors") or [],
            "season": squad.get("season") or {},
            "players": squad.get("players") or [],
            "standing": ranked.get(k),
        }
    return out


def scorer_board(teams: dict) -> list[dict]:
    """Le classement des buteurs, reconstruit depuis les effectifs.

    Sofascore ne publie que les 50 premiers ; les buts sont déjà accrochés à
    chaque joueur par `fetch_squads`, il suffit de les remettre à plat.
    """
    rows = []
    for club in teams.values():
        for player in club["players"]:
            if player.get("goals"):
                rows.append({
                    "name": player["name"],
                    "team": club["key"],
                    "goals": player["goals"],
                    "position": player.get("position"),
                    "country_code": player.get("country_code"),
                })
    rows.sort(key=lambda r: (-r["goals"], r["name"]))
    return rows


def season_events(teams: dict, force: bool = False) -> list[dict]:
    """Toutes les rencontres de la saison, arbitrées.

    `fixtures` ne couvre que la fenêtre que Forebet expose. Sofascore, lui, a la
    saison entière — c'est ce qui permet un calendrier qui commence en septembre
    et une page club avec tous ses résultats.

    ⚠️ Mais Sofascore oriente domicile/extérieur **à l'envers de Flashscore sur
    61 rencontres sur 70** (voir `hosts.py`). Publier son hôte tel quel
    inverserait donc presque tout le calendrier. Or Flashscore couvre elle aussi
    la saison entière, par sa page « résultats » : on arbitre chaque rencontre
    contre elle, exactement comme on le fait pour la fenêtre récente.

    Ce que Flashscore ne connaît pas garde l'orientation Sofascore et sort
    marqué `arbitrated: False` — le site affiche alors l'affiche sans prétendre
    savoir qui reçoit.
    """
    try:
        table = host_verdicts(load_verdict_source(force=force))
    except Exception as exc:                      # une source d'appoint absente
        print(f"arbitrage du calendrier indisponible ({exc})", file=sys.stderr)
        table = {}

    out = []
    for event in (load_events().get("events") or []):
        home, away = event.get("home_key"), event.get("away_key")
        if home not in teams or away not in teams:
            continue
        hs = event.get("home_score")
        aws = event.get("away_score")
        day = (event.get("kickoff") or "").split(" ")[0]
        verdict = table.get((day, frozenset((home, away))))

        arbitrated = verdict is not None
        if arbitrated and verdict != home:
            home, away = away, home
            hs, aws = aws, hs

        out.append({
            "round": event.get("round"),
            "kickoff": event.get("kickoff"),
            "kickoff_iso": event.get("kickoff_iso"),
            "home": home,
            "away": away,
            "home_score": hs,
            "away_score": aws,
            "finished": event.get("finished"),
            "arbitrated": arbitrated,
        })
    out.sort(key=lambda e: e["kickoff_iso"] or "")
    done = sum(1 for e in out if e["arbitrated"])
    print(f"calendrier de saison : {done}/{len(out)} rencontre(s) arbitrée(s)")
    return out


def build(matches: list[dict], fixtures: list[dict],
          force: bool = False) -> tuple[dict, dict]:
    now = datetime.now()
    teams = team_directory(matches, fixtures)
    store = load_store()

    # Les rencontres portent la clé de chaque club : les pages lient par clé,
    # jamais par nom — un nom se réécrit, une clé non.
    for fixture in fixtures:
        fixture["home_key"] = key(fixture.get("home", ""))
        fixture["away_key"] = key(fixture.get("away", ""))

    detail = {}
    for match in matches:
        match = dict(match)
        match["home_key"] = key(match.get("home", ""))
        match["away_key"] = key(match.get("away", ""))
        # Les effectifs vivent maintenant dans l'annuaire : les répéter dans
        # chaque fiche pesait deux fois pour rien.
        match.pop("squads", None)
        match.pop("crests", None)
        detail[str(match["match_id"])] = match

    events = load_events()
    site = {
        "generated": now.strftime("%d/%m/%Y à %H:%M"),
        "generated_iso": now.isoformat(timespec="minutes"),
        "today": now.strftime("%d/%m/%Y"),
        "season": events.get("season_year"),
        "current_round": events.get("current_round"),
        "competition": "Zain First Division",
        "country": "Koweït",
        "teams": teams,
        "fixtures": fixtures,
        "matches": detail,
        "standings": freshest_standings(matches),
        "scorers": scorer_board(teams),
        "season_events": season_events(teams, force),
    }
    crests = {k: (store.get(v["name"]) or {}).get("badge")
              for k, v in teams.items()}
    return site, {k: v for k, v in crests.items() if v}


def main() -> int:
    parser = argparse.ArgumentParser(description="Site public.")
    add_source_arguments(parser)
    args = parser.parse_args()
    if not args.urls and not args.file:
        args.fixtures = True
        args.scope = "all"

    matches, fixtures = assemble(args)
    if not matches:
        print("aucune fiche récupérée — rien à écrire", file=sys.stderr)
        return 1

    site, crests = build(matches, fixtures, args.force)
    SITE.parent.mkdir(parents=True, exist_ok=True)
    SITE.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
    CRESTS.write_text(json.dumps(crests, ensure_ascii=False), encoding="utf-8")

    print(f"écrit : {SITE.name}   ({SITE.stat().st_size // 1024} Ko, "
          f"{len(site['teams'])} clubs, {len(site['fixtures'])} rencontres, "
          f"{len(site['matches'])} fiches, {len(site['season_events'])} "
          f"rencontres de saison)")
    print(f"écrit : {CRESTS.name} ({CRESTS.stat().st_size // 1024} Ko, "
          f"{len(crests)} écussons)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
