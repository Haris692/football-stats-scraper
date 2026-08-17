"""Ce que `fetch_clock_sofa` fait d'une rencontre du relevé Sofascore.

Même raison d'être que `test_clock.py` : la minute est le premier chiffre que
l'œil lit, et la donnée n'existe que pendant un match — impossible de
l'éprouver à la demande. Les entrées ci-dessous sont celles réellement servies
le 17/08/2026 à 19h36 par `/api/v1/unique-tournament/20044/season/75693/
events/round/20`, journée où Forebet n'horlogeait que deux des quatre
rencontres.

Deux choses sont éprouvées ici, et ce sont les deux qui peuvent mentir sans
qu'on le voie :

- la **minute calculée**, puisque la source ne publie qu'un instant de départ ;
- le **rapprochement des noms**, puisque nos rencontres et les siennes n'ont ni
  les mêmes identifiants ni les mêmes libellés de clubs.

    python test_clock_sofa.py
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from fetch_clock_sofa import _pair, minute_of, normalise, status_of

erreurs = 0

# 19h15 au coup d'envoi, 19h36 au moment du relevé.
COUP_ENVOI = 1786986900
RELEVE = 1786988160


def verifie(intitule, obtenu, attendu):
    global erreurs
    if obtenu != attendu:
        print(f"  RATÉ  {intitule}\n        obtenu   {obtenu!r}\n"
              f"        attendu  {attendu!r}")
        erreurs += 1


def rencontre(**champs):
    """Une rencontre du relevé, telle que la source la sert."""
    base = {
        "id": 16271571,
        "homeTeam": {"name": "Al-Shamiya FC"},
        "awayTeam": {"name": "Burgan SC"},
        "startTimestamp": COUP_ENVOI,
        "status": {"code": 6, "description": "1st half", "type": "inprogress"},
        "time": {"periodLength": 2700, "overtimeLength": 1200,
                 "totalPeriodCount": 2, "currentPeriodStartTimestamp": 1786986913,
                 "initial": 0, "max": 2700, "extra": 540},
        "homeScore": {"current": 0, "display": 0, "period1": 0},
        "awayScore": {"current": 1, "display": 1, "period1": 1},
    }
    base.update(champs)
    return base


print("— une première mi-temps en cours —")
b = normalise(rencontre(), RELEVE)
verifie("la minute est calculée depuis le début de période", b["minute"], 21)
verifie("le statut", b["status"], "en_cours")
verifie("ça tourne", b["running"], True)
verifie("pas de temps additionnel avant la 45e", b["added"], None)
verifie("la source est nommée", b["source"], "sofascore")
verifie("le libellé porte la minute", b["label"], "21")

print("— le temps additionnel de la première mi-temps —")
# ⚠️ Le compte part du **début de période**, pas du coup d'envoi théorique : la
# période a démarré 13 s après l'heure annoncée. 47 min et 10 s après cette
# heure-là, on joue donc la 47e minute — soit « 45+2 » au tableau.
b = normalise(rencontre(), COUP_ENVOI + 47 * 60 + 10)
verifie("la minute se fige à la fin réglementaire", b["minute"], 45)
verifie("le surplus part en temps additionnel", b["added"], "2")

print("— la seconde mi-temps —")
# `initial` porte les 45 minutes déjà jouées ; la période vient de reprendre.
seconde = {"currentPeriodStartTimestamp": RELEVE, "initial": 2700, "max": 5400}
b = normalise(rencontre(status={"code": 7, "description": "2nd half",
                                "type": "inprogress"}, time=seconde), RELEVE + 90)
verifie("elle repart de la 46e, pas de la 1re", b["minute"], 47)

print("— la mi-temps, la fin, le report —")
b = normalise(rencontre(status={"code": 31, "description": "Halftime",
                                "type": "inprogress"}), RELEVE)
verifie("mi-temps : un statut, pas une minute", (b["status"], b["minute"]),
        ("mi_temps", None))
b = normalise(rencontre(status={"code": 100, "description": "Ended",
                                "type": "finished"}), RELEVE)
verifie("terminée", (b["status"], b["running"]), ("termine", False))
b = normalise(rencontre(status={"code": 60, "description": "Postponed",
                                "type": "postponed"}), RELEVE)
verifie("reportée", b["status"], "reporte")

print("— ce dont on ne dit rien —")
verifie("pas commencée : aucune horloge",
        normalise(rencontre(status={"code": 0, "description": "Not started",
                                    "type": "notstarted"}, time={}), RELEVE), None)
verifie("un type inconnu ne devient pas « en cours »",
        status_of({"code": 999, "type": "quelque chose de neuf"}), None)
# Une rencontre que la source dit en cours depuis quatre heures : son repère de
# temps est resté en arrière. Mieux vaut pas de minute qu'une 240e.
verifie("un repère de temps aberrant est écarté",
        normalise(rencontre(), COUP_ENVOI + 4 * 3600), None)
verifie("en cours sans repère de temps : rien à afficher",
        normalise(rencontre(time={}), RELEVE), None)

print("— l'orientation du score —")
# Notre hôte est Burgan, le sien Al-Shamiya : le couple entier se permute.
b = normalise(rencontre(), RELEVE, inverted=True)
verifie("le score suit notre hôte", b["score"], [1, 0])
verifie("la mi-temps aussi", b["half_time"], [1, 0])
b = normalise(rencontre(), RELEVE)
verifie("sans permutation, le score reste celui de la source", b["score"], [0, 1])

print("— le rapprochement des noms —")
# Aucune rencontre n'est horlogée si ces paires ne se rejoignent pas : c'est
# par elles, et par le jour, qu'on retrouve nos identifiants Forebet.
for chez_nous, chez_eux in (
    (("Burgan SC", "Al Shamiya"), ("Al-Shamiya FC", "Burgan SC")),
    (("Al Jazira", "Yarmouk (KUW)"), ("Yarmouk SC", "Al Jazeera FC Kuwait")),
    (("Sulaibikhat", "Sahel (KUW)"), ("Al Sahel SC", "Al Sulaibikhat FC")),
    (("Sporty", "Khaitan SC"), ("Khaitan SC", "Sporty FC")),
):
    verifie(f"{chez_nous[0]} - {chez_nous[1]}",
            _pair(*chez_nous), _pair(*chez_eux))

print("\n" + ("tout est bon" if not erreurs else f"{erreurs} vérification(s) en échec"))
sys.exit(1 if erreurs else 0)
