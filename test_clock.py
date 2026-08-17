"""Ce que `fetch_clock.normalise` fait d'une entrée du relevé Forebet.

La minute est le premier chiffre que l'œil lit sur un match en cours : s'il est
faux, tout ce qui est autour devient suspect. Et comme la donnée n'existe que
pendant une rencontre, on ne peut pas l'éprouver à la demande — d'où ce fichier,
bâti sur des entrées réellement observées le 17/08/2026 sur `/gsv/`.

    python test_clock.py
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from fetch_clock import fetch, normalise

erreurs = 0


def verifie(intitule, obtenu, attendu):
    global erreurs
    if obtenu != attendu:
        print(f"  RATÉ  {intitule}\n        obtenu   {obtenu!r}\n"
              f"        attendu  {attendu!r}")
        erreurs += 1


def entree(**champs):
    """Une entrée du relevé, avec les champs que la source met toujours."""
    base = {"lid": "417", "host_sc": "0", "guest_sc": "0", "minute": "",
            "running": False, "ht_home": "", "ht_away": ""}
    base.update(champs)
    return base


print("— une rencontre en cours —")
b = normalise(entree(minute="37", running=True, host_sc="1", guest_sc="0"))
verifie("la minute est un nombre", b["minute"], 37)
verifie("le statut", b["status"], "en_cours")
verifie("le libellé brut est gardé", b["label"], "37")
verifie("le score du relevé", b["score"], [1, 0])
verifie("pas de temps additionnel", b["added"], None)
verifie("la ligue", b["league_id"], "417")

print("— le temps additionnel —")
b = normalise(entree(minute="45", ad_tm="3", running=True))
verifie("repris tel quel", b["added"], "3")
verifie("il ne se mélange pas à la minute", b["minute"], 45)

# ⚠️ La source laisse traîner `ad_tm` après le coup de sifflet. Repris à ce
# moment-là, il ferait afficher « 90+4' » sur un match terminé depuis une heure.
b = normalise(entree(minute="FT", ad_tm="4", running=False, host_sc="2", guest_sc="1"))
verifie("lâché dès que la rencontre ne tourne plus", b["added"], None)
verifie("fin de match", b["status"], "termine")
verifie("pas de minute à la fin", b["minute"], None)

print("— la mi-temps —")
b = normalise(entree(minute="HT", running=True, ht_home="1", ht_away="0"))
verifie("statut", b["status"], "mi_temps")
verifie("le score de la mi-temps", b["half_time"], [1, 0])

print("— ce qui ne se jouera pas —")
b = normalise(entree(minute="Postp.", running=False, host_sc="?", guest_sc="?"))
verifie("statut", b["status"], "reporte")
# `?` veut dire « on ne sait pas », et surtout pas zéro.
verifie("aucun score inventé", b["score"], None)

print("— les cas limites —")
verifie("une entrée vide ne dit rien", normalise(entree()), None)
verifie("ce n'est pas un dict", normalise("bonjour"), None)
b = normalise(entree(minute="", running=True))
verifie("« ça tourne » sans minute reste en cours", b["status"], "en_cours")
verifie("et n'invente pas de minute", b["minute"], None)

# Un statut que la source inventerait demain : il doit rester lisible plutôt
# que de faire disparaître la rencontre du relevé.
b = normalise(entree(minute="Break", running=True))
verifie("statut inconnu, libellé gardé", b["label"], "Break")
verifie("statut inconnu, rencontre gardée", b["status"], "en_cours")

# `running` arrive en booléen sur /gsv/ et en chaîne sur d'autres façades.
verifie("running en chaîne", normalise(entree(minute="12", running="1"))["running"], True)
verifie("running vide", normalise(entree(minute="12", running=""))["running"], False)
verifie("arrêté mais avec une minute",
        normalise(entree(minute="12", running=""))["status"], "arrete")

print("— le relevé complet —")
# `fetch` ne doit JAMAIS lever : l'horloge est un bonus posé sur le direct, une
# panne ici ne doit pas emporter le relevé des statistiques.


class BrowserQuiTombe:
    def get_json(self, *a, **k):
        raise RuntimeError("Chrome est parti")


verifie("une source en panne rend un relevé vide",
        fetch(browser=BrowserQuiTombe()), {})


class BrowserQuiRend:
    def __init__(self, blob):
        self.blob = blob

    def get_json(self, *a, **k):
        return self.blob


releve = fetch(browser=BrowserQuiRend({
    "2487403": entree(minute="12", running=True),
    "2487405": entree(minute="Postp."),
    "pasunid": entree(minute="30", running=True),
    "2487404": entree(),                       # listée, pas commencée
}))
verifie("les identifiants sont des entiers", sorted(releve), [2487403, 2487405])
verifie("la rencontre non commencée est absente", 2487404 in releve, False)

print("— la fusion dans le collecteur —")
# Deux points d'entrée dont la couverture ne se recouvre pas : chaque rencontre
# peut avoir des statistiques, une horloge, les deux, ou ni l'une ni l'autre. On
# ne peut l'éprouver en vrai que pendant un match, d'où ce montage à sources
# factices — c'est le seul endroit où une erreur ne se verrait qu'un soir de
# journée de championnat, une fois tout le monde en train de regarder.
import copy
import json
import tempfile
from datetime import datetime
from pathlib import Path

import serve

maintenant = datetime.now().isoformat(timespec="minutes")
fichier = Path(tempfile.mkdtemp()) / "site.json"
fichier.write_text(json.dumps({"fixtures": [
    {"match_id": m, "kickoff_iso": maintenant}
    for m in (2487402, 2487403, 2487404, 2487405)]}), encoding="utf-8")

STATS = {
    2487402: {"fields": ["goals"], "home": {"goals": 1}, "away": {"goals": 0},
              "full_time": None},                       # relevée ET suivie
    2487403: {"fields": ["goals"], "home": {"goals": 0}, "away": {"goals": 0},
              "full_time": None},                       # relevée, pas suivie
}
CLOCKS = {
    2487402: {"minute": 37, "status": "en_cours", "label": "37"},
    2487404: {"minute": 12, "status": "en_cours", "label": "12"},  # suivie, pas relevée
    2487405: {"minute": None, "status": "reporte", "label": "Postp."},
}
# La seconde source d'horloge, celle qui comble les trous de la première.
SOFA = {2487403: {"minute": 22, "status": "en_cours", "label": "22",
                  "source": "sofascore"}}
demandes = []


def repli(fixtures, browser=None):
    demandes.append(sorted(f["match_id"] for f in fixtures))
    return {f["match_id"]: SOFA[f["match_id"]]
            for f in fixtures if f["match_id"] in SOFA}


# ⚠️ Copie profonde : `_cycle` pose `clock` DANS le bloc de statistiques. Avec
# une copie de surface, la clé restait collée d'un cycle sur l'autre et un
# relevé sans horloge semblait en garder une — la vraie `fetch_stats` rend un
# bloc neuf à chaque appel.
serve.fetch_stats = lambda ids, browser=None, force=False: copy.deepcopy(STATS)
serve.fetch_clock = lambda browser=None: dict(CLOCKS)
serve.fetch_clock_sofa = repli

# Les faits de jeu : une requête par rencontre, donc un compteur des demandes.
LIGNES = {2487402: [{"type": "goal", "class": "regular", "minute": 12,
                     "added": None, "player": "Un tel", "side": "home",
                     "score": "1-0"}]}
demandes_faits = []


def faits(fixtures, browser=None):
    demandes_faits.append(sorted(f["match_id"] for f in fixtures))
    return {f["match_id"]: LIGNES.get(f["match_id"], []) for f in fixtures}


serve.fetch_live_events = faits
serve.CdpBrowser = lambda **k: "faux-chrome"

collecteur = serve.LiveCollector(fichier)
collecteur._cycle(collecteur.live_ids(), None)
live = collecteur.snapshot()["live"]

verifie("les quatre rencontres sont publiées", sorted(live),
        ["2487402", "2487403", "2487404", "2487405"])
verifie("l'horloge se pose sur les statistiques",
        live["2487402"]["clock"]["minute"], 37)
verifie("les statistiques survivent à la fusion",
        live["2487402"]["home"]["goals"], 1)
verifie("l'horloge de repli comble le trou de la première source",
        live["2487403"]["clock"]["minute"], 22)
verifie("le repli n'est demandé QUE pour ce qui manque — sinon on solliciterait "
        "une seconde source pour rien", demandes, [[2487403]])
verifie("suivie sans relevé : un bloc quand même",
        live["2487404"]["clock"]["minute"], 12)
verifie("et ce bloc n'a AUCUNE statistique — sans quoi la page dessinerait "
        "un tableau vide", live["2487404"].get("fields"), None)
verifie("le fil du match est publié, et dit d'où il vient",
        (live["2487402"]["timeline"], live["2487402"]["timeline_source"]),
        (LIGNES[2487402], "sofascore"))
verifie("il est demandé pour toutes les rencontres suivies, la première fois",
        demandes_faits, [[2487402, 2487403, 2487404, 2487405]])

verifie("la rencontre reportée sort du suivi",
        collecteur.live_ids(), [2487402, 2487403, 2487404])

# Le coup de sifflet final : `ft_score` se remplit, la rencontre sort du suivi.
STATS[2487402]["full_time"] = "2-0"
collecteur._cycle(collecteur.live_ids(), None)
verifie("la rencontre finie sort du suivi",
        collecteur.live_ids(), [2487403, 2487404])

# Ni l'une ni l'autre source ne la connaît : le bloc existe (il a des
# statistiques) mais il n'a pas d'horloge. Une minute inventée serait pire que
# pas de minute du tout.
verifie("à score inchangé, le fil n'est pas redemandé — une requête PAR "
        "rencontre, on ne la paie pas toutes les minutes",
        len(demandes_faits), 1)

# Un but tombe : celui-là, et lui seul, mérite qu'on redemande son fil.
STATS[2487403]["home"]["goals"] = 1
LIGNES[2487403] = [{"type": "goal", "class": "regular", "minute": 61,
                    "added": None, "player": "Un autre", "side": "home",
                    "score": "1-0"}]
collecteur._cycle(collecteur.live_ids(), None)
verifie("un but redemande le fil de cette rencontre-là", demandes_faits[-1],
        [2487403])
verifie("et le but arrive dans le relevé",
        collecteur.snapshot()["live"]["2487403"]["timeline"], LIGNES[2487403])

SOFA.clear()
collecteur._cycle(collecteur.live_ids(), None)
verifie("sans horloge nulle part, aucune n'est fabriquée",
        "clock" in collecteur.snapshot()["live"]["2487403"], False)

print("— quand plus rien ne répond —")
# Chrome mort sous le collecteur : les trois sources se taisent, chacune ayant
# avalé sa panne. Le collecteur doit le comprendre tout seul et reposer son
# navigateur, sinon il resservira le même cadavre jusqu'à la fin des temps.
serve.fetch_stats = lambda ids, browser=None, force=False: {}
serve.fetch_clock = lambda browser=None: {}
serve.fetch_live_events = lambda fixtures, browser=None: {}
repose = []
collecteur._drop = lambda b: (repose.append(b), None)[1]
verifie("le navigateur est reposé", collecteur._cycle(collecteur.live_ids(),
                                                      "chrome-mort"), None)
verifie("et c'est bien celui-là", repose, ["chrome-mort"])
verifie("le relevé le dit plutôt que de se taire",
        collecteur.snapshot()["state"], "indisponible : aucune source")

print(f"\n{erreurs} erreur(s)")
sys.exit(1 if erreurs else 0)
