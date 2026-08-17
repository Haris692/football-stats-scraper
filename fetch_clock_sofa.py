"""L'horloge de repli, via Sofascore, pour les matchs que Forebet ne suit pas.

`fetch_clock.py` interroge `forebet.com/gsv/`, qui ne rend que les rencontres
que Forebet suit à cet instant. Sur cette division, c'est environ une sur deux —
le même trou de couverture que pour les statistiques. Relevé le 17/08/2026 à
19h36, journée 20 : Forebet horlogeait deux des quatre rencontres, Sofascore les
quatre. D'où ce second relevé, appelé **seulement pour ce qui manque**.

⚠️ **On n'y prend que l'horloge.** Sofascore inverse domicile et extérieur sur
61 des 70 rencontres de la saison (voir `hosts.py`) : son étiquette d'hôte ne
vaut rien ici. Le rapprochement se fait donc sur la **paire** d'équipes et sur
le **jour**, jamais sur « qui reçoit », et le score est réorienté sur notre
propre hôte avant d'être rendu — permuté avec sa mi-temps, jamais tout seul.

⚠️ **La minute est calculée, pas lue.** La source ne publie pas un compteur :
elle donne l'instant où la période en cours a commencé, et c'est l'horloge du
poste qui fait la soustraction. Une horloge de poste déréglée décale donc la
minute — d'où le garde-fou de `minute_of()`, qui préfère ne rien dire plutôt que
d'annoncer une 210e minute.

⚠️ **Une journée entière en une requête.** Le point d'entrée rend toutes les
rencontres de la journée : suivre quatre matchs coûte une requête, comme d'en
suivre un. La journée est lue dans `data/events.json`, déjà collecté chaque
matin, pour ne pas payer deux requêtes de plus (saison, journée courante) à
chaque relevé.

    python fetch_clock_sofa.py            # les rencontres du jour, lisible
    python fetch_clock_sofa.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from browser import CdpBrowser
from fetch_events import current_round, round_events
from fetch_squads import key, season_id

ROOT = Path(__file__).resolve().parent
EVENTS = ROOT / "data" / "events.json"

# Ce que Sofascore écrit dans `status.type`, traduit dans le vocabulaire de
# `fetch_clock` — c'est lui que la page connaît (`CLOCK_WORDS`, dans
# `pieces.js`), et les deux sources doivent parler pareil.
STATUS_BY_TYPE = {
    "finished": "termine",
    "postponed": "reporte",
    "canceled": "annule",
    "cancelled": "annule",
    "suspended": "suspendu",
    "interrupted": "suspendu",
    "willcontinue": "retarde",
    "delayed": "retarde",
}
# La mi-temps et les tirs au but sont des `inprogress` : seul le code les
# distingue. 31 « Halftime », 32 « Awaiting extra time », 50 « Penalties ».
HALFTIME_CODES = {31, 32}
SHOOTOUT_CODES = {50}

# Au-delà de ça après la fin réglementaire de la période, on ne croit plus le
# repère de temps : la source laisse traîner `currentPeriodStartTimestamp` sur
# une rencontre dont elle a perdu le fil, et la minute filerait toute seule.
MAX_ADDED = 30 * 60


def _day(value: str | None) -> str:
    """Le jour d'un `kickoff_iso`, seule partie qui sert au rapprochement."""
    return (value or "").split("T")[0]


def _pair(home: str | None, away: str | None) -> frozenset:
    return frozenset((key(home or ""), key(away or "")))


def status_of(status: dict) -> str | None:
    """Le statut dans le vocabulaire du projet, ou `None` s'il ne dit rien.

    `None` couvre « pas commencé » et les types inconnus : dans les deux cas,
    l'appelant se passe d'horloge — il ne la fabrique pas.
    """
    code = status.get("code")
    if code in HALFTIME_CODES:
        return "mi_temps"
    if code in SHOOTOUT_CODES:
        return "tirs_au_but"
    kind = (status.get("type") or "").lower()
    if kind in STATUS_BY_TYPE:
        return STATUS_BY_TYPE[kind]
    return "en_cours" if kind == "inprogress" else None


def minute_of(block: dict, now_ts: float) -> tuple[int | None, str | None]:
    """(minute, temps additionnel) à partir du début de la période en cours.

    `initial` : ce qui était déjà écoulé au coup d'envoi de cette période — 0 en
    première mi-temps, 2700 s en seconde. `max` : la fin réglementaire de la
    période. Au-delà, la minute se fige et le surplus devient le temps
    additionnel, comme sur un tableau d'affichage.
    """
    start = block.get("currentPeriodStartTimestamp")
    if not start:
        return None, None
    elapsed = int(now_ts) - int(start) + int(block.get("initial") or 0)
    if elapsed < 0:
        return None, None

    limit = int(block.get("max") or 0)
    # La minute affichée est celle qu'on est en train de jouer : 0 s écoulée,
    # c'est la 1re minute. C'est le compte de la source elle-même.
    minute = elapsed // 60 + 1
    if not limit:
        return minute, None
    if elapsed > limit + MAX_ADDED:
        return None, None
    if minute > limit // 60:
        return limit // 60, str(minute - limit // 60)
    return minute, None


