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
RESULTS_URL = "https://www.flashscore.com/football/kuwait/division-1/results/"


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


def resolve_year(day: int, month: int, now: datetime | None = None,
                 past: bool = False) -> int:
    """Flashscore n'affiche pas l'année (« 06.08. 19:45 »).

    On prend l'année courante, sauf si la date obtenue est loin dans le passé —
    auquel cas c'est un match de l'année suivante, cas du passage de décembre à
    janvier.

    `past=True` pour la page « résultats », où le raisonnement s'inverse : ces
    rencontres ont déjà eu lieu, donc une date loin *devant* est en réalité
    l'année précédente. Sans ça, un résultat de janvier lu en août se retrouvait
    daté de l'année suivante — vérifié le 11/08/2026, toute la première moitié
    de saison partait en 2027.
    """
    now = now or datetime.now()
    year = now.year
    try:
        candidate = datetime(year, month, day)
    except ValueError:
        return year
    if past:
        return year - 1 if (candidate - now).days > 120 else year
    if (now - candidate).days > 120:
        return year + 1
    return year


def parse_fixtures(html: str, past: bool = False) -> list[dict]:
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

        # Deux formes cohabitent sur la même page : « 06.08. 19:45 » pour les
        # rencontres récentes, et « 31.12.2025 » — datée, mais sans heure — pour
        # les plus anciennes. Ne lire que la première laissait 36 résultats sur
        # 70 sans date (constaté le 11/08/2026).
        kickoff = kickoff_iso = None
        recent = re.match(r"(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2})", when)
        dated = re.match(r"(\d{2})\.(\d{2})\.(\d{4})\s*$", when)
        if recent:
            day, month, hour, minute = (int(g) for g in recent.groups())
            year = resolve_year(day, month, past=past)
        elif dated:
            day, month, year = (int(g) for g in dated.groups())
            hour = minute = None
        if recent or dated:
            when_time = f" {hour:02d}:{minute:02d}" if hour is not None else ""
            kickoff = f"{day:02d}/{month:02d}/{year}{when_time}"
            kickoff_iso = (f"{year:04d}-{month:02d}-{day:02d}"
                           + (f"T{hour:02d}:{minute:02d}" if hour is not None else ""))

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


def _load_page(url: str, past: bool, force: bool, max_age_hours: float,
               browser: CdpBrowser | None = None) -> list[dict]:
    cached = cache_path(url)
    if cached.exists() and not force:
        age = (datetime.now().timestamp() - cached.stat().st_mtime) / 3600
        if age <= max_age_hours:
            return parse_fixtures(cached.read_text(encoding="utf-8", errors="replace"),
                                  past=past)

    # Le tableau est monté en JavaScript : on attend une vraie ligne.
    if browser is not None:
        return parse_fixtures(
            browser.get(url, wait_for="div.event__match", force=force), past=past)
    with CdpBrowser(max_age_hours=max_age_hours) as own:
        html = own.get(url, wait_for="div.event__match", force=force)
    return parse_fixtures(html, past=past)


def load(force: bool = False, max_age_hours: float = 6.0,
         browser: CdpBrowser | None = None) -> list[dict]:
    return _load_page(FIXTURES_URL, False, force, max_age_hours, browser)


def load_results(force: bool = False, max_age_hours: float = 6.0,
                 browser: CdpBrowser | None = None) -> list[dict]:
    """Les rencontres déjà jouées, avec leur hôte selon Flashscore.

    Cette page ne sert pas à prolonger le calendrier — Forebet connaît déjà les
    matchs joués. Elle sert d'**arbitre sur qui reçoit** : c'est la seule source
    qui, sur les rencontres passées, porte une étiquette indépendante de
    Forebet. Voir `hosts.py` et la section correspondante de PROGRESS.md.
    """
    return _load_page(RESULTS_URL, True, force, max_age_hours, browser)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calendrier Flashscore.")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--out", help="écrire le JSON dans ce fichier")
    parser.add_argument("--results", action="store_true",
                        help="les rencontres jouées, et non le calendrier")
    args = parser.parse_args()

    fixtures = load_results(args.force) if args.results else load(args.force)
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
