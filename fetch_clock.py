"""L'horloge d'un match en cours : minute de jeu, temps additionnel, statut.

    https://www.forebet.com/gsv/

C'est **le même contenu que le flux SSE `/glvs/`**, servi en instantané au lieu
d'être poussé. Le choix est délibéré (voir PROGRESS.md, 17/08/2026) : `all.js`
utilise les deux — l'`EventSource` au chargement, et ce point d'entrée en XHR
quand l'onglet redevient visible, pour rattraper ce qu'il a manqué. Le second
convient bien mieux ici, parce que le collecteur ne pousse rien : il prend un
relevé par minute et le publie. Un flux poussé n'émet **qu'au changement**, donc
un collecteur qui vient de démarrer resterait muet jusqu'au fait de jeu suivant,
et il faudrait tenir la page Chrome ouverte en permanence — celle-là même que
`fetch_stats` fait naviguer à chaque relevé.

Ce que `get_evs_n.php` ne donne pas et qu'on trouve ici (vérifié le
10/08/2026 : son en-tête ne porte ni `minute` ni `status`) :

- la **minute de jeu** et le **temps additionnel** (`ad_tm`) ;
- un **statut franc** : `FT` clôt la rencontre, `Postp.` dit qu'elle est
  reportée. Le reste du projet devait le deviner d'une fenêtre de 150 minutes
  autour du coup d'envoi.

⚠️ **Le relevé est global, pas filtré.** Une seule requête (~8 Ko) rend toutes
les rencontres que Forebet suit à cet instant, indexées par identifiant de
match — d'où qu'elles viennent. C'est aussi ce que fait la page elle-même : elle
tire la liste entière et y cherche son match. Suivre quatre rencontres coûte
donc exactement une requête, comme d'en suivre une.

⚠️ **Un match absent du relevé n'est pas une anomalie** : Forebet n'y met que ce
qu'il suit au moment de la demande. L'absence rend `None`, et l'appelant se
passe d'horloge — il ne la fabrique pas.

    python fetch_clock.py                    # tout le relevé, lisible
    python fetch_clock.py 2487403 2487405    # seulement ces rencontres
"""

from __future__ import annotations

import argparse
import json
import sys

from browser import CdpBrowser

ENDPOINT = "https://www.forebet.com/gsv/"

# La Division 1 koweïtienne chez Forebet. Lue dans `#drlscrm` d'une page de
# match, qui porte « <match_id>,<league_id> ». Sert à reconnaître nos
# rencontres dans un relevé mondial, jamais à filtrer la requête : le point
# d'entrée ne prend aucun paramètre.
LEAGUE_ID = "417"

# Ce que la source écrit dans `minute` quand ce n'est pas un nombre. Tout le
# reste est traité comme une minute de jeu.
STATUSES = {
    "HT": "mi_temps",
    "FT": "termine",
    "AET": "termine",           # après prolongation
    "Pen.": "termine",          # aux tirs au but
    "Live Pen.": "tirs_au_but",
    "Postp.": "reporte",
    "Canc.": "annule",
    "Abn.": "abandonne",
    "Susp.": "suspendu",
    "Delayed": "retarde",
}


def _int(value):
    if value is None or value == "" or value == "?":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _running(value) -> bool:
    """`running` arrive en booléen ici, en `"1"` / `""` sur d'autres façades."""
    return value is True or value in ("1", 1)


