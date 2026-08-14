/* Le onze sur un terrain.
 *
 * Ce fichier connaît DEUX qualités de feuille, et ne montre jamais l'une pour
 * l'autre.
 *
 * ── Quand le club publie les rôles du jour (`role` : GK, RB, CAM, LW…) ──
 * Alors le dispositif et les côtés sont de la DONNÉE, pas une déduction : le
 * club les a écrits. Le terrain les suit, et la suite affichée est la sienne
 * (« 4-2-3-1 »). C'est arrivé pour la première fois le 14/08/2026, avec la
 * feuille de Sulaibikhat pour la J19.
 *
 * ── Sinon, et c'est le cas ordinaire ──
 * ⚠️ CE N'EST PAS UN DISPOSITIF, et le reste du fichier est construit pour ne
 * jamais laisser croire le contraire. Trois choses n'existent pas dans la
 * donnée, et aucune ne doit être inventée par le dessin :
 *
 *   1. **Le rôle du jour.** Le poste vient de la fiche générale du joueur chez
 *      Sofascore. Cinq « défenseurs » peuvent être une défense à trois avec
 *      deux pistons — on montre combien il y en a, jamais comment ils
 *      jouaient.
 *   2. **Le côté.** Rien ne dit qui était latéral gauche. L'ordre horizontal
 *      dans une ligne est donc celui de la feuille du club, arbitraire, et la
 *      note de la carte le dit.
 *   3. **Le poste des inconnus.** Un joueur que la source ne connaît pas n'a
 *      pas de poste. Il n'est PAS placé quelque part au jugé : il va dans une
 *      bande nommée, sous le terrain. Sept joueurs placés et quatre à côté,
 *      ça a l'air incomplet — ça l'est, et le maquiller serait le mensonge.
 *
 * Ce que le dessin dit de vrai, en revanche, aucune source ne le publie :
 * Sulaibikhat a commencé sa rencontre du 11/08/2026 avec cinq défenseurs.
 *
 * ⚠️ Le basculement est TOUT OU RIEN : il suffit qu'un seul titulaire n'ait
 * pas de rôle reconnu pour que la feuille entière retombe sur les postes
 * Sofascore. Un onze à moitié placé par le club et à moitié par la fiche
 * n'aurait aucune lecture — et serait le genre de faux crédible que ce projet
 * redoute le plus.
 */

import { el } from "../core/dom.js";
import { t } from "../core/i18n.js";

/* Du gardien vers l'attaque : c'est le sens de lecture d'une composition, et
   il place le but en bas, là où l'œil l'attend. */
const LINES = ["G", "D", "M", "F"];

/* Les rôles tels que les clubs les écrivent, rangés en cinq lignes du but vers
   l'attaque. Une table explicite, jamais une analyse de la chaîne : un rôle
   inconnu doit faire retomber la feuille sur les postes Sofascore, pas être
   deviné par un `startsWith("L")` complaisant.

   `x` ordonne la ligne de la gauche vers la droite de l'écran. On regarde le
   terrain depuis le but de l'équipe : le latéral GAUCHE est donc à gauche,
   comme sur les visuels des clubs. */
const ROLES = {
  GK: [0, 0], G: [0, 0],

  LB: [1, -2], LWB: [1, -2], LCB: [1, -1], CB: [1, 0], SW: [1, 0],
  RCB: [1, 1], RB: [1, 2], RWB: [1, 2],

  LM: [2, -2], LCM: [2, -1], CDM: [2, 0], DM: [2, 0], CM: [2, 0],
  RCM: [2, 1], RM: [2, 2],

  LW: [3, -2], LAM: [3, -1], CAM: [3, 0], AM: [3, 0], RAM: [3, 1],
  RW: [3, 2],

  LS: [4, -1], ST: [4, 0], CF: [4, 0], SS: [4, 0], RS: [4, 1],
};

/* Vrai si TOUS les titulaires portent un rôle connu — la seule condition qui
   autorise le terrain à montrer un dispositif. */
function published(starters) {
  return starters.length > 0
    && starters.every(p => Object.prototype.hasOwnProperty.call(ROLES, p.role || ""));
}

/* Les lignes du club, du but vers l'attaque, chacune triée de gauche à droite.
   Le tri est stable : deux rôles de même abscisse — les deux CB d'une défense
   à quatre — gardent l'ordre de la feuille, faute de mieux. */
function byRole(starters) {
  const lines = [[], [], [], [], []];
  starters.forEach((p, i) => {
    const [line, x] = ROLES[p.role];
    lines[line].push({ p, x, i });
  });
  return lines.map(l =>
    l.sort((a, b) => a.x - b.x || a.i - b.i).map(o => o.p));
}

