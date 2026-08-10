"""Parseur d'une page match Forebet.

Travaille sur du HTML déjà récupéré (voir `browser.py`) et le transforme en
dictionnaire. Aucun réseau n'est nécessaire si la page est en cache.

Les sélecteurs sont ceux relevés sur la page match du 05/08/2026 ; les points
qui ont demandé du reverse engineering sont commentés sur place.

    python parse_match.py https://www.forebet.com/fr/football/matches/al-shamiya-al-jazira-2487393
    python parse_match.py --file cache/xxx.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from browser import ForebetBrowser, cache_path

ROOT = Path(__file__).resolve().parent


# --- petits utilitaires ---------------------------------------------------

def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def _num(value: str):
    """« 3.20 » -> 3.2, « 28 » -> 28, « - » / « » -> None."""
    if value is None:
        return None
    value = value.strip().replace("%", "").replace("°", "").replace(",", ".")
    if value in ("", "-", "–", "?"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return None


def _first_num(text: str):
    """Récupère le dernier nombre d'un libellé du type « Marqués 15 »."""
    found = re.findall(r"-?\d+(?:[.,]\d+)?", text or "")
    return _num(found[-1]) if found else None


# --- en-tête du match -----------------------------------------------------

# Le slug n'est pas restreint à [a-z0-9-] : Forebet laisse passer parenthèses et
# accents (« sporty-sahel-(kuw)-2487392 », « ferencváros-w-paok-w-2487422 »).
# Une classe trop stricte faisait sortir `match_id` à None sur ces matchs-là.
MATCH_ID_RE = re.compile(r"/matches/(?P<slug>.+?)-(?P<id>\d+)(?:$|[/?#])")


def parse_crests(soup: BeautifulSoup) -> dict:
    """URL de l'écusson de chaque club.

    Forebet sert les logos sous `/images/icons/{id}.png` et met le nom du club
    dans l'attribut `alt` (« Al Shamiya - Logo »), ce qui donne la correspondance
    nom -> écusson sans avoir à deviner. Les images de `/images/fc/` sont des
    drapeaux de pays, pas des écussons : ne pas les confondre.
    """
    crests = {}
    for anchor in soup.select("a.team-logo"):
        img = anchor.select_one("img[src]")
        if img is None:
            continue
        alt = (img.get("alt") or "").strip()
        name = alt[:-len(" - Logo")].strip() if alt.endswith("- Logo") else alt
        if name:
            crests[name] = img["src"]
    return crests


def parse_header(soup: BeautifulSoup) -> dict:
    # La page match embarque sa propre ligne de résultat : le premier `.rcnt`
    # du tableau 1X2 décrit le match lui-même.
    row = soup.select_one("#m1x2_table .rcnt")
    link = row.select_one("a.tnmscn") if row else None
    href = link.get("href", "") if link else ""
    match = MATCH_ID_RE.search(href)

    return {
        "match_id": int(match.group("id")) if match else None,
        "slug": match.group("slug") if match else None,
        "url": f"https://www.forebet.com{href}" if href else None,
        "competition_tag": _txt(row.select_one(".shortTag")) if row else None,
        "home": _txt(row.select_one(".homeTeam")) if row else None,
        "away": _txt(row.select_one(".awayTeam")) if row else None,
        "kickoff": _txt(row.select_one(".date_bah")) if row else None,
    }


# --- pronostics -----------------------------------------------------------

# Les dix marchés vivent tous dans le HTML servi, y compris ceux dont l'onglet
# n'est pas actif à l'affichage : rien à cliquer, rien à recharger.
MARKETS = {
    "m1x2_table": ("1X2", ["1", "X", "2"]),
    "uo_table": ("Plus/Moins 2.5", ["moins", "plus"]),
    "ht_table": ("Mi-temps 1X2", ["1", "X", "2"]),
    "htft_table": ("Mi-temps / fin de match", None),
    "bts_table": ("Les deux équipes marquent", ["non", "oui"]),
    "dbc_table": ("Double chance", None),
    "ah_table": ("Handicap asiatique", None),
    "gscr_table": ("Score exact", None),
    "corner_table": ("Corners", ["moins", "plus"]),
    "card_table": ("Cartons", ["moins", "plus"]),
}


