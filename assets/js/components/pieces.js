/* Les petites pièces réutilisées partout : écusson, puce de club, pastille,
   note de méthode. Chacune est écrite une fois et jamais recopiée — c'est ce
   qui fait qu'un club a la même tête sur les six pages. */

import { el } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { crest, team, nameOf } from "../core/data.js";

/** L'écusson d'un club. L'emplacement est réservé à la bonne taille AVANT que
 *  l'image n'arrive : `crests.json` est chargé après le reste, et rien ne doit
 *  sauter quand il se pose. */
export function crestOf(key, size = "") {
  const src = crest(key);
  const cls = "crest" + (size ? ` crest--${size}` : "");
  if (src) {
    return el("img", { class: cls, src, alt: "", loading: "lazy", decoding: "async" });
  }
  const box = el("span", {
    class: `${cls} crest--none`,
    "aria-hidden": "true",
    text: (nameOf(key) || "?").slice(0, 2).toUpperCase(),
  });
  // Quand les écussons finissent par arriver, on remplace la pastille.
  document.addEventListener("crests", () => {
    const late = crest(key);
    if (late) box.replaceWith(el("img", { class: cls, src: late, alt: "", loading: "lazy" }));
  }, { once: true });
  return box;
}

/** Un club cliquable : écusson + nom. Le lien va toujours vers sa fiche. */
export function clubChip(key, { size = "", link = true, bold = true } = {}) {
  const inner = [crestOf(key, size), el("span", {
    class: "team-chip__name truncate" + (bold ? "" : " muted"),
    text: nameOf(key),
  })];
  return link
    ? el("a", { class: "team-chip", href: `club.html?c=${encodeURIComponent(key)}` }, inner)
    : el("span", { class: "team-chip" }, inner);
}

export const badge = (text, variant) =>
  el("span", { class: "badge" + (variant ? ` badge--${variant}` : ""), text });

export const dot = side => el("span", { class: `dot dot--${side}` });

/** La note de méthode d'un bloc, repliée. Le site dit ce qu'il sait, d'où ça
 *  vient et ce qui manque — mais à la demande. Déplié partout, il y aurait plus
 *  de commentaire que de données. */
export function methodNote(text) {
  return el("details", { class: "note" }, [
    el("summary", { text: t("Méthode") }),
    el("p", { text }),
  ]);
}

/** La couleur d'un club, pour un liseré et rien d'autre.
 *  ⚠️ Jamais dans un graphique : deux clubs peuvent partager une teinte, et une
 *  couleur de club peut être blanche ou quasi noire. Les barres restent
 *  bleu/orange, qui portent domicile et extérieur, pas l'identité. */
export const clubColor = key => (team(key)?.colors || [])[0] || null;

/** Un chiffre avec son étiquette. La brique de tous les blocs de statistiques
 *  du site : même hiérarchie partout, valeur d'abord, libellé ensuite. */
export function stat(label, value, note) {
  return el("div", { class: "stat" }, [
    el("div", { class: "stat__v num", text: value === null || value === undefined ? "—" : String(value) }),
    el("div", { class: "stat__l", text: label }),
    note ? el("div", { class: "stat__n", text: note }) : null,
  ]);
}
