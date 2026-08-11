/* Les cartes qui peuplent les rails : une rencontre, un club, un buteur.
   Toutes cliquables, toutes de la même famille, toutes atteignables au clavier
   parce que ce sont de vrais liens et pas des `div` avec un `onclick`. */

import { el } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { nameOf, team } from "../core/data.js";
import { crestOf, badge, clubColor } from "./pieces.js";

const parseScore = s => {
  const [h, a] = String(s || "").split(/\s*-\s*/).map(Number);
  return Number.isFinite(h) && Number.isFinite(a) ? [h, a] : null;
};

/** Une rencontre. Jouée, elle montre le score et efface le perdant d'un cran ;
 *  à venir, elle montre l'heure. La même carte dans les deux cas — c'est ce qui
 *  permet de mélanger passé et futur dans un même rail sans que ça sursaute. */
export function fixtureCard(f) {
  const score = parseScore(f.score);
  const side = (key, value, lost) => el("div", {
    class: "fixture__side" + (lost ? " fixture__side--lost" : ""),
  }, [
    crestOf(key, "sm"),
    el("span", { class: "name truncate", text: nameOf(key) }),
    el("span", { class: "score", text: value }),
  ]);

  const top = [
    el("span", { text: (f.kickoff || "").split(" ")[0] }),
    f.round ? badge("J" + f.round) : null,
  ];
  if (f.live) top.push(badge("LIVE", "live"));

  const body = score
    ? [
        side(f.home_key, score[0], score[0] < score[1]),
        side(f.away_key, score[1], score[1] < score[0]),
      ]
    : [
        side(f.home_key, "", false),
        side(f.away_key, "", false),
      ];

  const foot = score
    ? el("div", { class: "fixture__foot" }, [
        el("span", { text: t("Voir la rencontre") + " ›" }),
      ])
    : el("div", { class: "fixture__foot" }, [
        el("span", { class: "fixture__kick",
                     text: (f.kickoff || "").split(" ")[1] || "—" }),
      ]);

  const href = f.match_id
    ? `match.html?id=${f.match_id}`
    : `calendrier.html#${(f.kickoff_iso || "").slice(0, 10)}`;

  return el("a", { class: "fixture", href }, [
    el("div", { class: "fixture__top" }, top),
    ...body,
    foot,
  ]);
}

/** Un club. Le liseré du haut prend sa couleur d'écusson — c'est le seul
 *  endroit du site où la couleur d'un club sert, et elle n'y code rien
 *  d'analytique, juste une identité. */
export function clubCard(key) {
  const c = team(key);
  const rank = c?.standing;
  return el("a", {
    class: "club", href: `club.html?c=${encodeURIComponent(key)}`,
    style: clubColor(key) ? { "--club": clubColor(key) } : {},
  }, [
    crestOf(key, "lg"),
    el("div", { class: "club__name truncate", text: nameOf(key) }),
    el("div", { class: "club__meta", text: rank
      ? `${rank.rank}ᵉ · ${rank.points} pts`
      : `${(c?.players || []).length} ${t("joueurs")}` }),
  ]);
}

/** Un buteur. Le rang est écrit : dans un rail, on perd sinon le fait qu'il
 *  s'agit d'un classement et pas d'une liste. */
export function scorerCard(row, rank) {
  return el("a", {
    class: "fixture", style: { width: "230px" },
    href: `club.html?c=${encodeURIComponent(row.team)}`,
  }, [
    el("div", { class: "fixture__top" }, [
      el("span", { class: "num", text: `#${rank}` }),
      row.country_code ? badge(row.country_code) : null,
    ]),
    el("div", { class: "scorer" }, [
      el("div", { class: "scorer__g num", text: row.goals }),
      el("div", {}, [
        el("div", { class: "scorer__n truncate", text: row.name }),
        el("div", { class: "club__meta truncate", text: nameOf(row.team) }),
      ]),
    ]),
    el("div", { class: "fixture__foot" }, [
      el("span", { text: t("Voir le club") + " ›" }),
    ]),
  ]);
}
