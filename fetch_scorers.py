"""Le classement des buteurs de la division, à sa source.

⚠️ **Ce module corrige un faux du site, trouvé le 12/08/2026.** Le classement
était jusqu'ici *reconstruit* : `fetch_squads` accrochait ses buts à chaque
joueur d'un effectif, et `build_site` remettait les effectifs à plat. Un
classement dérivé d'un effectif ne contient donc que les joueurs **encore
inscrits** — celui qui a quitté son club en cours de saison disparaît, ses buts
avec lui.

Le site affichait ainsi Allan Paulista (11) en tête, alors que le meilleur
buteur de la division est **Lucas Shallon (12 buts, Al Sulaibikhat)**, absent de
la liste faute d'être encore dans un effectif.

L'autorité, c'est le classement publié par la compétition elle-même :

    /unique-tournament/20044/season/{sid}/statistics?order=-goals

Il ne dépend d'aucun effectif : il énumère tous ceux qui ont joué dans la
saison, avec leur club **au moment où ils ont marqué**.

⚠️ **Ce qu'il ne donne pas, malgré les apparences.** L'endpoint accepte
`fields=assists,appearances,minutesPlayed` et renvoie les clés — toutes à
`null` sur cette division (vérifié le 12/08/2026). Il n'y a donc toujours ni
passe décisive, ni match joué, ni minute : **ne pas re-sonder**, et ne rien
promettre de tel sur la page. Les deux seuls chiffres réels sont `goals` et
`penaltyGoals`.

    python fetch_scorers.py             # écrit data/scorers.json
    python fetch_scorers.py --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from browser import CdpBrowser
from fetch_squads import BASE, HOST_PAGE, TOURNAMENT, key, season_id

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "scorers.json"

# Le classement se lit par pages de 100. Une division de 8 clubs tient
# largement en une : les buteurs y sont une centaine, et la page est triée par
# buts décroissants — on s'arrête donc au premier joueur à zéro plutôt que de
# paginer pour ramener cent lignes vides.
PAGE_SIZE = 100
MAX_PAGES = 4

# Le classement bouge à chaque journée : le garder une demi-journée suffit à
# éviter les rappels d'une même passe, sans jamais servir la veille au matin.
MAX_AGE_HOURS = 6.0


def fetch(browser: CdpBrowser, sid: int, force: bool) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        url = (f"{BASE}/api/v1/unique-tournament/{TOURNAMENT}/season/{sid}"
               f"/statistics?limit={PAGE_SIZE}&page={page}"
               f"&order=-goals&accumulation=total&fields=goals,penaltyGoals")
        data = browser.get_json(url, force=force, max_age_hours=MAX_AGE_HOURS,
                                referer=HOST_PAGE)
        results = (data or {}).get("results") or []
        if not results:
            break
        for row in results:
            player = row.get("player") or {}
            team = row.get("team") or {}
            goals = row.get("goals") or 0
            if not goals:
                # Trié par buts décroissants : le premier zéro clôt la liste.
                return rows
            if not player.get("id"):
                continue
            rows.append({
                "id": player["id"],
                "name": player.get("name"),
                "team": key(team.get("name") or ""),
                "team_name": team.get("name"),
                "goals": goals,
                "penalties": row.get("penaltyGoals") or None,
            })
        if page >= ((data or {}).get("pages") or 1):
            break
    return rows


def collect(force: bool = False) -> dict:
    with CdpBrowser() as browser:
        sid, year = season_id(browser, force)
        rows = fetch(browser, sid, force)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": "sofascore",
        "tournament": {"id": TOURNAMENT, "season_id": sid, "season": year},
        "scorers": rows,
    }


def load() -> dict:
    """Le classement déjà collecté, ou un squelette vide."""
    if not OUTPUT.exists():
        return {"scorers": []}
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def print_summary(data: dict) -> None:
    for i, row in enumerate(data["scorers"], 1):
        pen = f"  (dont {row['penalties']} pen.)" if row["penalties"] else ""
        print(f"  {i:3}. {str(row['goals']).rjust(2)}  "
              f"{(row['name'] or '?')[:28].ljust(28)} "
              f"{(row['team_name'] or row['team'] or '?')[:24]}{pen}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classement des buteurs.")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--out", default=str(OUTPUT))
    parser.add_argument("--summary", action="store_true",
                        help="le classement en clair")
    args = parser.parse_args()

    data = collect(args.force)
    if not data["scorers"]:
        print("aucun buteur récupéré.", file=sys.stderr)
        return 1

    # Un club inconnu du reste du site ne serait rattaché à rien : la page
    # afficherait un buteur sans écusson ni lien. Mieux vaut le voir ici.
    orphans = sorted({r["team_name"] for r in data["scorers"] if not r["team"]})
    if orphans:
        print(f"⚠️ club(s) non rapproché(s) : {', '.join(orphans)}",
              file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(r["goals"] for r in data["scorers"])
    print(f"écrit : {out}  ({len(data['scorers'])} buteurs, {total} buts)")
    if args.summary:
        print_summary(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
