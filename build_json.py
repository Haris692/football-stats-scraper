"""Export JSON : un fichier par match dans `output/`, plus un index.

Même collecte que `build_console.py` — c'est la même fonction `assemble()` qui
sert les deux. La console est faite pour être lue par un humain ; ce module
produit la même matière sous une forme qu'un autre programme peut consommer
(générateur de visuels, feuille de calcul, autre front).

Deux choix qui distinguent cette sortie de la charge utile de la console :

- **Les écussons ne sont pas embarqués.** Dans la console ils sont des `data:`
  URI, ce qui garantit un fichier unique et hors-ligne ; ici ils pèseraient
  400 Ko par match pour rien. Le fichier `output/teams.json` les porte une seule
  fois, et chaque match renvoie vers lui par le nom du club.
- **Les pronostics restent écartés**, comme dans la console : ce projet publie
  des relevés, pas des prédictions (voir PROGRESS.md). `parse_match.py` continue
  de les extraire pour qui en voudrait.

    python build_json.py --fixtures --scope all
    python build_json.py --fixtures --out export/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from build_console import add_source_arguments, assemble
from crests import load_store, pair_note

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"

SCHEMA_VERSION = 1


def team_entry(match: dict, side: str, teams: dict) -> dict:
    """Tout ce qu'on sait d'un des deux camps, rassemblé au même endroit.

    Dans la charge utile de la console, ces informations sont éparpillées entre
    `standings`, `stats`, `result_blocks` et `palette` : la page les recroise à
    l'affichage. Un consommateur externe, lui, n'a pas envie de refaire ce
    travail.
    """
    name = match.get("home" if side == "home" else "away")
    standing = next((r for r in match.get("standings") or [] if r["team"] == name), None)
    season = (match.get("stats") or {}).get(side) or {}
    palette = match.get("palette") or {}

    # Blocs 1 et 2 : le parcours complet de chaque équipe ; 3 et 4 : son bilan
    # à domicile (l'hôte) ou à l'extérieur (le visiteur). Ordre garanti par la
    # source, vérifié dans parse_match.py.
    blocks = match.get("result_blocks") or []
    overall = blocks[1 if side == "home" else 2] if len(blocks) == 5 else None
    venue = blocks[3 if side == "home" else 4] if len(blocks) == 5 else None

    return {
        "name": name,
        "side": side,
        "colors": (teams.get(name) or {}).get("colors") or [],
        # La couleur retenue pour ce match précis : elle peut différer de la
        # première couleur du club quand les deux équipes partagent une teinte.
        "match_color": palette.get(side),
        "standing": standing,
        "season": season,
        "form": (overall or {}).get("form"),
        "record_all_competitions": (overall or {}).get("record"),
        "record_at_venue": (venue or {}).get("record"),
    }


def match_document(match: dict, fixture: dict | None, teams: dict) -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "match_id": match.get("match_id"),
        "url": match.get("url"),
        "competition": match.get("competition_tag"),
        "kickoff": match.get("kickoff"),
        "kickoff_iso": (fixture or {}).get("kickoff_iso"),
        "played": bool((fixture or {}).get("played")),
        "score": (fixture or {}).get("score"),
        "broadcast": match.get("broadcast"),
        "home": team_entry(match, "home", teams),
        "away": team_entry(match, "away", teams),
        # Le relevé de la rencontre elle-même, absent tant que le match n'a pas
        # été joué (ou si la source ne le couvre pas). Voir fetch_stats.py.
        "match_stats": match.get("match_stats"),
        "head_to_head": (match.get("result_blocks") or [{}])[0] or None,
        "standings": match.get("standings"),
    }


def write_all(matches: list[dict], fixtures: list[dict], out_dir: Path,
              clean: bool) -> list[Path]:
    by_id = {f.get("match_id"): f for f in fixtures if f.get("match_id")}
    teams = load_store()
    for m in matches:
        m.setdefault("palette", pair_note(teams, m.get("home"), m.get("away")))

    matches_dir = out_dir / "matches"
    if clean and matches_dir.exists():
        # Sans ça, une fiche d'un ancien build survivrait à côté des nouvelles
        # et l'index ne la mentionnerait pas — un fichier orphelin qu'on ne sait
        # plus dater.
        shutil.rmtree(matches_dir)
    matches_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for match in matches:
        mid = match.get("match_id")
        if mid is None:
            print(f"  ignoré : {match.get('home')} - {match.get('away')} n'a pas "
                  f"d'identifiant de match", file=sys.stderr)
            continue
        doc = match_document(match, by_id.get(mid), teams)
        path = matches_dir / f"{mid}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)

    # Les écussons une seule fois, pas dans chaque fiche.
    (out_dir / "teams.json").write_text(
        json.dumps(teams, ensure_ascii=False, indent=2), encoding="utf-8")

    now = datetime.now()
    detailed = {m.get("match_id") for m in matches}
    index = {
        "schema": SCHEMA_VERSION,
        "generated": now.isoformat(timespec="seconds"),
        "source": "forebet.com (fiches et statistiques), flashscore.com (calendrier)",
        "counts": {"fixtures": len(fixtures), "documents": len(written)},
        "fixtures": [{
            **{k: f.get(k) for k in ("match_id", "home", "away", "kickoff",
                                     "kickoff_iso", "played", "score",
                                     "competition_tag", "source")},
            # Une rencontre venue du seul calendrier Flashscore n'a pas de fiche :
            # on le dit ici plutôt que de laisser le consommateur chercher un
            # fichier qui n'existe pas.
            "document": f"matches/{f['match_id']}.json"
                        if f.get("match_id") in detailed else None,
        } for f in fixtures],
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exporte les rencontres au format JSON, un fichier par match.")
    add_source_arguments(parser)
    parser.add_argument("--out", default=str(OUTPUT_DIR),
                        help="répertoire de sortie (défaut : output/)")
    parser.add_argument("--keep-stale", action="store_true",
                        help="ne pas effacer les fiches des builds précédents")
    args = parser.parse_args()

    matches, fixtures = assemble(args)
    if not matches:
        print("aucun match à exporter : le cache est vide et aucune URL n'a été "
              "donnée.", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = write_all(matches, fixtures, out_dir, clean=not args.keep_stale)

    total = sum(p.stat().st_size for p in written)
    print(f"écrit : {out_dir}  ({len(written)} fiche(s) sur {len(fixtures)} "
          f"rencontres, {total // 1024} Ko + index et écussons)")
    for path in written:
        print(f"  · {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
