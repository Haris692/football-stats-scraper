/* Les huit clubs. Une grille, pas un rail : huit tient à l'écran, et un rail
   qui ne défile presque pas donne l'impression qu'il manque quelque chose. */

import { el, append } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { teams, nameOf } from "../core/data.js";
import { crestOf, methodNote } from "../components/pieces.js";
import { clubCard } from "../components/cards.js";

function comparison() {
  const rows = teams()
    .filter(c => c.season && c.season.matches)
    .sort((a, b) => (b.season.goals_scored || 0) - (a.season.goals_scored || 0));
  if (!rows.length) return null;

  return el("section", { class: "page section" }, [
    el("h2", { text: t("Le championnat en un coup d'œil") }),
    methodNote(t("Bilans de saison agrégés par Sofascore. Ce sont les seules " +
      "statistiques par club qu'aucune autre source ne donne : matchs sans " +
      "encaisser, buts sur penalty, cartons rouges. Ni tirs ni possession — " +
      "cette source ne les a nulle part sur cette division.")),
    el("div", { class: "card", style: { marginTop: "var(--s-4)" } }, [
      el("div", { class: "table__wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: t("Équipe") }),
            el("th", { class: "n", text: t("Joués") }),
            el("th", { class: "n", text: t("Buts pour") }),
            el("th", { class: "n", text: t("Buts contre") }),
            el("th", { class: "n", text: t("Matchs sans encaisser") }),
            el("th", { class: "n", text: t("Buts sur penalty") }),
            el("th", { class: "n", text: t("Cartons rouges") }),
          ])]),
          el("tbody", {}, rows.map(c => el("tr", {}, [
            el("td", {}, [
              el("a", { class: "team-chip", href: `club.html?c=${encodeURIComponent(c.key)}` }, [
                crestOf(c.key, "sm"),
                el("span", { class: "truncate", text: nameOf(c.key) }),
              ]),
            ]),
            el("td", { class: "n", text: c.season.matches ?? "—" }),
            el("td", { class: "n", text: c.season.goals_scored ?? "—" }),
            el("td", { class: "n", text: c.season.goals_conceded ?? "—" }),
            el("td", { class: "n num", text: c.season.clean_sheets ?? "—" }),
            el("td", { class: "n", text: c.season.penalty_goals ?? "—" }),
            el("td", { class: "n", text: c.season.red_cards ?? "—" }),
          ]))),
        ]),
      ]),
    ]),
  ]);
}

boot(async host => {
  document.title = `${t("Les clubs")} — ${t("Division 1 koweïtienne")}`;
  append(host, [
    el("section", { class: "page section" }, [
      el("div", { class: "eyebrow", text: t("Division 1 koweïtienne") }),
      el("h1", { text: t("Les clubs"), style: { marginBlock: "var(--s-2) var(--s-5)" } }),
      el("div", { class: "grid-cards" }, teams().map(c => clubCard(c.key))),
    ]),
    comparison(),
  ]);
});