def parse_predictions(soup: BeautifulSoup) -> dict:
    out = {}
    for table_id, (label, prob_labels) in MARKETS.items():
        row = soup.select_one(f"#{table_id} .rcnt")
        if row is None:
            continue

        values = [_num(_txt(s)) for s in row.select(".fprc > span")]
        entry = {"label": label}

        if prob_labels and len(values) == len(prob_labels):
            entry["probabilities"] = dict(zip(prob_labels, values))
        elif len(values) == 1:
            # htft / dbc / ah n'affichent qu'un taux de confiance du pronostic.
            entry["probability"] = values[0]
        elif values:
            entry["probabilities_raw"] = values

        pick = _txt(row.select_one(".predict .forepr"))
        if pick:
            entry["pick"] = pick

        # `.ex_sc` existe en double (version mobile dans `.predict`) : on prend
        # la variante `tabonly`, la seule qui porte le score au format « 1 - 3 ».
        entry["expected_score"] = _txt(row.select_one("div.ex_sc.tabonly")) or None
        entry["average"] = _num(_txt(row.select_one("div.avg_sc.tabonly")))
        entry["confidence"] = _num(_txt(row.select_one(".prwth .wnums")))
        out[table_id.replace("_table", "")] = entry
    return out


# --- blocs de résultats (face à face, forme, domicile/extérieur) ----------

def parse_result_blocks(soup: BeautifulSoup) -> list[dict]:
    blocks = []
    for block in soup.select("div.st_scrblock"):
        title_el = block.find_previous(class_="mptlt")
        rows = []
        for row in block.select("div.st_row"):
            dates = [_txt(d) for d in row.select(".st_date div")]
            score = _txt(row.select_one(".st_rescnt .st_res"))
            home_goals = away_goals = None
            if "-" in score:
                left, _, right = score.partition("-")
                home_goals, away_goals = _num(left), _num(right)

            href = row.select_one("a.stat_link")
            match = MATCH_ID_RE.search(href.get("href", "")) if href else None

            # L'équipe sujet du bloc porte `active-team` ; c'est elle qui sert de
            # référence pour le bilan V/N/D calculé plus bas.
            home_is_subject = "active-team" in (row.select_one(".st_hteam") or {}).get("class", [])
            away_is_subject = "active-team" in (row.select_one(".st_ateam") or {}).get("class", [])

            rows.append({
                "date": "/".join(dates) if dates else None,
                "home": _txt(row.select_one(".st_hteam")),
                "away": _txt(row.select_one(".st_ateam")),
                "score": score or None,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "half_time": _txt(row.select_one(".st_htscr")).strip("()") or None,
                "competition": _txt(row.select_one(".st_ltag")) or None,
                "match_id": int(match.group("id")) if match else None,
                "subject_side": "home" if home_is_subject else ("away" if away_is_subject else None),
            })

        blocks.append({
            "title": _txt(title_el) or None,
            "matches": rows,
            # Forebet calcule les % V/N/D en JS : `.st_dstc` est vide dans le
            # HTML servi. On les recalcule depuis les lignes, c'est plus sûr.
            #
            # Le bloc intitulé « Les 6 derniers matchs » contient en réalité
            # toute la saison (16-17 lignes, coupes comprises) : c'est
            # l'affichage qui tronque à 6. D'où deux bilans distincts.
            "record": summarise(rows),
            "record_recent": summarise(rows[:6]),
            "form": form_string(rows[:6]),
        })
    return blocks


