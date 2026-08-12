"""Liste les rencontres depuis la page ligue Forebet.

La page ligue porte à la fois la journée à venir et les résultats récents. On en
tire de quoi alimenter la console : identité du match, coup d'envoi, score s'il
est joué, et l'URL de la fiche détaillée.

    python fetch_fixtures.py                 # depuis le cache si possible
    python fetch_fixtures.py --force         # rafraîchit la page ligue
    python fetch_fixtures.py --out data.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from browser import ForebetBrowser

LEAGUE_URL = "https://www.forebet.com/fr/predictions-kuwait/1st-division"
# Plus court que les six heures par défaut : c'est la page qui porte les scores.
LEAGUE_MAX_AGE_HOURS = 1.0
MATCH_ID_RE = re.compile(r"/matches/(?P<slug>.+?)-(?P<id>\d+)(?:$|[/?#])")


def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def parse_fixtures(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")

    # La page glisse deux ou trois rencontres d'autres championnats en pied de
    # page (`#body-cont`) : elles portent un autre `shortTag` et n'ont rien à
    # faire ici. On ne garde que le tableau principal.
    main = soup.select_one("#body-main") or soup
    fixtures = []

    for row in main.select("div.rcnt"):
        link = row.select_one("a.tnmscn") or row.select_one('a[href*="/matches/"]')
        href = link.get("href", "") if link else ""
        match = MATCH_ID_RE.search(href)
        if not match:
            continue

        # `.l_scr` est vide tant que le match n'est pas joué : c'est ce qui
        # distingue une rencontre à venir d'un résultat.
        score = _txt(row.select_one(".l_scr")) or None
        kickoff = _txt(row.select_one(".date_bah")) or None

        fixtures.append({
            "match_id": int(match.group("id")),
            "url": f"https://www.forebet.com{href}",
            "competition_tag": _txt(row.select_one(".shortTag")) or None,
            "home": _txt(row.select_one(".homeTeam")),
            "away": _txt(row.select_one(".awayTeam")),
            "kickoff": kickoff,
            "kickoff_iso": to_iso(kickoff),
            "score": score,
            "played": bool(score),
        })

    fixtures.sort(key=lambda f: f["kickoff_iso"] or "")
    return fixtures


def to_iso(kickoff: str | None) -> str | None:
    """« 06/08/2026 19:45 » -> « 2026-08-06T19:45 », pour trier et comparer."""
    if not kickoff:
        return None
    try:
        return datetime.strptime(kickoff.strip(), "%d/%m/%Y %H:%M").isoformat(timespec="minutes")
    except ValueError:
        return None


def load_league_html(force: bool = False) -> str:
    """La page ligue, du cache si elle est encore fraîche.

    ⚠️ **Cette page est la seule à porter `score` et `played`** pour tout le
    calendrier — les fiches de match détaillées ont leur `full_time`, mais rien
    ne le remonte dans la liste. Un cache périmé ici, et le site affiche « à
    venir » une rencontre jouée la veille, alors même que sa fiche en connaît le
    score. C'est arrivé le 12/08/2026 : la page datait du 11 à 08:16, dix heures
    avant le coup d'envoi, et le calendrier est resté bloqué là.

    La cause était que ce cache **n'avait aucune limite d'âge** : le seul
    `exists()` suffisait, ce que `browser.get()` ne fait jamais. Une heure est
    court par rapport aux six heures par défaut, et c'est voulu : cette page-là
    change plusieurs fois par jour, et elle ne coûte qu'une requête.
    """
    with ForebetBrowser(max_age_hours=LEAGUE_MAX_AGE_HOURS) as browser:
        return browser.get(LEAGUE_URL, wait_for="div.rcnt", force=force)


def main() -> int:
    parser = argparse.ArgumentParser(description="Liste les rencontres de la ligue.")
    parser.add_argument("--force", action="store_true", help="rafraîchir la page ligue")
    parser.add_argument("--out", help="écrire le JSON dans ce fichier")
    args = parser.parse_args()

    fixtures = parse_fixtures(load_league_html(args.force))
    if args.out:
        Path(args.out).write_text(json.dumps(fixtures, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"écrit : {args.out}")

    upcoming = [f for f in fixtures if not f["played"]]
    print(f"{len(fixtures)} rencontres, dont {len(upcoming)} à venir\n")
    for f in fixtures:
        state = f["score"] if f["played"] else "à venir"
        print(f"  {f['kickoff'] or '?':17} {f['home']:>18} - {f['away']:18} {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
