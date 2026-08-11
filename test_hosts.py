"""La permutation d'hôte emporte-t-elle bien TOUT ce qui décrit un camp ?

Le risque de cette correction n'est pas de permuter à tort : c'est de permuter
à moitié. Une fiche dont le nom change mais dont les tirs restent en place
affiche des chiffres attribués au mauvais club, et rien ne le signale.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from hosts import arbitrate, swap_match, verdicts

erreurs = 0


def verifie(intitule, obtenu, attendu):
    global erreurs
    if obtenu != attendu:
        print(f"  RATÉ  {intitule}\n        obtenu   {obtenu!r}\n"
              f"        attendu  {attendu!r}")
        erreurs += 1


def fiche():
    return {
        "match_id": 1, "slug": "shamiya-yarmouk", "url": "https://…/shamiya-yarmouk-1",
        "home": "Al Shamiya", "away": "Yarmouk (KUW)",
        "kickoff": "02/08/2026 18:00",
        "stats": {
            "home": {"goals": {"scored": 15}},
            "away": {"goals": {"scored": 35}},
            "others": {"Corners": {"home": 3, "away": 9}},
        },
        "match_stats": {
            "home": {"possession": 34, "shots": 4},
            "away": {"possession": 66, "shots": 20},
            "attacks": {"home": {"total": 62}, "away": {"total": 90},
                        "suspect": True},
            "colors": {"home": "#0046A8", "away": "#B0E8E6"},
            "half_time": "0-1", "full_time": "0-3",
            "venue": "Jaber Al-Mubarak Stadium",
        },
        # Paire volontairement incomplète : `palette` n'a pas toujours les deux
        # côtés, et une absence ne doit pas devenir un `None`.
        "palette": {"home": "#fff", "away": "#0c3760", "away_true": "#0c3760"},
        "squads": {"home": {"sofascore_name": "Al-Shamiya FC"},
                   "away": {"sofascore_name": "Yarmouk SC"}},
        # Rencontres CITÉES par la fiche : elles ont leur propre hôte, et le
        # verdict rendu sur ce match-ci ne les concerne pas.
        "result_blocks": [{"matches": [
            {"home": "Sahel (KUW)", "away": "Sporty",
             "home_goals": 2, "away_goals": 0},
        ]}],
    }


print("— permutation d'une fiche —")
m = fiche()
swap_match(m)

verifie("noms", (m["home"], m["away"]), ("Yarmouk (KUW)", "Al Shamiya"))
verifie("stats de saison", (m["stats"]["home"]["goals"]["scored"],
                            m["stats"]["away"]["goals"]["scored"]), (35, 15))
verifie("stats.others", (m["stats"]["others"]["Corners"]["home"],
                         m["stats"]["others"]["Corners"]["away"]), (9, 3))
verifie("possession", (m["match_stats"]["home"]["possession"],
                       m["match_stats"]["away"]["possession"]), (66, 34))
verifie("tirs", (m["match_stats"]["home"]["shots"],
                 m["match_stats"]["away"]["shots"]), (20, 4))
verifie("attaques", (m["match_stats"]["attacks"]["home"]["total"],
                     m["match_stats"]["attacks"]["away"]["total"]), (90, 62))
verifie("couleurs", (m["match_stats"]["colors"]["home"],
                     m["match_stats"]["colors"]["away"]), ("#B0E8E6", "#0046A8"))
verifie("mi-temps", m["match_stats"]["half_time"], "1-0")
verifie("score final", m["match_stats"]["full_time"], "3-0")
verifie("squads", (m["squads"]["home"]["sofascore_name"],
                   m["squads"]["away"]["sofascore_name"]),
        ("Yarmouk SC", "Al-Shamiya FC"))

# Ce qui NE doit PAS bouger.
verifie("slug conservé", m["slug"], "shamiya-yarmouk")
verifie("url conservée", m["url"], "https://…/shamiya-yarmouk-1")
verifie("stade conservé", m["match_stats"]["venue"], "Jaber Al-Mubarak Stadium")
verifie("clé non appariée intacte", m["match_stats"]["attacks"]["suspect"], True)
verifie("face à face intact", m["result_blocks"][0]["matches"][0]["home"],
        "Sahel (KUW)")

# Une paire incomplète se déplace, elle ne se complète pas.
verifie("palette permutée", (m["palette"]["home"], m["palette"]["away"]),
        ("#0c3760", "#fff"))
verifie("away_true devient home_true", m["palette"].get("home_true"), "#0c3760")
verifie("pas d'away_true inventé", "away_true" in m["palette"], False)

# Deux permutations reviennent au point de départ : la preuve qu'aucune valeur
# ne s'est perdue en route.
avant = fiche()
apres = fiche()
swap_match(apres)
swap_match(apres)
verifie("permutation involutive", apres, avant)


print("— arbitrage —")
RESULTATS = [
    {"home": "Yarmouk", "away": "Al Shamiya", "kickoff": "02/08/2026 18:00"},
    {"home": "Khaitan", "away": "Al Sulaibikhat", "kickoff": "02/08/2026 19:45"},
    # L'aller, même paire, autre jour, ordre inverse : c'est lui qui piège un
    # appariement fait sur la seule paire d'équipes.
    {"home": "Al Shamiya", "away": "Yarmouk", "kickoff": "22/09/2025 19:30"},
]

fixtures = [
    {"match_id": 1, "home": "Al Shamiya", "away": "Yarmouk (KUW)",
     "kickoff": "02/08/2026 18:00", "score": "0 - 3"},
    {"match_id": 2, "home": "Khaitan SC", "away": "Sulaibikhat",
     "kickoff": "02/08/2026 19:45", "score": "0 - 1"},
    {"match_id": 3, "home": "Burgan SC", "away": "Sporty",
     "kickoff": "14/08/2026 19:25", "score": None},
]
matches = [fiche(), {"match_id": 2, "home": "Khaitan SC", "away": "Sulaibikhat"}]
swaps = arbitrate(fixtures, matches, RESULTATS)

verifie("une seule permutation", len(swaps), 1)
verifie("le match 1 est remis à l'endroit",
        (fixtures[0]["home"], fixtures[0]["away"]), ("Yarmouk (KUW)", "Al Shamiya"))
verifie("son score suit", fixtures[0]["score"], "3 - 0")
verifie("sa fiche suit", matches[0]["home"], "Yarmouk (KUW)")
verifie("le match 2, déjà d'accord, ne bouge pas",
        (fixtures[1]["home"], fixtures[1]["away"]), ("Khaitan SC", "Sulaibikhat"))
verifie("le match 2 n'est pas marqué", fixtures[1].get("host_swapped"), None)
verifie("match 1 arbitré", fixtures[0]["host_source"], "flashscore")
verifie("match 3 sans arbitre", fixtures[2]["host_source"], None)
verifie("match 3 laissé à Forebet",
        (fixtures[2]["home"], fixtures[2]["away"]), ("Burgan SC", "Sporty"))

# L'aller de septembre ne doit pas servir de verdict au retour d'août.
verifie("l'index distingue les deux manches", len(verdicts(RESULTATS)), 3)

print(f"\n{erreurs} erreur(s)")
sys.exit(1 if erreurs else 0)
