"""Le filtre de libellés accepte-t-il les refus, et rien d'autre ?"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from shoot import is_reject_label

DOIT_CLIQUER = [
    "Refuser", "Tout refuser", "Refuser tout", "Je refuse",
    "Reject all", "Reject", "Reject additional cookies",
    "Reject all cookies", "Decline", "Decline all", "Deny all",
    "Continuer sans accepter", "Continue without accepting",
    "Non merci", "No thanks", "Disagree",
    "Only necessary cookies", "Essentiels uniquement",
    "Uniquement les cookies essentiels", "Cookies nécessaires uniquement",
    "Refuser les cookies optionnels", "Reject optional cookies",
    # Formes niées — celle de Sourcepoint, le bandeau le plus répandu.
    "I do not agree", "I don't agree", "Do not agree", "I disagree",
    "Ne pas accepter", "Je n'accepte pas", "Pas d'accord",
]

NE_DOIT_PAS = [
    # le piège rencontré sur The Guardian
    "Reject all and subscribe",
    "Accepter et continuer", "Tout accepter", "Accept all",
    "Accept all cookies", "I agree", "J'accepte", "Autoriser",
    "Allow all", "Continuer", "Continue", "OK", "Fermer", "Close",
    "S'abonner", "Subscribe", "Get Guardian Ad-Lite for €5/month",
    "Purchase Guardian Ad-Lite", "Se connecter", "Sign in",
    "Gérer mes choix", "Manage preferences", "Paramétrer",
    "En savoir plus", "Learn more", "Personnaliser",
    "Reject all and pay", "Refuser et s'abonner",
    # Voisins immédiats du bouton de refus, à ne surtout pas confondre.
    "I agree", "Manage options", "Gérer les options", "Store and/or access "
    "information on a device", "partners", "privacy policy",
]

erreurs = 0
for label in DOIT_CLIQUER:
    if not is_reject_label(label):
        print(f"  RATÉ (devrait cliquer)   {label!r}")
        erreurs += 1
for label in NE_DOIT_PAS:
    if is_reject_label(label):
        print(f"  DANGER (ne doit PAS)     {label!r}")
        erreurs += 1

print(f"\n{len(DOIT_CLIQUER)} refus + {len(NE_DOIT_PAS)} pièges — {erreurs} erreur(s)")
sys.exit(1 if erreurs else 0)
