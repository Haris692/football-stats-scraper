/* Le onze sur un terrain.
 *
 * ⚠️ CE N'EST PAS UN DISPOSITIF, et tout ce fichier est construit pour ne
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
 */

import { el } from "../core/dom.js";
import { t } from "../core/i18n.js";

/* Du gardien vers l'attaque : c'est le sens de lecture d'une composition, et
   il place le but en bas, là où l'œil l'attend. */
const LINES = ["G", "D", "M", "F"];

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

/** La suite des lignes, « 1-5-2-3 », ou `null` si un poste manque.
 *
 *  ⚠️ Volontairement `null` dès qu'un seul joueur n'a pas de poste : une somme
 *  qui ne fait pas onze se lirait comme un dispositif, et un « 1-2-2-2 » à
 *  sept joueurs serait faux deux fois. */
export function shapeOf(starters = []) {
  if (!starters.length || starters.some(p => !LINES.includes(p.position))) return null;
  return LINES.map(k => starters.filter(p => p.position === k).length).join("-");
}