/* Le nom sur une pastille doit tenir en une ligne, et surtout DÉSIGNER
   quelqu'un. Ne garder que la fin ne suffit pas : sur cette division les noms
   de famille se répètent énormément — Sulaibikhat aligne « Saleh Khamees Al
   Enezi » et « Musaed Al Enezi » dans le même onze, et deux pastilles lisant
   « Al Enezi » ne distinguent personne.

   D'où l'initiale du prénom, puis la partie qui identifie : à partir du « Al »
   quand il y en a un, le dernier mot sinon. « S. Al Enezi » et « M. Al Enezi »
   se lisent d'un coup d'œil. Un nom de deux mots est déjà court, on n'y touche
   pas. */
function short(name) {
  const parts = (name || "").trim().split(/\s+/);
  if (parts.length <= 2) return name;
  const al = parts.findIndex((w, i) => i > 0 && /^al$/i.test(w));
  const tail = al > 0 ? parts.slice(al) : [parts[parts.length - 1]];
  return `${parts[0][0]}. ${tail.join(" ")}`;
}

function chip(p) {
  const body = [
    el("span", { class: "pitch__no", text: p.number || "—" }),
    el("span", { class: "pitch__name", text: short(p.name) }),
    p.captain ? el("span", { class: "pitch__c", text: "C", title: t("Capitaine") }) : null,
  ];
  // Même règle que la liste : un joueur sans fiche n'a pas de lien, et rien
  // dans son apparence ne suggère qu'il y a quelque chose à cliquer.
  return p.id
    ? el("a", { class: "pitch__p", href: `joueur.html?p=${p.id}` }, body)
    : el("span", { class: "pitch__p pitch__p--flat",
                   title: t("Ce joueur ne figure dans aucune fiche : la source ne l'a pas.") },
        body);
}

/** Le terrain d'un onze. Rend `null` s'il n'y a personne à placer. */
export function pitch(starters = []) {
  // Le club a écrit son onze : on le dessine tel quel, personne à côté.
  if (published(starters)) {
    return el("div", { class: "pitch" }, [
      el("div", { class: "pitch__field" },
        [...byRole(starters)].reverse().map(line =>
          line.length ? el("div", { class: "pitch__line" }, line.map(chip)) : null)),
    ]);
  }

  const known = LINES.map(k => starters.filter(p => p.position === k));
  const unknown = starters.filter(p => !LINES.includes(p.position));
  if (!known.some(l => l.length) && !unknown.length) return null;

  return el("div", { class: "pitch" }, [
    el("div", { class: "pitch__field" }, [
      // Dessiné dans l'ordre inverse : la ligne d'attaque en haut du terrain,
      // le gardien en bas. Une ligne vide disparaît — un rang de zéro joueur
      // occuperait de la hauteur pour ne rien dire.
      ...[...LINES].reverse().map((k, i) => {
        const line = known[LINES.length - 1 - i];
        return line.length
          ? el("div", { class: "pitch__line" }, line.map(chip))
          : null;
      }),
    ]),
    unknown.length ? el("div", { class: "pitch__off" }, [
      el("div", { class: "pitch__off-label",
                  text: `${unknown.length} ${t("sans poste connu")}` }),
      el("div", { class: "pitch__line" }, unknown.map(chip)),
    ]) : null,
  ]);
}

/** La suite des lignes, ou `null` si un poste manque.
 *
 *  Deux écritures, parce que ce sont deux choses différentes :
 *
 *  · Le club a publié les rôles → son dispositif, à sa convention, SANS le
 *    gardien : « 4-2-3-1 ». Les lignes vides sautent, sinon un 4-4-2 se lirait
 *    « 4-4-0-2 ».
 *  · Sinon → le compte des postes de fiche, gardien COMPRIS : « 1-5-2-3 ».
 *    Ce n'est pas un dispositif et le nombre de tirets le dit déjà ; la note
 *    de méthode de la carte l'écrit en toutes lettres.
 *
 *  ⚠️ Volontairement `null` dès qu'un seul joueur n'a pas de poste : une somme
 *  qui ne fait pas onze se lirait comme un dispositif, et un « 1-2-2-2 » à
 *  sept joueurs serait faux deux fois. */
export function shapeOf(starters = []) {
  if (published(starters)) {
    return byRole(starters).slice(1).filter(l => l.length)
      .map(l => l.length).join("-");
  }
  if (!starters.length || starters.some(p => !LINES.includes(p.position))) return null;
  return LINES.map(k => starters.filter(p => p.position === k).length).join("-");
}

/** Vrai si le dispositif affiché est celui que le club a publié.
 *
 *  Exporté pour la note de méthode : la carte affirme « le terrain ne montre
 *  pas un dispositif », ce qui devient FAUX dès qu'une feuille porte les
 *  rôles. Une note qui contredit le dessin juste au-dessus d'elle est pire que
 *  pas de note du tout. */
export function hasRoles(starters = []) {
  return published(starters);
}