def normalise(row: dict, now_ts: float, inverted: bool = False) -> dict | None:
    """Un bloc d'horloge de la même forme que celui de `fetch_clock`.

    `inverted` : la source étiquette l'hôte à l'envers du nôtre. Les deux scores
    sont alors permutés ensemble, mi-temps comprise.
    """
    state = status_of(row.get("status") or {})
    if state is None:
        return None

    minute = added = None
    if state == "en_cours":
        minute, added = minute_of(row.get("time") or {}, now_ts)
        # En cours mais sans repère de temps exploitable : le marqueur « live »
        # dit déjà que ça se joue, une horloge muette n'ajouterait rien.
        if minute is None:
            return None

    home, away = row.get("homeScore") or {}, row.get("awayScore") or {}
    score = [home.get("current"), away.get("current")]
    half = [home.get("period1"), away.get("period1")]
    if inverted:
        score.reverse()
        half.reverse()

    return {
        "source": "sofascore",
        "minute": minute,
        # Même convention que `fetch_clock` : le libellé brut de la source
        # quand elle en a un, la minute sinon.
        "label": str(minute) if minute is not None
                 else ((row.get("status") or {}).get("description") or None),
        "added": added,
        "running": state == "en_cours",
        "status": state,
        "league_id": None,
        "score": None if None in score else score,
        "half_time": None if None in half else half,
    }


def rounds_for(fixtures: list[dict]) -> set[int]:
    """Les journées Sofascore où vivent ces rencontres, d'après `events.json`.

    Évite deux requêtes (la saison, la journée courante) à chaque relevé. Le
    fichier est réécrit chaque matin ; s'il manque ou ne connaît pas encore la
    rencontre, `fetch()` retombe sur la journée courante demandée à la source.
    """
    try:
        blob = json.loads(EVENTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    wanted = {(_day(f.get("kickoff_iso")), _pair(f.get("home"), f.get("away")))
              for f in fixtures}
    numbers = set()
    for event in blob.get("events") or []:
        seen = (_day(event.get("kickoff_iso")),
                frozenset((event.get("home_key"), event.get("away_key"))))
        if seen in wanted and event.get("round"):
            numbers.add(int(event["round"]))
    return numbers


def fetch(fixtures: list[dict], browser: CdpBrowser | None = None,
          force: bool = True, now: datetime | None = None) -> dict:
    """{match_id: bloc d'horloge} pour celles de ces rencontres qui se jouent.

    `fixtures` porte nos rencontres à nous — `match_id`, `kickoff_iso`, `home`,
    `away` — et c'est par elles qu'on retrouve les leurs. Une rencontre absente
    du relevé, pas commencée ou d'un statut inconnu n'a simplement pas de clé
    dans le résultat.
    """
    fixtures = [f for f in fixtures if f.get("match_id")]
    if not fixtures:
        return {}
    now_ts = (now or datetime.now()).timestamp()

    owned = browser is None
    browser = browser or CdpBrowser()
    try:
        sid, _ = season_id(browser, False)
        numbers = rounds_for(fixtures)
        if not numbers:
            last = current_round(browser, sid, False) or 0
            # La journée suivante aussi : à cheval sur deux journées, la source
            # peut avoir déjà basculé.
            numbers = {n for n in (last, last + 1) if n}
        rows = []
        for number in sorted(numbers):
            rows += round_events(browser, sid, number, force=force, max_age_hours=0)
    except Exception as exc:
        # Une horloge de repli qui tombe ne doit rien emporter : l'appelant a
        # déjà ses statistiques, et l'autre source son horloge à elle.
        print(f"  horloge (repli) : indisponible ({exc})", file=sys.stderr, flush=True)
        return {}
    finally:
        if owned:
            browser.close()

    index = {(_day(f.get("kickoff_iso")), _pair(f.get("home"), f.get("away"))): f
             for f in fixtures}
    out = {}
    for row in rows:
        home = (row.get("homeTeam") or {}).get("name")
        away = (row.get("awayTeam") or {}).get("name")
        stamp = row.get("startTimestamp")
        if not stamp:
            continue
        day = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
        fixture = index.get((day, _pair(home, away)))
        if fixture is None:
            continue
        block = normalise(row, now_ts,
                          inverted=key(home or "") != key(fixture.get("home") or ""))
        if block is not None:
            out[int(fixture["match_id"])] = block
    return out


def _today_fixtures() -> list[dict]:
    """Les rencontres du jour selon nos propres données — pour la ligne de
    commande seulement ; `serve.py` passe les siennes."""
    for name in ("console.data.json", "site.json"):
        path = ROOT / "data" / name if name == "site.json" else ROOT / name
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        today = datetime.now().strftime("%Y-%m-%d")
        rows = [f for f in blob.get("fixtures") or []
                if _day(f.get("kickoff_iso")) == today]
        if rows:
            return rows
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="L'horloge des matchs du jour, vue par Sofascore.")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args()

    fixtures = _today_fixtures()
    if not fixtures:
        print("aucune rencontre aujourd'hui dans nos données")
        return 0
    clocks = fetch(fixtures)

    if args.json:
        print(json.dumps(clocks, ensure_ascii=False, indent=2))
        return 0

    print(f"{len(clocks)} rencontre(s) horlogée(s) sur {len(fixtures)}")
    for fixture in fixtures:
        block = clocks.get(int(fixture["match_id"]))
        horloge = "—"
        if block:
            horloge = block["label"] or "—"
            if block["added"]:
                horloge += f"+{block['added']}"
        score = f"{block['score'][0]}-{block['score'][1]}" if block and block["score"] else "?-?"
        print(f"  #{fixture['match_id']}  {fixture.get('home', ''):>14} - "
              f"{fixture.get('away', ''):14}  {horloge:>8}  {score:>5}  "
              f"{block['status'] if block else 'pas suivi'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