def form_string(rows: list[dict]) -> str:
    """Forme de l'équipe sujet, du plus récent au plus ancien (« VVNDV »)."""
    letters = []
    for row in rows:
        if row["home_goals"] is None or row["subject_side"] is None:
            continue
        own = row["home_goals"] if row["subject_side"] == "home" else row["away_goals"]
        other = row["away_goals"] if row["subject_side"] == "home" else row["home_goals"]
        letters.append("V" if own > other else ("N" if own == other else "D"))
    return "".join(letters)


def summarise(rows: list[dict]) -> dict:
    """Bilan V/N/D de l'équipe sujet sur les lignes fournies."""
    wins = draws = losses = 0
    scored = conceded = 0
    counted = 0
    for row in rows:
        if row["home_goals"] is None or row["away_goals"] is None:
            continue
        side = row["subject_side"]
        if side is None:
            continue
        counted += 1
        own = row["home_goals"] if side == "home" else row["away_goals"]
        other = row["away_goals"] if side == "home" else row["home_goals"]
        scored += own
        conceded += other
        if own > other:
            wins += 1
        elif own == other:
            draws += 1
        else:
            losses += 1
    return {
        "played": counted,
        "wins": wins, "draws": draws, "losses": losses,
        "goals_for": scored, "goals_against": conceded,
    }


# --- classement -----------------------------------------------------------

def parse_standings(soup: BeautifulSoup) -> list[dict]:
    # Deux tables `#standings` : la première est celle de la compétition en cours.
    table = soup.select_one("table#standings")
    if table is None:
        return []

    standings = []
    for tr in table.select("tr"):
        cells = [_txt(c) for c in tr.select("td, th")]
        # Les deux premières lignes sont un titre vide puis l'en-tête.
        if len(cells) < 10 or _num(cells[0]) is None:
            continue
        standings.append({
            "rank": _num(cells[0]),
            "team": cells[1],
            "points": _num(cells[2]),
            "played": _num(cells[3]),
            "wins": _num(cells[4]),
            "draws": _num(cells[5]),
            "losses": _num(cells[6]),
            "goals_for": _num(cells[7]),
            "goals_against": _num(cells[8]),
            "goal_diff": _num(cells[9]),
        })
    return standings


# --- statistiques complètes ----------------------------------------------

def parse_stats(soup: BeautifulSoup) -> dict:
    stats: dict = {"home": {}, "away": {}}

    goals = [_first_num(_txt(e)) for e in soup.select(".os_goals_section1_child")]
    if len(goals) == 8:
        stats["home"]["goals"] = {
            "scored": goals[0], "scored_avg": goals[1],
            "conceded": goals[2], "conceded_avg": goals[3],
        }
        stats["away"]["goals"] = {
            "scored": goals[4], "scored_avg": goals[5],
            "conceded": goals[6], "conceded_avg": goals[7],
        }

    shots = soup.select(".os_shots_stats_section")
    if len(shots) == 4:
        def shot(el):
            # Chaque bloc porte « libellé | total | moyenne par match ».
            nums = re.findall(r"-?\d+(?:[.,]\d+)?", _txt(el))
            return (_num(nums[0]) if nums else None,
                    _num(nums[1]) if len(nums) > 1 else None)

        for side, (total_el, blocked_el) in (("home", shots[0:2]), ("away", shots[2:4])):
            total, total_avg = shot(total_el)
            blocked, blocked_avg = shot(blocked_el)
            stats[side]["shots"] = {
                "total": total, "total_avg": total_avg,
                "blocked": blocked, "blocked_avg": blocked_avg,
            }

    attacks = [_first_num(_txt(e)) for e in soup.select(".os_attacks_stats")]
    if len(attacks) == 8:
        stats["home"]["attacks"] = {
            "total": attacks[0], "total_avg": attacks[1],
            "dangerous": attacks[4], "dangerous_avg": attacks[5],
        }
        stats["away"]["attacks"] = {
            "total": attacks[2], "total_avg": attacks[3],
            "dangerous": attacks[6], "dangerous_avg": attacks[7],
        }

    # Deux sous-tableaux (« Autres » et « Disciplinaire ») dont les index de
    # colonnes ne se suivent pas : on indexe par libellé, jamais par position.
    others: dict = {}
    for table in soup.select("table.os_others_table"):
        for tr in table.select("tr"):
            cells = tr.select("td, th")
            if len(cells) != 5:
                continue
            label = _txt(cells[2])
            if not label or label.lower().startswith("moy"):
                continue  # ligne d'en-tête
            others[label] = {
                "home": {"total": _txt(cells[1]) or None, "avg": _num(_txt(cells[0]))},
                "away": {"total": _txt(cells[3]) or None, "avg": _num(_txt(cells[4]))},
            }
    if others:
        stats["others"] = others

    return stats


