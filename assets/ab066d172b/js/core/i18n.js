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
  "Rencontre en cours, relevée toutes les minutes.":
    "Match in progress, recorded every minute.",
  "Minute relevée à la source, au dernier relevé — pas un chronomètre.":
    "Minute as reported by the source at the last reading — not a running clock.",
  // L'horloge du direct. Abrégés des deux côtés : ils tiennent dans le
  // marqueur, à côté du point rouge.
  "MT": "HT", "t.a.b.": "pens", "susp.": "susp.", "retardé": "delayed",
  "score incertain": "score uncertain",
  "Composition": "Line-up", "Titulaires": "Starting XI",
  "Remplaçants": "Substitutes", "Capitaine": "Captain", "Gardien": "Goalkeeper",
  "Support": "Published on",
  "Publié par le club comme": "Published by the club as",
  "Ce joueur ne figure dans aucune fiche : la source ne l'a pas.":
    "This player has no profile: the source does not list him.",
  "Fournie par le club, pas relevée : aucune source automatique ne publie de feuille de match sur cette division. Ce document est le visuel d'avant-match du club, lu et apparié à la main.":
    "Supplied by the club, not recorded: no automatic source publishes team sheets for this division. This is the club's pre-match graphic, read and matched by hand.",
  "Il donne donc le onze et le banc, jamais les changements — on n'en tire aucune minute jouée.":
    "It therefore gives the eleven and the bench, never the substitutions — no minutes played can be derived from it.",
  "joueur(s) n'ont pas de fiche : la source ne les connaît pas, ils sont nommés sans lien.":
    "player(s) have no profile: the source does not know them, so they are named without a link.",
  "Effectifs de la saison, pas la composition du jour — celle-ci est plus haut, telle que le club l'a publiée.":
    "Season squads, not the day's line-up — that is above, as the club published it.",
  "sans poste connu": "with no known position",
  "Le terrain range les joueurs par poste, il ne montre pas un dispositif : le poste vient de la fiche générale du joueur, pas de son rôle ce soir-là, et rien n'indique qui jouait à gauche ou à droite — la place dans une ligne est celle de la feuille.":
    "The pitch groups players by position, it does not show a formation: the position comes from the player's general profile, not from his role that night, and nothing says who played left or right — the place within a line is the one on the team sheet.",
  "Le club publie les rôles : le dispositif et les côtés sont les siens, pas une déduction de la page. Ils valent pour le coup d'envoi — rien ici ne dit comment l'équipe s'est replacée ensuite.":
    "The club publishes the roles: the formation and the flanks are its own, not something this page inferred. They describe the kick-off — nothing here says how the side shifted afterwards.",
  "Un seul des deux clubs publie les rôles de ses joueurs : de ce côté-là le dispositif et les côtés sont les siens, au coup d'envoi. En face, le terrain range simplement par poste de fiche et ne dit ni le rôle du soir, ni qui jouait à gauche.":
    "Only one of the two clubs publishes its players' roles: on that side the formation and the flanks are the club's own, at kick-off. Opposite, the pitch merely groups players by profile position and says neither the night's role nor who played left.",
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

  // page joueur
  "Ce joueur n'existe pas": "No such player",
  "Âge": "Age", "ans": "years", "Taille": "Height", "Pied fort": "Preferred foot",
  "Gauche": "Left", "Droit": "Right", "Les deux": "Both",
  "Buts cette saison": "Goals this season", "Valeur estimée": "Estimated value",
  "Profil de buteur": "Scoring profile", "Quand il marque": "When he scores",
  "Contre qui": "Against whom", "minutes": "minutes",
  "Dont penaltys": "Of which penalties",
  "Premier but": "First goal", "Dernier but": "Last goal",
  "Carrière": "Career", "Date": "Date", "De": "From", "Vers": "To",
  "Indemnité": "Fee", "Compétitions traversées": "Competitions played in",
  "Gardien": "Goalkeeper", "Défenseur": "Defender",
  "Défenseur central": "Centre-back", "Latéral gauche": "Left-back",
  "Latéral droit": "Right-back", "Milieu défensif": "Defensive midfielder",
  "Milieu": "Midfielder", "Milieu central": "Central midfielder",
  "Milieu gauche": "Left midfielder", "Milieu droit": "Right midfielder",
  "Milieu offensif": "Attacking midfielder", "Attaquant": "Forward",
  "Avant-centre": "Striker", "Ailier gauche": "Left winger",
  "Ailier droit": "Right winger",
  "Identité, poste détaillé et valeur estimée : Sofascore. La valeur est une estimation de la source, pas un montant de transaction.":
    "Identity, detailed position and estimated value: Sofascore. The value is the source's estimate, not a transaction amount.",
  "Calculé par nous, à partir de la chronologie de chaque rencontre : la source ne publie que le total de buts. Ni minutes jouées, ni tirs, ni notes n'existent sur cette division — cette page n'en invente pas.":
    "Computed by us from each match timeline: the source publishes only a goal total. No minutes played, no shots and no ratings exist for this division — this page invents none.",
  "Les championnats où la source lui connaît des statistiques. Cela ne dit ni le nombre de matchs ni les buts hors de cette division.":
    "The leagues where the source has statistics for him. It says nothing about appearances or goals outside this division.",
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
  "Relevé pendant la rencontre, une fois par minute, par le serveur qui sert cette page — jamais par le navigateur. La minute affichée en haut vient d'un second point d'entrée de la même source, et date du dernier relevé : elle ne défile pas toute seule. Il arrive que la source réattribue un but d'un camp à l'autre en début de rencontre, et le relevé est alors marqué incertain.":
    "Recorded during the match, once a minute, by the server hosting this page — never by the browser. The clock shown above comes from a second endpoint of the same source and dates from the last reading: it does not tick on its own. The source sometimes moves a goal from one side to the other early on, and the reading is then flagged as uncertain.",
  "Relevé pendant la rencontre, une fois par minute, par le serveur qui sert cette page — jamais par le navigateur. La source ne donne pas la minute de jeu sur cette rencontre : ces chiffres disent où en est le match, pas depuis combien de temps. Il arrive aussi qu'elle réattribue un but d'un camp à l'autre en début de rencontre, et le relevé est alors marqué incertain.":
    "Recorded during the match, once a minute, by the server hosting this page — never by the browser. The source does not give the clock for this match: these figures say where the match stands, not how long it has been going. It also sometimes moves a goal from one side to the other early on, and the reading is then flagged as uncertain.",
  "Chiffres de la saison entière, pas de cette rencontre. Chaque ligne est mise à l'échelle indépendamment : la longueur compare les deux équipes entre elles, pas une ligne à l'autre.":
    "Whole-season figures, not this match. Each row is scaled on its own: bar length compares the two teams with each other, never one row against another.",
  "Effectifs de la saison, pas les compositions du jour : aucune source ne publie de feuille de match pour ce championnat.":
    "Season squads, not the day's line-ups: no source publishes team sheets for this league.",
  "Effectif de la saison, pas une composition : aucune source ne publie de feuille de match sur cette division. Les buts sont la seule statistique individuelle qui existe — ni minutes, ni passes, ni notes. Source : Sofascore.":
    "Season squad, not a line-up: no source publishes team sheets for this division. Goals are the only individual statistic that exists — no minutes, no assists, no ratings. Source: Sofascore.",
  "Les buts sont la seule statistique individuelle publiée sur cette division : ni passes décisives, ni minutes jouées, ni notes. Source : Sofascore.":
    "Goals are the only individual statistic published for this division: no assists, no minutes played, no ratings. Source: Sofascore.",
  "Ce classement est celui de la compétition, pas la somme des effectifs : un joueur qui a quitté son club en cours de saison y garde ses buts. Un nom sans lien est un joueur dont la fiche n'existe pas.":
    "This is the competition's own ranking, not the sum of the squads: a player who left his club mid-season keeps his goals here. A name without a link is a player with no profile page.",
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
