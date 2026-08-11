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
  "Prochaine journée": "Next matchday", "Dernière journée": "Last matchday",
  "Rencontre en cours. Le score n'est pas suivi en direct sur cette page.":
    "Match in progress. The score is not tracked live on this page.",
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

  // onglets de la fiche rencontre — passés par variable, donc invisibles à un
  // simple grep de `t("…")` : les oublier laissait deux mots français au milieu
  // d'une page anglaise.
  "Le match": "The match", "Les équipes": "The teams", "La saison": "The season",

  // Les notes de méthode. Elles disent ce que la source sait et ce qu'elle
  // ignore : c'est la partie du site qu'un club lira le plus attentivement, et
  // la laisser en français serait pire que de ne pas l'écrire.
  "Buts et cartons à la minute où la source les situe. Domicile au-dessus de la ligne, extérieur au-dessous. Source : Sofascore, seule à nommer les buteurs de cette division.":
    "Goals and cards at the minute the source places them. Home above the line, away below. Source: Sofascore, the only one naming scorers in this division.",
  "Aucune statistique individuelle n'existe sur cette division : ni note, ni minutes jouées, ni arrêts du gardien. Un meilleur joueur ne se calcule donc pas. « D'après les buts » signale un doublé, seul cas où les chiffres tranchent ; « observé » veut dire que quelqu'un a regardé la rencontre. Un jugement n'est jamais présenté comme une mesure.":
    "No individual statistics exist for this division: no ratings, no minutes played, no goalkeeper saves. A standout player therefore cannot be computed. “From the goals” marks a brace, the only case where the figures decide on their own; “watched” means someone saw the match. A judgement is never presented as a measurement.",
  "Relevé de cette rencontre, pas de la saison. Source : Forebet — la seule à publier possession et tirs sur cette division. Les rubriques absentes ne sont pas à zéro : elles ne sont pas couvertes.":
    "Recorded for this match, not the season. Source: Forebet, the only one publishing possession and shots for this division. Missing rows are not zero: they are simply not covered.",
  "Chiffres de la saison entière, pas de cette rencontre. Chaque ligne est mise à l'échelle indépendamment : la longueur compare les deux équipes entre elles, pas une ligne à l'autre.":
    "Whole-season figures, not this match. Each row is scaled on its own: bar length compares the two teams with each other, never one row against another.",
  "Effectifs de la saison, pas les compositions du jour : aucune source ne publie de feuille de match pour ce championnat.":
    "Season squads, not the day's line-ups: no source publishes team sheets for this league.",
  "Effectif de la saison, pas une composition : aucune source ne publie de feuille de match sur cette division. Les buts sont la seule statistique individuelle qui existe — ni minutes, ni passes, ni notes. Source : Sofascore.":
    "Season squad, not a line-up: no source publishes team sheets for this division. Goals are the only individual statistic that exists — no minutes, no assists, no ratings. Source: Sofascore.",
  "Les buts sont la seule statistique individuelle publiée sur cette division : ni passes décisives, ni minutes jouées, ni notes. Source : Sofascore.":
    "Goals are the only individual statistic published for this division: no assists, no minutes played, no ratings. Source: Sofascore.",
  "Bilans de saison agrégés par Sofascore. Ce sont les seules statistiques par club qu'aucune autre source ne donne : matchs sans encaisser, buts sur penalty, cartons rouges. Ni tirs ni possession — cette source ne les a nulle part sur cette division.":
    "Season records aggregated by Sofascore. These are the only per-club figures no other source provides: clean sheets, penalty goals, red cards. No shots and no possession — this source has neither anywhere in this division.",
  "La saison entière vient de Sofascore ; la fenêtre récente est complétée par Forebet et Flashscore, qui apportent la fiche détaillée. Les rencontres marquées « ? » n'ont pas d'hôte arbitré : les sources se contredisent sur qui reçoit, et on ne tranche pas sans une deuxième qui confirme.":
    "The full season comes from Sofascore; the recent window is completed by Forebet and Flashscore, which bring the detailed match page. Fixtures marked “?” have no arbitrated host: the sources disagree on who is at home, and we do not decide without a second one confirming.",

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