# --- assemblage -----------------------------------------------------------

def parse_match(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    return {
        **parse_header(soup),
        "crests": parse_crests(soup),
        "predictions": parse_predictions(soup),
        "result_blocks": parse_result_blocks(soup),
        "standings": parse_standings(soup),
        "stats": parse_stats(soup),
    }


def load_html(url: str | None, file: str | None, force: bool) -> str:
    if file:
        return Path(file).read_text(encoding="utf-8", errors="replace")
    cached = cache_path(url)
    if cached.exists() and not force:
        return cached.read_text(encoding="utf-8", errors="replace")
    with ForebetBrowser() as browser:
        return browser.get(url, wait_for="#m1x2_table .rcnt", force=force)


def print_summary(data: dict) -> None:
    """Vue lisible en console, pour contrôler une extraction à l'œil."""
    print(f"{data['home']} - {data['away']}   {data['kickoff']}   "
          f"[{data['competition_tag']}]  #{data['match_id']}")

    print("\nPronostics")
    for key, pred in data["predictions"].items():
        probs = pred.get("probabilities") or {}
        shown = " / ".join(f"{k} {v}%" for k, v in probs.items())
        if not shown and pred.get("probability") is not None:
            shown = f"{pred['probability']}%"
        pick = pred.get("pick") or pred.get("expected_score") or "-"
        print(f"  {pred['label']:28} {shown:26} -> {pick}")

    print("\nBlocs de résultats")
    for block in data["result_blocks"]:
        rec = block["record"]
        print(f"  {(block['title'] or '?')[:32]:34} {rec['played']:2} matchs  "
              f"{rec['wins']}V {rec['draws']}N {rec['losses']}D  "
              f"{rec['goals_for']}:{rec['goals_against']}   forme {block['form']}")

    print("\nClassement")
    for row in data["standings"]:
        print(f"  {row['rank']:2}. {row['team']:20} {row['points']:3} pts  "
              f"{row['played']:2}j  {row['goals_for']:2}:{row['goals_against']:2}")

    print("\nStatistiques")
    for side in ("home", "away"):
        team = data[side]
        block = data["stats"].get(side, {})
        goals = block.get("goals", {})
        shots = block.get("shots", {})
        attacks = block.get("attacks", {})
        print(f"  {team:14} buts {goals.get('scored')}:{goals.get('conceded')}"
              f"  tirs {shots.get('total')} ({shots.get('total_avg')}/m)"
              f"  attaques dang. {attacks.get('dangerous')}")
    others = data["stats"].get("others", {})
    if others:
        print(f"  autres : {', '.join(others)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse une page match Forebet.")
    parser.add_argument("url", nargs="?", help="URL de la page match")
    parser.add_argument("--file", help="lire un HTML local plutôt qu'une URL")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--out", help="écrire le JSON dans ce fichier")
    parser.add_argument("--summary", action="store_true",
                        help="afficher un résumé lisible au lieu du JSON")
    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("donne une URL ou --file")

    data = parse_match(load_html(args.url, args.file, args.force))

    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"écrit : {args.out}")
    if args.summary:
        print_summary(data)
    elif not args.out:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
