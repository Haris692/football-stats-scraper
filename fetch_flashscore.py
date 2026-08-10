"""Calendrier lointain de la Division 1 koweïtienne, via Flashscore.

Pourquoi une deuxième source : la page ligue de Forebet ne montre que la journée
en cours et la précédente. Flashscore publie les journées suivantes — d'où un
horizon de plusieurs semaines au lieu de deux jours.

Ce que Flashscore N'A PAS pour cette division (vérifié, voir PROGRESS.md) : la
fiche match y est marquée « FINAL RESULT ONLY », donc ni statistiques, ni
compositions, ni chronologie. On ne lui demande que des dates et des affiches ;
tout le reste continue de venir de Forebet.

Accès : son robots.txt ne bloque aucun agent Anthropic, et n'interdit sous
`User-agent: *` que /standings/, /draw/ et /newsfeed/ — qu'on ne touche pas.

    python fetch_flashscore.py
    python fetch_flashscore.py --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from browser import CdpBrowser, cache_path

FIXTURES_URL = "https://www.flashscore.com/football/kuwait/division-1/fixtures/"


def normalise(name: str) -> str:
    """Clé de rapprochement entre les deux sources.

    Les mêmes clubs n'y portent pas le même nom : « Yarmouk (KUW) » chez Forebet
    contre « Yarmouk » chez Flashscore, « Sulaibikhat » contre « Al Sulaibikhat »,
    « Khaitan SC » contre « Khaitan ». On retire les préfixes, suffixes et
    parenthèses pour comparer ce qui reste.
    """
    n = (name or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"\b(al|fc|sc)\b", " ", n)
    return re.sub(r"[^a-z]+", "", n)


def resolve_year(day: int, month: int, now: datetime | None = None) -> int:
    """Flashscore n'affiche pas l'année (« 06.08. 19:45 »).

    On prend l'année courante, sauf si la date obtenue est loin dans le passé —
    auquel cas c'est un match de l'année suivante, cas du passage de décembre à
    janvier.
    """
    now = now or datetime.now()
    year = now.year
    try:
        candidate = datetime(year, month, day)
    except ValueError:
        return year
    if (now - candidate).days > 120:
        return year + 1
    return year


def parse_fixtures(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    fixtures = []

    for row in soup.select("div.event__match"):
        home = row.select_one(".event__homeParticipant")
        away = row.select_one(".event__awayParticipant")
        if not home or not away:
            continue

        # Les classes utiles sont hachées et changent à chaque déploiement
        # (`wcl-participant_bctDY`) : on s'appuie sur `data-testid`, stable.
        stage = row.select_one('[data-testid="wcl-stageTime"]')
        when = ""
        if stage:
            inner = stage.select_one('[data-testid="wcl-scores-simple-text-01"]')
            when = (inner or stage).get_text(" ", strip=True)

        match = re.match(r"(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2})", when)
        kickoff = kickoff_iso = None
        if match:
            day, month, hour, minute = (int(g) for g in match.groups())
            year = resolve_year(day, month)
            kickoff = f"{day:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}"
            kickoff_iso = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}"

        fixtures.append({
            "flashscore_id": (row.get("id") or "").replace("g_1_", "") or None,
            "home": home.get_text(" ", strip=True),
            "away": away.get_text(" ", strip=True),
            "kickoff": kickoff,
            "kickoff_iso": kickoff_iso,
            "source": "flashscore",
        })

    fixtures.sort(key=lambda f: f["kickoff_iso"] or "")
    return fixtures


def load(force: bool = False, max_age_hours: float = 6.0) -> list[dict]:
    cached = cache_path(FIXTURES_URL)
    if cached.exists() and not force:
        age = (datetime.now().timestamp() - cached.stat().st_mtime) / 3600
        if age <= max_age_hours:
            return parse_fixtures(cached.read_text(encoding="utf-8", errors="replace"))

    with CdpBrowser(max_age_hours=max_age_hours) as browser:
        # Le tableau est monté en JavaScript : on attend une vraie ligne.
        html = browser.get(FIXTURES_URL, wait_for="div.event__match", force=force)
    return parse_fixtures(html)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calendrier Flashscore.")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--out", help="écrire le JSON dans ce fichier")
    args = parser.parse_args()

    fixtures = load(args.force)
    if args.out:
        Path(args.out).write_text(json.dumps(fixtures, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"écrit : {args.out}")

    print(f"{len(fixtures)} rencontre(s) au calendrier\n")
    for f in fixtures:
        print(f"  {f['kickoff'] or '?':17} {f['home']:>18} - {f['away']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
