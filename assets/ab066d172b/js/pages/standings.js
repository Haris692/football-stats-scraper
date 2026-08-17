/* Le classement, et les buteurs.

   ⚠️ Le championnat koweïtien départage à la CONFRONTATION DIRECTE, pas à la
   différence de buts. L'ordre affiché est celui de la source, qui applique
   cette règle ; on ne retrie jamais côté page — un tri par différence de buts
   donnerait un classement faux et crédible, le pire des deux. */

import { el, append } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { standings, scorers, teams, nameOf, site } from "../core/data.js";
import { crestOf, badge, methodNote } from "../components/pieces.js";

const keyOf = name => teams().find(c => c.name === name)?.key;

function table() {
  const rows = standings();
  if (!rows.length) return null;
  const last = rows.length;

  return el("section", { class: "page section" }, [
    el("div", { class: "eyebrow", text: t("Division 1 koweïtienne") }),
    el("h1", { text: t("Classement"), style: { marginBlock: "var(--s-2) var(--s-3)" } }),
    el("p", { class: "lede",
      text: t("Le championnat départage à la confrontation directe, pas à la différence de buts.") }),
    el("div", { class: "card", style: { marginTop: "var(--s-5)" } }, [
      el("div", { class: "table__wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "#" }), el("th", { text: t("Équipe") }),
            el("th", { class: "n", text: "J" }),
            el("th", { class: "n", text: "V" }),
            el("th", { class: "n", text: "N" }),
            el("th", { class: "n", text: "D" }),
            el("th", { class: "n", text: t("Buts pour") }),
            el("th", { class: "n", text: t("Buts contre") }),
            el("th", { class: "n", text: "+/-" }),
            el("th", { class: "n", text: "Pts" }),
          ])]),
          el("tbody", {}, rows.map(r => {
            const k = keyOf(r.team);
            const diff = (r.goals_for ?? 0) - (r.goals_against ?? 0);
            return el("tr", {
              data: { zone: r.rank === 1 ? "up" : r.rank === last ? "down" : null },
            }, [
              el("td", { class: "rank", text: r.rank }),
              el("td", {}, [
                el("a", { class: "team-chip", href: `club.html?c=${encodeURIComponent(k)}` }, [
                  crestOf(k, "sm"), el("span", { class: "truncate", text: r.team }),
                ]),
              ]),
              el("td", { class: "n", text: r.played }),
              el("td", { class: "n", text: r.wins }),
              el("td", { class: "n", text: r.draws }),
              el("td", { class: "n", text: r.losses }),
              el("td", { class: "n", text: r.goals_for }),
              el("td", { class: "n", text: r.goals_against }),
              el("td", { class: "n", text: (diff > 0 ? "+" : "") + diff }),
              el("td", { class: "n num", text: r.points }),
            ]);
          })),
        ]),
      ]),
    ]),
  ]);
}

function scorerTable() {
  const rows = scorers();
  if (!rows.length) return null;
  return el("section", { class: "page section", id: "buteurs" }, [
    el("h2", { text: t("Meilleurs buteurs") }),
    methodNote(t("Les buts sont la seule statistique individuelle publiée sur " +
      "cette division : ni passes décisives, ni minutes jouées, ni notes. " +
      "Source : Sofascore.") + " " +
      t("Ce classement est celui de la compétition, pas la somme des " +
        "effectifs : un joueur qui a quitté son club en cours de saison y " +
        "garde ses buts. Un nom sans lien est un joueur dont la fiche " +
        "n'existe pas.")),
    el("div", { class: "card", style: { marginTop: "var(--s-4)" } }, [
      el("div", { class: "table__wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "#" }), el("th", { text: t("Joueur") || "Joueur" }),
            el("th", { text: t("Équipe") }), el("th", { class: "n", text: t("Buts") }),
          ])]),
          el("tbody", {}, rows.map((r, i) => el("tr", {}, [
            el("td", { class: "rank", text: i + 1 }),
            el("td", {}, [
              // Pas de fiche, pas de lien : `id` n'est renseigné que si la
              // page du joueur existe (voir `scorer_board`).
              r.id ? el("a", { href: `joueur.html?p=${r.id}`, text: r.name })
                   : el("span", { text: r.name }),
              r.country_code ? el("span", { style: { marginInlineStart: "var(--s-2)" } },
                                   [badge(r.country_code)]) : null,
            ]),
            el("td", {}, [
              el("a", { class: "team-chip", href: `club.html?c=${encodeURIComponent(r.team)}` }, [
                crestOf(r.team, "sm"),
                el("span", { class: "truncate", text: nameOf(r.team) }),
              ]),
            ]),
            el("td", { class: "n num", text: r.goals }),
          ]))),
        ]),
      ]),
    ]),
  ]);
}

boot(async host => {
  document.title = `${t("Classement")} — ${t("Division 1 koweïtienne")}`;
  append(host, [table(), scorerTable()]);
  // Un lien vers #buteurs doit atterrir sous la barre collante, pas dessous.
  if (location.hash) {
    const target = document.querySelector(location.hash);
    if (target) target.scrollIntoView();
  }
});
