"""Statistiques relevées d'un match, via l'endpoint interne de Forebet.

    https://www.forebet.com/scripts/get_evs_n.php?gdt=1&mid=<match_id>&gmc=1

C'est la seule source trouvée qui donne possession et tirs sur la Division 1
koweïtienne (TheSportsDB et API-Football n'en ont pas — voir PROGRESS.md). Sans
`gmc=1` le même endpoint ne renvoie que la chronologie.

⚠️ Deux pièges, tous deux constatés sur de vraies réponses :

1. **Un zéro ne veut pas dire zéro.** La moitié des champs (`passes`, `fouls`,
   `tackles`, `saves`, `offsides`, `ball_safe`, `goal_attempts`) est servie à 0
   sur cette division parce que le fournisseur ne la couvre pas, pas parce que
   le match s'est joué sans une faute. On ne publie donc un champ que s'il est
   non nul pour au moins une des deux équipes.
2. **Les attaques sont incohérentes.** Sur Al Jazira - Sporty, les attaques
   dangereuses (94) dépassent les attaques totales (79). Le couple est conservé
   mais marqué `suspect`, et la console ne l'affiche pas dans ce cas.

    python fetch_stats.py 2486626 2486627 --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from browser import CdpBrowser

ROOT = Path(__file__).resolve().parent

ENDPOINT = "https://www.forebet.com/scripts/get_evs_n.php?gdt=1&mid={mid}&gmc=1"

# Toujours présentés, même à zéro : là, un zéro est une information.
CORE = ("possession", "shots", "shots_on", "shots_off", "corners",
        "yellow", "red", "goals")
# Publiés seulement s'ils sont renseignés (voir piège n° 1).
OPTIONAL = ("fouls", "offsides", "saves", "tackles", "passes", "passes_accuracy",
            "shots_blocked", "shots_inside", "shots_outside", "substitutions")

EVENT_LABELS = {
    "goal": "but",
    "owngoal": "csc",
    "penalty": "penalty",
    "missed_penalty": "penalty manqué",
    "yellowcard": "carton jaune",
    "redcard": "carton rouge",
    "yellowredcard": "second jaune",
    "substitution": "remplacement",
    "var": "VAR",
}


def _int(value):
    """Les compteurs arrivent tantôt en nombre, tantôt en chaîne."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def side_stats(entry: dict) -> dict:
    shots = entry.get("shots") or {}
    passes = entry.get("passes") or {}
    attacks = entry.get("attacks") or {}
    return {
        "possession": _int(entry.get("possessiontime")),
        "shots": _int(shots.get("total")),
        "shots_on": _int(shots.get("ongoal")),
        "shots_off": _int(shots.get("offgoal")),
        "shots_blocked": _int(shots.get("blocked")),
        "shots_inside": _int(shots.get("insidebox")),
        "shots_outside": _int(shots.get("outsidebox")),
        "corners": _int(entry.get("corners")),
        "yellow": _int(entry.get("yellowcards")),
        "red": _int(entry.get("redcards")),
        "goals": _int(entry.get("goals")),
        "fouls": _int(entry.get("fouls")),
        "offsides": _int(entry.get("offsides")),
        "saves": _int(entry.get("saves")),
        "tackles": _int(entry.get("tackles")),
        "passes": _int(passes.get("total")),
        "passes_accuracy": _int(passes.get("percentage")),
        "substitutions": _int(entry.get("substitutions")),
        "attacks": _int(attacks.get("attacks")),
        "dangerous_attacks": _int(attacks.get("dangerous_attacks")),
    }


def prune(home: dict, away: dict) -> list[str]:
    """Retire des deux camps les champs que la source ne couvre pas.

    Un champ optionnel nul (ou absent) des *deux* côtés est un trou de
    couverture, pas un relevé. On le supprime plutôt que d'afficher « 0 faute ».
    Renvoie la liste des champs effectivement renseignés.
    """
    kept = list(CORE)
    for field in OPTIONAL:
        if (home.get(field) or 0) or (away.get(field) or 0):
            kept.append(field)
        else:
            home.pop(field, None)
            away.pop(field, None)
    return kept


