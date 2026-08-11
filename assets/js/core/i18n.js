/* Deux langues, et une règle : le français est la clé, l'anglais la traduction.
   Écrire la phrase française directement dans le code garde le sens sous les
   yeux au moment où on le programme — un dictionnaire de clés abstraites
   (`match.timeline.title`) rend chaque appel illisible.

   Le site s'adresse à des clubs koweïtiens : l'anglais n'est pas une option
   décorative, c'est la langue dans laquelle il sera lu. */

const EN = {
  // chrome
  "Accueil": "Home", "Rencontres": "Fixtures", "Clubs": "Clubs",
  "Classement": "Table", "Calendrier": "Calendar", "Buteurs": "Scorers",
  "Thème": "Theme", "Retour": "Back",
  "Aller au contenu": "Skip to content",
  "Division 1 koweïtienne": "Kuwait Division 1",
  "Saison": "Season", "Journée": "Matchday", "Journée en cours": "Current matchday",

  // accueil
  "À la une": "Featured", "Ce soir": "Tonight", "À venir": "Upcoming",
  "Derniers résultats": "Latest results", "Les clubs": "The clubs",
  "Meilleurs buteurs": "Top scorers", "Tout voir": "See all",
  "Voir la rencontre": "View match", "Voir le club": "View club",
  "Le championnat en un coup d'œil": "The league at a glance",
  "buts marqués": "goals scored", "rencontres jouées": "matches played",
  "moyenne par match": "average per match", "clubs": "clubs",

  // rencontre
  "Chronologie": "Timeline", "Statistiques du match": "Match statistics",
  "Homme du match": "Standout player", "Comparatif": "Head to head",
  "Carte d'identité": "Season profile", "Effectifs": "Squads",
  "Parcours": "Form", "Face à face": "Previous meetings",
  "Contenu Instagram": "Instagram content",
  "Pas encore joué": "Not played yet", "Mi-temps": "Half-time",
  "Score final": "Full-time", "Stade": "Venue", "Arbitre": "Referee",
  "reçoit": "hosts", "à domicile": "at home", "à l'extérieur": "away",
  "observé": "watched", "d'après les buts": "from the goals",
  "But": "Goal", "But sur penalty": "Penalty", "But contre son camp": "Own goal",
  "Carton jaune": "Yellow card", "Carton rouge": "Red card",
  "Second jaune": "Second yellow",
  "Possession": "Possession", "Tirs": "Shots", "Tirs cadrés": "Shots on target",
  "Tirs non cadrés": "Shots off target", "Corners": "Corners",
  "Cartons jaunes": "Yellow cards", "Cartons rouges": "Red cards",
  "Remplacements": "Substitutions", "Buts": "Goals",
  "Attaques": "Attacks", "Attaques dangereuses": "Dangerous attacks",

  // club
  "Effectif": "Squad", "Gardiens": "Goalkeepers", "Défenseurs": "Defenders",
  "Milieux": "Midfielders", "Attaquants": "Forwards", "Poste inconnu": "Unknown position",
  "Entraîneur": "Manager", "Résultats": "Results", "Prochaines rencontres": "Next fixtures",
  "Matchs sans encaisser": "Clean sheets", "Buts sur penalty": "Penalty goals",
  "Buts pour": "Goals for", "Buts contre": "Goals against",
  "Différence": "Goal difference", "Points": "Points", "Joués": "Played",
  "Victoires": "Wins", "Nuls": "Draws", "Défaites": "Losses",
  "joueurs": "players", "buts": "goals", "but": "goal",

  // classement
  "Le championnat départage à la confrontation directe, pas à la différence de buts.":
    "This league separates equal teams on head-to-head, not goal difference.",
  "Équipe": "Team",

  "Aujourd'hui": "Today", "Joueur": "Player", "Bilan de saison": "Season record",
  "Attaque": "Attack", "Défense": "Defence", "Jeu": "Play", "Discipline": "Discipline",
  "Direct": "Live",

  // états
  "Rien à afficher": "Nothing to show",
  "Cette rencontre n'existe pas": "No such match",
  "Ce club n'existe pas": "No such club",
  "Retour à l'accueil": "Back home",
  "Chargement": "Loading",
  "Les données n'ont pas pu être chargées.": "The data could not be loaded.",
  "Le site a besoin d'un serveur pour lire ses données : ouvre-le via une adresse http, pas en double-cliquant le fichier.":
    "The site needs a server to read its data: open it over http rather than by double-clicking the file.",
  "Réessayer": "Retry",
  "Méthode": "Method",
  "Sources : Forebet, Sofascore, Flashscore.": "Sources: Forebet, Sofascore, Flashscore.",
  "Aucun pronostic : cette console publie des relevés, pas des prédictions.":
    "No predictions: this site publishes recorded figures, not forecasts.",
};

const STORE = "kd1-lang";

export let lang = (() => {
  try {
    const saved = localStorage.getItem(STORE);
    if (saved === "fr" || saved === "en") return saved;
  } catch (e) { /* navigation privée */ }
  return (navigator.language || "fr").toLowerCase().startsWith("en") ? "en" : "fr";
})();

/** Traduit. Une phrase sans traduction retombe sur le français plutôt que sur
 *  une clé vide : mieux vaut un mot dans la mauvaise langue qu'un trou. */
export function t(fr) {
  return lang === "en" ? (EN[fr] ?? fr) : fr;
}

export function setLang(next) {
  lang = next;
  try { localStorage.setItem(STORE, next); } catch (e) { /* ignore */ }
  document.documentElement.lang = next;
  location.reload();
}

export const other = () => (lang === "fr" ? "en" : "fr");
