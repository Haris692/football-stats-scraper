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
serve.fetch_stats = lambda ids, browser=None, force=False: dict(STATS)
serve.fetch_clock = lambda browser=None: dict(CLOCKS)
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
verifie("relevée sans horloge : pas de clé `clock`",
        "clock" in live["2487403"], False)
verifie("suivie sans relevé : un bloc quand même",
        live["2487404"]["clock"]["minute"], 12)
verifie("et ce bloc n'a AUCUNE statistique — sans quoi la page dessinerait "
        "un tableau vide", live["2487404"].get("fields"), None)
verifie("la rencontre reportée sort du suivi",
        collecteur.live_ids(), [2487402, 2487403, 2487404])

# Le coup de sifflet final : `ft_score` se remplit, la rencontre sort du suivi.
STATS[2487402]["full_time"] = "2-0"
collecteur._cycle(collecteur.live_ids(), None)
verifie("la rencontre finie sort du suivi",
        collecteur.live_ids(), [2487403, 2487404])

print(f"\n{erreurs} erreur(s)")
sys.exit(1 if erreurs else 0)