def normalise(raw: dict) -> dict | None:
    """Transforme la réponse brute en un bloc `home` / `away` exploitable.

    Renvoie None si le match n'est pas couvert : l'endpoint répond alors 200
    avec des listes vides plutôt qu'une erreur.
    """
    if not isinstance(raw, dict):
        return None
    header = raw.get("match") or {}
    rows = raw.get("stats") or []

    # L'appariement passe par `team_id` : l'ordre du tableau `stats` n'est pas
    # garanti, et rien d'autre n'identifie le camp.
    host_id, guest_id = str(header.get("host_id") or ""), str(header.get("guest_id") or "")
    by_team = {str(r.get("team_id")): r for r in rows if r.get("team_id") is not None}
    home_raw, away_raw = by_team.get(host_id), by_team.get(guest_id)
    if home_raw is None and away_raw is None and len(rows) == 2:
        home_raw, away_raw = rows  # identifiants absents : on retombe sur l'ordre
    if home_raw is None or away_raw is None:
        return None

    home, away = side_stats(home_raw), side_stats(away_raw)
    if not any((home.get(f) or 0) or (away.get(f) or 0)
               for f in ("possession", "shots", "corners")):
        return None  # match listé mais sans relevé

    fields = prune(home, away)

    # Attaques : gardées à part, parce qu'on ne peut pas leur faire confiance
    # aveuglément (voir l'en-tête du module).
    attacks = {
        "home": {"total": home.pop("attacks", None),
                 "dangerous": home.pop("dangerous_attacks", None)},
        "away": {"total": away.pop("attacks", None),
                 "dangerous": away.pop("dangerous_attacks", None)},
    }
    attacks["suspect"] = any(
        (attacks[s]["dangerous"] or 0) > (attacks[s]["total"] or 0)
        for s in ("home", "away")
    )
    if not any(attacks[s]["total"] for s in ("home", "away")):
        attacks = None

    return {
        "source": "forebet/get_evs_n",
        "fields": fields,
        "home": home,
        "away": away,
        "attacks": attacks,
        "timeline": timeline(raw.get("events") or [], host_id, guest_id),
        "venue": header.get("venue") or None,
        "venue_capacity": _int(header.get("venue_capacity")),
        "referee": header.get("referee") or None,
        "half_time": header.get("ht_score") if header.get("ht_score") not in ("-", "") else None,
        "full_time": header.get("ft_score") if header.get("ft_score") not in ("-", "") else None,
        # Couleurs officielles quand elles sont là — elles ne le sont pas
        # toujours. Les écussons (crests.py) restent la source principale.
        "colors": {"home": header.get("host_color") or None,
                   "away": header.get("guest_color") or None},
    }


def timeline(events: list, host_id: str, guest_id: str) -> list[dict]:
    """Chronologie des faits de jeu.

    Les noms de joueurs sont toujours `null` sur cette division : on ne les
    reprend pas plutôt que d'afficher des tirets.
    """
    out = []
    for event in events:
        team = str(event.get("team_id") or "")
        kind = event.get("type") or ""
        minute = _int(event.get("minute"))
        if minute is None:
            continue
        out.append({
            "minute": minute,
            "extra": _int(event.get("extra_minute")),
            "type": kind,
            "label": EVENT_LABELS.get(kind, kind.replace("_", " ")),
            "side": "home" if team == host_id else ("away" if team == guest_id else None),
            "player": event.get("player_name") or None,
        })
    out.sort(key=lambda e: (e["minute"], e["extra"] or 0))
    return out


def fetch(match_ids, browser: CdpBrowser | None = None, force: bool = False,
          max_age_hours: float = 12.0) -> dict:
    """{match_id: bloc de stats} — les matchs non couverts sont simplement absents."""
    owned = browser is None
    browser = browser or CdpBrowser()
    out = {}
    try:
        for mid in match_ids:
            if mid is None:
                continue
            try:
                raw = browser.get_json(ENDPOINT.format(mid=mid), force=force,
                                       max_age_hours=max_age_hours)
            except Exception as exc:
                print(f"  stats {mid} : indisponible ({exc})", file=sys.stderr)
                continue
            # `raw` à None = corps vide : match à venir, ou pas de relevé. Ce
            # n'est pas un incident, on n'en dit rien.
            block = normalise(raw) if raw is not None else None
            if block is not None:
                out[int(mid)] = block
    finally:
        if owned:
            browser.close()
    return out


def print_summary(stats: dict) -> None:
    for mid, block in stats.items():
        print(f"\n#{mid}  {block['venue'] or 'stade inconnu'}"
              f"  mi-temps {block['half_time'] or '?'}"
              f"  final {block['full_time'] or '?'}")
        for field in block["fields"]:
            print(f"  {field:16} {block['home'].get(field)!s:>6} | "
                  f"{block['away'].get(field)}")
        if block["attacks"]:
            note = "  (incohérent, non publié)" if block["attacks"]["suspect"] else ""
            print(f"  attaques         {block['attacks']['home']['total']!s:>6} | "
                  f"{block['attacks']['away']['total']}{note}")
        if block["timeline"]:
            print("  " + ", ".join(f"{e['minute']}' {e['label']} ({e['side']})"
                                   for e in block["timeline"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Statistiques relevées d'un match Forebet.")
    parser.add_argument("match_ids", nargs="+", type=int)
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--max-age", type=float, default=12.0,
                        help="âge maximum du cache en heures (défaut : 12)")
    parser.add_argument("--out", help="écrire le JSON dans ce fichier")
    parser.add_argument("--summary", action="store_true",
                        help="résumé lisible au lieu du JSON")
    args = parser.parse_args()

    stats = fetch(args.match_ids, force=args.force, max_age_hours=args.max_age)
    if not stats:
        print("aucune statistique : ces matchs ne sont pas couverts.", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"écrit : {args.out}")
    if args.summary:
        print_summary(stats)
    elif not args.out:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
