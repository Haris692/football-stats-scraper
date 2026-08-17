"""Les faits de jeu d'une rencontre en cours : buts et cartons, chez Sofascore.

Ce qui manquait au direct, constaté le 17/08/2026 pendant la J20 : le score
bougeait (0-3 à la 51e sur Sporty - Khaitan) mais la page ne disait ni QUI ni
QUAND. La chronologie affichée vient de `data/events.json`, collecté le matin :
un but marqué le soir n'y est que le lendemain. Et le relevé de Forebet, qui
porte pourtant un champ `timeline`, était vide sur trois rencontres sur quatre
et sans nom de buteur sur la quatrième.

Sofascore, lui, nomme les buteurs — c'est déjà la raison pour laquelle le
projet l'interroge chaque matin (`fetch_events.timeline`). On réutilise
exactement la même fonction, donc le même format, à ceci près qu'on la demande
**pendant** le match au lieu du lendemain.

⚠️ **Une requête par rencontre**, contrairement à l'horloge : les faits de jeu
n'ont pas de point d'entrée par journée. C'est l'appelant qui décide quand
rafraîchir — `serve.py` ne le fait qu'au changement de score, ou toutes les cinq
minutes, jamais à chaque relevé.

⚠️ **L'orientation est celle de Sofascore, et il inverse.** Sur 61 des 70
rencontres de la saison, son hôte n'est pas le nôtre (voir `hosts.py`). Un but
`isHome` chez lui est donc parfois un but de notre visiteur : les camps sont
permutés ici, avec les scores intermédiaires qui les accompagnent. Sans ça, le
direct afficherait les buts du bon match dans le mauvais sens.

⚠️ **Le rapprochement ne coûte aucune requête** : `data/events.json` porte déjà
`sofascore_id` pour chaque rencontre de la saison. On y lit l'identifiant et
l'orientation, et on ne sort sur le réseau que pour les faits de jeu eux-mêmes.

    python fetch_live_events.py           # les rencontres du jour
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from browser import CdpBrowser
from fetch_clock_sofa import EVENTS, _day, _pair, _today_fixtures
from fetch_events import timeline
from fetch_squads import key

ROOT = Path(__file__).resolve().parent


def _swap_score(score: str | None) -> str | None:
    """« 0-2 » devient « 2-0 ». Même règle que `hosts._swap_score`."""
    found = re.match(r"^\s*(\d+)(\s*[-–]\s*)(\d+)\s*$", score or "")
    return f"{found[3]}{found[2]}{found[1]}" if found else score


def _flip(line: list[dict]) -> list[dict]:
    """Le fil du match vu depuis notre hôte à nous."""
    return [{**item,
             "side": "away" if item.get("side") == "home" else "home",
             "score": _swap_score(item.get("score"))}
            for item in line]


def events_for(fixtures: list[dict]) -> dict[int, tuple[int, bool]]:
    """{match_id: (identifiant Sofascore, faut-il permuter)}.

    Lu dans `data/events.json`, sans requête. Une rencontre que le fichier ne
    connaît pas — collecte du matin plus ancienne que le calendrier — n'a
    simplement pas de clé : l'appelant s'en passe.
    """
    try:
        blob = json.loads(EVENTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    index = {}
    for event in blob.get("events") or []:
        day = _day(event.get("kickoff_iso"))
        home, away = event.get("home_key"), event.get("away_key")
        if day and home and away and event.get("sofascore_id"):
            index[(day, frozenset((home, away)))] = event

    out = {}
    for fixture in fixtures:
        mid = fixture.get("match_id")
        if not mid:
            continue
        event = index.get((_day(fixture.get("kickoff_iso")),
                           _pair(fixture.get("home"), fixture.get("away"))))
        if event is None:
            continue
        out[int(mid)] = (int(event["sofascore_id"]),
                         event.get("home_key") != key(fixture.get("home") or ""))
    return out


def fetch(fixtures: list[dict], browser: CdpBrowser | None = None,
          force: bool = True) -> dict:
    """{match_id: [faits de jeu]}, dans notre orientation.

    Une rencontre dont la source ne dit rien rend une liste vide — pas
    d'absence de clé : « aucun but pour l'instant » est une réponse, et
    l'appelant doit pouvoir la distinguer de « pas encore demandé ».
    """
    pairs = events_for(fixtures)
    if not pairs:
        return {}

    owned = browser is None
    browser = browser or CdpBrowser()
    out = {}
    try:
        for mid, (sofa_id, inverse) in pairs.items():
            try:
                line = timeline(browser, sofa_id, force=force, max_age_hours=0)
            except Exception as exc:
                # Une rencontre qui tousse ne doit pas emporter les trois
                # autres : le direct en publie autant qu'il en a.
                print(f"  faits de jeu : #{mid} indisponible ({exc})",
                      file=sys.stderr, flush=True)
                continue
            out[mid] = _flip(line) if inverse else line
    finally:
        if owned:
            browser.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Les faits de jeu des rencontres du jour, chez Sofascore.")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args()

    fixtures = _today_fixtures()
    if not fixtures:
        print("aucune rencontre aujourd'hui dans nos données")
        return 0
    lines = fetch(fixtures)

    if args.json:
        print(json.dumps(lines, ensure_ascii=False, indent=2))
        return 0

    for fixture in fixtures:
        line = lines.get(int(fixture["match_id"]))
        print(f"\n  {fixture.get('home', '')} - {fixture.get('away', '')}")
        if line is None:
            print("    pas de correspondance dans events.json")
            continue
        if not line:
            print("    rien pour l'instant")
        for item in line:
            stamp = f"{item['minute']}{'+' + str(item['added']) if item['added'] else ''}'"
            print(f"    {stamp:>6}  {item['side']:>5}  {item['type']}/{item['class']}"
                  f"  {item['player'] or '—'}  {item['score'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
