/* Le rail : une rangée qui défile latéralement, avec accroche et flèches.

   C'est l'emprunt assumé aux plateformes vidéo, et il ne tient que parce qu'on
   a de quoi le remplir — 84 rencontres, 8 clubs, 50 buteurs. Un rail de trois
   cartes serait une grille déguisée : `railOrGrid()` bascule tout seul.

   Le défilement clavier et tactile marche sans les flèches ; les flèches ne
   sont là que pour la souris, qui n'a rien d'autre. */

import { el, qs } from "../core/dom.js";
import { t } from "../core/i18n.js";

const MIN_FOR_RAIL = 4;

export function rail(title, cards, { more, moreLabel } = {}) {
  if (!cards.length) return null;

  const track = el("div", { class: "rail__track scroller" }, cards);
  const prev = el("button", {
    class: "rail__arrow rail__arrow--prev", type: "button",
    "aria-label": "←", text: "‹", hidden: true,
  });
  const next = el("button", {
    class: "rail__arrow rail__arrow--next", type: "button",
    "aria-label": "→", text: "›",
  });

  const step = () => track.clientWidth * 0.8;
  prev.addEventListener("click", () => track.scrollBy({ left: -step(), behavior: "smooth" }));
  next.addEventListener("click", () => track.scrollBy({ left: step(), behavior: "smooth" }));

  // Une flèche qui ne mène nulle part est un mensonge : on les cache aux bouts.
  const sync = () => {
    const max = track.scrollWidth - track.clientWidth - 2;
    prev.hidden = track.scrollLeft <= 2;
    next.hidden = track.scrollLeft >= max;
  };
  track.addEventListener("scroll", sync, { passive: true });
  new ResizeObserver(sync).observe(track);

  return el("section", { class: "rail section" }, [
    el("div", { class: "rail__head" }, [
      el("h2", { text: t(title) }),
      more ? el("a", { class: "rail__more", href: more,
                       text: t(moreLabel || "Tout voir") + " ›" }) : null,
    ]),
    el("div", { style: { position: "relative" } }, [prev, track, next]),
  ]);
}

/** Sous quatre cartes, une grille se lit mieux qu'un rail : rien à faire
 *  défiler, tout est déjà là. */
export function railOrGrid(title, cards, opts = {}) {
  if (!cards.length) return null;
  if (cards.length >= MIN_FOR_RAIL) return rail(title, cards, opts);
  return el("section", { class: "section page" }, [
    el("div", { class: "rail__head", style: { paddingInline: "0" } }, [
      el("h2", { text: t(title) }),
      opts.more ? el("a", { class: "rail__more", href: opts.more,
                            text: t(opts.moreLabel || "Tout voir") + " ›" }) : null,
    ]),
    el("div", { class: "grid-cards" }, cards),
  ]);
}
