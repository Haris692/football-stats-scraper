"""Les rencontres vues par Sofascore : calendrier, chronologie, entraîneurs.

Le partage des rôles, après le sondage du 11/08/2026 :

- **Forebet garde les chiffres** — possession, tirs, corners. Sofascore a bien
  un endpoint `event/{id}/statistics`, mais sur cette division il ne renvoie
  qu'une ligne, « Red cards ». Ne pas espérer mieux de ce côté.
- **Sofascore apporte ce que Forebet laisse vide** : les **buteurs nommés et
  minutés**, les cartons minutés, les deux entraîneurs du soir, et un
  calendrier structuré en journées avec la journée courante.

`fetch_squads.py` couvre les gens (effectifs, buteurs de la saison) ; ce
module-ci couvre les matchs. Les deux tapent la même source, d'où les mêmes
précautions : passer par `browser.get_json()`, qui exécute le `fetch()` dans
une page sofascore.com — le 403 conclu ailleurs ne vaut que pour `curl`.

⚠️ **Sofascore n'oriente pas domicile/extérieur comme les autres.** Il inverse
Flashscore sur 61 des 70 rencontres de la saison (voir `hosts.py`). Tout ce que
ce module renvoie est donc étiqueté dans **son** orientation, et
`build_console.py` le réoriente en l'accrochant. Ne jamais afficher un `side`
sorti d'ici sans l'avoir fait passer par là.

    python fetch_events.py --summary
    python fetch_events.py --round 18 --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from browser import CdpBrowser
from fetch_squads import ALIASES, BASE, HOST_PAGE, TOURNAMENT, key, season_id

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "events.json"

# Une rencontre terminée ne bouge plus : ses buts sont marqués, ses cartons
# distribués. Son relevé peut donc rester en cache très longtemps — c'est ce
# qui rend le rafraîchissement quotidien bon marché, puisqu'il ne redemande
# que les journées récentes.
AGE_FINISHED = 24 * 30
AGE_OPEN = 0.5

# Statuts Sofascore d'une rencontre jouée jusqu'au bout.
FINISHED = {"finished", "AP", "AET"}


def _maybe(browser: CdpBrowser, url: str, **kwargs):
    """Un GET dont l'absence est une réponse.

    Tous les compléments ne sont pas renseignés partout : une rencontre
    ancienne peut n'avoir ni banc ni chronologie, et la source répond alors
    404. Ce n'est pas une panne, c'est un trou de couverture — il ne doit pas
    interrompre la collecte des 69 autres.
    """
    try:
        return browser.get_json(url, **kwargs)
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def _kickoff(timestamp: int | None) -> tuple[str | None, str | None]:
    if not timestamp:
        return None, None
    moment = datetime.fromtimestamp(timestamp)
    return moment.strftime("%d/%m/%Y %H:%M"), moment.strftime("%Y-%m-%dT%H:%M")


def current_round(browser: CdpBrowser, sid: int, force: bool) -> int | None:
    data = browser.get_json(
        f"{BASE}/api/v1/unique-tournament/{TOURNAMENT}/season/{sid}/rounds",
        force=force, referer=HOST_PAGE)
    return ((data or {}).get("currentRound") or {}).get("round")


def round_events(browser: CdpBrowser, sid: int, number: int,
                 force: bool, max_age_hours: float) -> list[dict]:
    data = _maybe(browser,
                  f"{BASE}/api/v1/unique-tournament/{TOURNAMENT}/season/{sid}"
                  f"/events/round/{number}",
                  force=force, referer=HOST_PAGE, max_age_hours=max_age_hours)
    return (data or {}).get("events") or []


def timeline(browser: CdpBrowser, event_id: int, force: bool,
             max_age_hours: float) -> list[dict]:
    """Buts et cartons, dans l'ordre du match.

    Les repères de période (« HT », « FT ») sont écartés : ils ne disent rien
    que le score ne dise déjà. Un but sans joueur nommé est **conservé** — la
    source en a quelques-uns, et le passer sous silence ferait mentir le
    décompte affiché.
    """
    data = _maybe(browser, f"{BASE}/api/v1/event/{event_id}/incidents",
                  force=force, referer=HOST_PAGE, max_age_hours=max_age_hours)
    out = []
    for item in reversed((data or {}).get("incidents") or []):
        kind = item.get("incidentType")
        if kind not in ("goal", "card"):
            continue
        added = item.get("addedTime")
        out.append({
            "type": kind,
            # « regular », « penalty », « ownGoal » pour un but ; « yellow »,
            # « red », « yellowRed » pour un carton.
            "class": item.get("incidentClass"),
            "minute": item.get("time"),
            # 999 est la valeur que la source donne quand il n'y a pas de temps
            # additionnel : c'est un marqueur, pas des minutes.
            "added": added if added and added != 999 else None,
            "player": (item.get("player") or {}).get("name"),
            "side": "home" if item.get("isHome") else "away",
            "score": (f"{item['homeScore']}-{item['awayScore']}"
                      if item.get("homeScore") is not None else None),
        })
    return out


def managers(browser: CdpBrowser, event_id: int, force: bool,
             max_age_hours: float) -> dict:
    """Les deux entraîneurs du soir.

    Différent de l'entraîneur relevé par `fetch_squads` : celui-ci est celui du
    club *aujourd'hui*, celui-là celui qui était sur le banc ce jour-là.
    """
    data = _maybe(browser, f"{BASE}/api/v1/event/{event_id}/managers",
                  force=force, referer=HOST_PAGE,
                  max_age_hours=max_age_hours) or {}
    return {
        "home": (data.get("homeManager") or {}).get("name"),
        "away": (data.get("awayManager") or {}).get("name"),
    }


def collect(force: bool = False, only_round: int | None = None,
            browser: CdpBrowser | None = None) -> dict:
    """La saison entière, chronologies comprises.

    `force` ne s'applique **pas** aux rencontres terminées : leur relevé ne
    peut plus changer, et les redemander toutes ferait de chaque collecte
    ~150 requêtes pour rien. C'est le même compromis que `attach_stats()`.
    """
    own = browser is None
    browser = browser or CdpBrowser()
    try:
        sid, year = season_id(browser, force)
        last = current_round(browser, sid, force)
        print(f"saison {year} (id {sid}), journée courante {last}")

        numbers = [only_round] if only_round else range(1, (last or 0) + 4)
        events = []
        for number in numbers:
            # Les journées passées sont figées ; celle en cours et les
            # suivantes bougent (report, score, journée qui apparaît).
            fresh = last is None or number >= (last or 0)
            rows = round_events(browser, sid, number, force and fresh,
                                AGE_OPEN if fresh else AGE_FINISHED)
            for row in rows:
                kickoff, iso = _kickoff(row.get("startTimestamp"))
                done = (row.get("status") or {}).get("type") in FINISHED
                events.append({
                    "sofascore_id": row.get("id"),
                    "round": number,
                    "kickoff": kickoff,
                    "kickoff_iso": iso,
                    "home": (row.get("homeTeam") or {}).get("name"),
                    "away": (row.get("awayTeam") or {}).get("name"),
                    "home_key": key((row.get("homeTeam") or {}).get("name") or ""),
                    "away_key": key((row.get("awayTeam") or {}).get("name") or ""),
                    "home_score": (row.get("homeScore") or {}).get("current"),
                    "away_score": (row.get("awayScore") or {}).get("current"),
                    "finished": done,
                })

        done = [e for e in events if e["finished"]]
        print(f"{len(events)} rencontre(s), dont {len(done)} jouée(s)")
        for event in done:
            age = AGE_FINISHED
            event["timeline"] = timeline(browser, event["sofascore_id"],
                                         force=False, max_age_hours=age)
            event["managers"] = managers(browser, event["sofascore_id"],
                                         force=False, max_age_hours=age)

        goals = sum(len([i for i in e.get("timeline") or []
                         if i["type"] == "goal"]) for e in done)
        named = sum(len([i for i in e.get("timeline") or []
                         if i["type"] == "goal" and i["player"]]) for e in done)
        print(f"{goals} but(s) datés, dont {named} avec un buteur nommé")

        return {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "source": "sofascore",
            "season": sid,
            "season_year": year,
            "current_round": last,
            "events": events,
        }
    finally:
        if own:
            browser.close()


def load() -> dict:
    """Le dernier relevé sur disque, ou un squelette vide."""
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"events": [], "current_round": None}


def for_match(store: dict, home: str, away: str, day: str | None) -> dict | None:
    """La rencontre correspondant à une affiche, appariée sur la date.

    ⚠️ **Le jour fait partie de la clé.** Un aller-retour fournit les deux
    ordres de la même paire ; chercher sur la seule paire trouverait toujours
    quelque chose, et rendrait le verdict de l'aller sur le retour. C'est
    exactement le piège décrit dans `hosts.py`.
    """
    pair = {key(home or ""), key(away or "")}
    for event in store.get("events") or []:
        if {event.get("home_key"), event.get("away_key")} != pair:
            continue
        if day and (event.get("kickoff") or "").split(" ")[0] != day:
            continue
        return event
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Rencontres Sofascore.")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--round", type=int, help="une seule journée")
    parser.add_argument("--summary", action="store_true",
                        help="afficher un résumé lisible")
    parser.add_argument("--out", default=str(OUTPUT), help="fichier de sortie")
    args = parser.parse_args()

    store = collect(args.force, args.round)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(store, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"écrit : {out}")

    if args.summary:
        for event in store["events"]:
            if not event["finished"]:
                continue
            print(f"\nJ{event['round']} {event['kickoff']}  {event['home']} "
                  f"{event['home_score']}-{event['away_score']} {event['away']}")
            managers = event.get("managers") or {}
            if managers.get("home") or managers.get("away"):
                print(f"    bancs : {managers.get('home') or '?'} / "
                      f"{managers.get('away') or '?'}")
            for item in event.get("timeline") or []:
                minute = f"{item['minute']}"
                if item["added"]:
                    minute += f"+{item['added']}"
                mark = "⚽" if item["type"] == "goal" else "▪"
                print(f"    {mark} {minute:>5}'  {item['side']:<5} "
                      f"{item['class']:<8} {item['player'] or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
