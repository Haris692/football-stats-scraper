"""Qui reçoit : arbitrage entre Forebet, Flashscore et Sofascore.

Le problème, constaté le 10/08/2026 et tranché le 11 : les sources ne
désignent pas le même hôte. Elles s'accordent pourtant sur le **résultat** et
sur les **chiffres par équipe** — seule l'étiquette diverge. Corriger, c'est
donc permuter le couple (hôte, visiteur) *avec* ses colonnes, jamais déplacer
un chiffre tout seul.

**Flashscore fait autorité**, sur la foi du relevé suivant :

- sur les 70 rencontres de la saison, Sofascore l'inverse **61 fois** — la
  divergence est structurelle, pas un accident d'appariement ;
- sur les 10 rencontres que Forebet étiquette lui-même (les autres viennent
  déjà de Flashscore, les confronter serait circulaire), Forebet suit
  Flashscore **8 fois sur 10** et Sofascore **0 fois sur 10**.

Flashscore n'est donc jamais minoritaire, et deux sources indépendantes
s'opposent à Sofascore. Reste une réserve qu'aucune donnée ne lève : si
Forebet et Flashscore partagent un même flux en amont, leur accord ne vaut pas
double. Il faudrait la fédération koweïtienne pour en sortir.

⚠️ **L'appariement se fait sur la date autant que sur la paire d'équipes.**
Un aller-retour fournit les deux ordres, donc chercher la seule paire trouve
toujours une correspondance et conclut à tort à l'accord — c'est ce piège qui
a fait croire un temps à un accord de 66 sur 70.

⚠️ Ce qui n'est **pas** rattrapé : les bilans « à domicile » et « à
l'extérieur » de la saison, que Forebet calcule lui-même à partir de sa propre
idée de qui reçoit. Une permutation d'étiquette ne les recalcule pas.
"""

from __future__ import annotations

import re

from fetch_flashscore import load as load_calendar, load_results, normalise

# Une divergence de translittération, pas de préfixe : `normalise()` ne peut
# rien pour elle. Même alias que `fetch_squads`, dupliqué plutôt qu'importé
# pour ne pas faire dépendre l'arbitrage de la collecte des effectifs.
ALIASES = {"jazeerakuwait": "jazira"}

# Les couples de clés à permuter ensemble. Tout ce qui décrit un camp porte
# l'un de ces préfixes ; les inventorier explicitement évite de permuter par
# erreur les rencontres *citées* dans `result_blocks`, qui ont leur propre
# hôte et ne sont pas concernées par le verdict de celle-ci.
PAIRED_KEYS = (
    ("home", "away"),
    ("home_alt", "away_alt"),
    ("home_ink", "away_ink"),
    ("home_true", "away_true"),
)


def key(name: str) -> str:
    """Clé de rapprochement d'un nom de club, alias compris."""
    k = normalise(name)
    return ALIASES.get(k, k)


def _day(kickoff: str | None) -> str:
    return (kickoff or "").split(" ")[0]


def _swap_keys(target: dict) -> None:
    """Échange les deux camps, sans jamais inventer de clé.

    Une paire n'est pas toujours complète — `palette` porte `away_true` sans
    `home_true`. Écrire les deux à l'aveugle créerait un `home_true: None` qui
    n'existait pas, et ferait passer une absence pour une valeur connue.
    """
    for left, right in PAIRED_KEYS:
        if left in target and right in target:
            target[left], target[right] = target[right], target[left]
        elif left in target:
            target[right] = target.pop(left)
        elif right in target:
            target[left] = target.pop(right)


def _swap_score(score: str | None) -> str | None:
    """« 0 - 2 » devient « 2 - 0 », séparateur conservé."""
    found = re.match(r"^\s*(\d+)(\s*[-–]\s*)(\d+)\s*$", score or "")
    return f"{found[3]}{found[2]}{found[1]}" if found else score


def swap_fixture(fixture: dict) -> None:
    _swap_keys(fixture)
    fixture["score"] = _swap_score(fixture.get("score"))


def swap_match(match: dict) -> None:
    """Permute une fiche complète.

    `slug` et `url` sont laissés tels quels : ce sont les identifiants Forebet,
    et c'est par eux qu'on retrouve la page en cache.

    `palette` et `squads` sont permutés par acquit de conscience : dans le
    pipeline normal, `make_payload()` les recalcule *après* l'arbitrage, à
    partir de noms déjà corrigés. Les traiter ici rend la fonction juste aussi
    sur une charge utile déjà construite.
    """
    _swap_keys(match)

    stats = match.get("stats")
    if isinstance(stats, dict):
        _swap_keys(stats)
        for row in (stats.get("others") or {}).values():
            if isinstance(row, dict):
                _swap_keys(row)

    for section in ("palette", "squads"):
        if isinstance(match.get(section), dict):
            _swap_keys(match[section])

    live = match.get("match_stats")
    if isinstance(live, dict):
        _swap_keys(live)
        for section in ("attacks", "colors"):
            if isinstance(live.get(section), dict):
                _swap_keys(live[section])
        for field in ("half_time", "full_time"):
            if live.get(field):
                live[field] = _swap_score(live[field])


def verdicts(results: list[dict]) -> dict:
    """L'hôte selon Flashscore, indexé par (jour, paire d'équipes)."""
    table = {}
    for row in results:
        day = _day(row.get("kickoff"))
        if not day:
            continue
        home, away = key(row["home"]), key(row["away"])
        table[(day, frozenset((home, away)))] = home
    return table


def arbitrate(fixtures: list[dict], matches: list[dict],
              results: list[dict]) -> list[str]:
    """Aligne l'hôte de chaque rencontre sur le verdict de Flashscore.

    Ne touche qu'aux rencontres que Flashscore connaît **au même jour** ; les
    autres gardent l'étiquette de Forebet, faute d'arbitre. Renvoie la liste
    des permutations, pour que le build en rende compte.
    """
    table = verdicts(results)
    by_id = {m.get("match_id"): m for m in matches if m.get("match_id")}
    swapped = []

    for fixture in fixtures:
        home, away = key(fixture.get("home", "")), key(fixture.get("away", ""))
        if not home or not away:
            continue
        host = table.get((_day(fixture.get("kickoff")), frozenset((home, away))))
        if host is None:
            fixture["host_source"] = None
            continue

        fixture["host_source"] = "flashscore"
        if host == home:
            continue

        before = f"{fixture['home']} - {fixture['away']}"
        swap_fixture(fixture)
        detail = by_id.get(fixture.get("match_id"))
        if detail is not None:
            swap_match(detail)
            detail["host_swapped"] = True
        fixture["host_swapped"] = True
        swapped.append(f"{_day(fixture.get('kickoff'))} {before}"
                       f"  ->  {fixture['home']} - {fixture['away']}")

    return swapped


def load_verdict_source(force: bool = False, browser=None) -> list[dict]:
    """Les deux pages Flashscore : résultats **et** calendrier.

    Les rencontres à venir ne sont pas sur la page « résultats » ; sans le
    calendrier, elles resteraient sans arbitre alors que Forebet en étiquette
    déjà quelques-unes de son côté (celles de la journée en cours).

    Les rencontres venues de Flashscore par `merge_calendar` sont bien sûr
    d'accord avec elle : l'arbitrage est alors un contrôle à vide, ce qui est
    exactement ce qu'on veut — il ne doit rien permuter.
    """
    return load_results(force=force, browser=browser) + load_calendar(
        force=force, browser=browser)