def normalise(entry: dict) -> dict | None:
    """Un bloc d'horloge exploitable, ou `None` si l'entrée ne dit rien."""
    if not isinstance(entry, dict):
        return None

    label = (entry.get("minute") or "").strip()
    minute = _int(label)
    running = _running(entry.get("running"))

    if label in STATUSES:
        status = STATUSES[label]
    elif minute is not None:
        status = "en_cours" if running else "arrete"
    elif running:
        status = "en_cours"
    else:
        # Ni minute, ni statut connu, ni « ça tourne » : la rencontre est
        # listée mais pas commencée. Rien à afficher.
        return None

    # ⚠️ Le temps additionnel n'est bon qu'en cours de jeu : la source le laisse
    # traîner après le coup de sifflet (constaté dans `parseLiveJson`, qui le
    # retire lui-même dès que `ad_tm` retombe). On ne le reprend donc que si la
    # rencontre tourne, et jamais comme une minute.
    added = (entry.get("ad_tm") or "").strip() or None
    if not running:
        added = None

    home, away = _int(entry.get("host_sc")), _int(entry.get("guest_sc"))
    ht_home, ht_away = _int(entry.get("ht_home")), _int(entry.get("ht_away"))

    return {
        "source": "forebet/gsv",
        "minute": minute,
        # Le libellé brut, tel que la source l'écrit. Gardé à côté de `status`
        # parce qu'un statut inconnu doit rester lisible plutôt que disparaître.
        "label": label or None,
        "added": added,
        "running": running,
        "status": status,
        "league_id": entry.get("lid") or None,
        # Le score de CE relevé. Il ne remplace pas celui de `fetch_stats` — il
        # sert à le recouper, les deux points d'entrée n'ayant pas le même
        # fournisseur (voir `serve.py`).
        "score": None if home is None or away is None else [home, away],
        "half_time": None if ht_home is None or ht_away is None else [ht_home, ht_away],
    }


def fetch(browser: CdpBrowser | None = None, force: bool = True) -> dict:
    """{match_id: bloc d'horloge} — tout ce que Forebet suit à cet instant.

    `force` par défaut, à l'inverse du reste du projet : une horloge servie
    depuis le cache n'a aucun intérêt, c'est exactement la donnée qui périme en
    une minute.
    """
    owned = browser is None
    browser = browser or CdpBrowser()
    try:
        raw = browser.get_json(ENDPOINT, force=force, max_age_hours=0)
    except Exception as exc:
        # L'horloge est un bonus : le direct existait sans elle. Une panne ici
        # ne doit pas emporter le relevé des statistiques.
        print(f"  horloge : indisponible ({exc})", file=sys.stderr, flush=True)
        return {}
    finally:
        if owned:
            browser.close()

    if not isinstance(raw, dict):
        return {}
    out = {}
    for mid, entry in raw.items():
        block = normalise(entry)
        if block is not None and _int(mid) is not None:
            out[int(mid)] = block
    return out


def print_summary(clocks: dict, league_only: bool = False) -> None:
    rows = [(mid, b) for mid, b in clocks.items()
            if not league_only or b.get("league_id") == LEAGUE_ID]
    if not rows:
        print("aucune rencontre suivie en ce moment"
              + (f" en ligue {LEAGUE_ID}" if league_only else ""))
        return
    for mid, b in sorted(rows, key=lambda r: r[0]):
        horloge = b["label"] or "—"
        if b["added"]:
            horloge += f"+{b['added']}"
        score = f"{b['score'][0]}-{b['score'][1]}" if b["score"] else "?-?"
        print(f"  #{mid}  ligue {b['league_id'] or '?':>4}  {horloge:>10}  "
              f"{score:>5}  {b['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="L'horloge des matchs suivis par Forebet à cet instant.")
    parser.add_argument("match_ids", nargs="*", type=int,
                        help="ne montrer que ces rencontres (défaut : toutes)")
    parser.add_argument("--league", action="store_true",
                        help=f"ne montrer que la ligue {LEAGUE_ID} (Division 1 koweïtienne)")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args()

    clocks = fetch()
    if args.match_ids:
        clocks = {mid: b for mid, b in clocks.items() if mid in set(args.match_ids)}
        for mid in args.match_ids:
            if mid not in clocks:
                print(f"  #{mid} : pas suivi en ce moment", file=sys.stderr)

    if args.json:
        print(json.dumps(clocks, ensure_ascii=False, indent=2))
    else:
        print(f"{len(clocks)} rencontre(s) dans le relevé")
        print_summary(clocks, league_only=args.league)
    return 0


if __name__ == "__main__":
    sys.exit(main())
