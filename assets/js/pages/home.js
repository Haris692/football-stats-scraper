/* L'accueil. Un club koweïtien qui ouvre ce lien doit comprendre en une
   seconde de quoi il s'agit : une rencontre en grand, avec son score. Pas un
   tableau de bord, pas un menu, pas une grille de widgets. */

import { el, append } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import {
  site, featured, played, upcoming, teams, scorers, standings,
  nameOf, seasonTotals, match as matchOf,
} from "../core/data.js";
import { crestOf, badge, clubColor, stat } from "../components/pieces.js";
import { fixtureCard, clubCard, scorerCard } from "../components/cards.js";
import { railOrGrid } from "../components/rail.js";

function heroSide(key) {
  const row = (standings() || []).find(r => r.team === nameOf(key));
  return el("div", { class: "hero__team" }, [
    crestOf(key, "xl"),
    el("div", { class: "hero__name", text: nameOf(key) }),
    row ? el("div", { class: "hero__rank",
                      text: `${row.rank}ᵉ · ${row.points} pts` }) : null,
  ]);
}

function hero(f) {
  if (!f) return null;
  const detail = f.match_id ? matchOf(f.match_id) : null;
  const score = (f.score || "").split(/\s*-\s*/);

  const centre = f.score
    ? el("div", { class: "hero__score" }, [
        el("span", { text: score[0] }),
        el("span", { class: "sep", text: "–" }),
        el("span", { text: score[1] }),
      ])
    : el("div", { class: "hero__kick", text: (f.kickoff || "").split(" ")[1] || "—" });

  // Sous le score, la ligne des buteurs : c'est ce que Sofascore nous apporte
  // et que personne d'autre n'a sur cette division. Elle fait la différence
  // entre « 2-2 » et une rencontre dont on a envie de lire le détail.
  const goals = (detail?.timeline || []).filter(e => e.type === "goal");
  const line = goals.length ? el("div", { class: "hero__line" },
    goals.map(g => el("span", {}, [
      el("b", { text: g.player || nameOf(g.side === "home" ? f.home_key : f.away_key) }),
      ` ${g.minute}${g.added ? "+" + g.added : ""}'`,
    ]))) : null;

  return el("section", { class: "hero" }, [
    el("div", { class: "page hero__in" }, [
      el("div", { class: "hero__meta" }, [
        el("span", { class: "eyebrow", text: t("À la une") }),
        f.round ? badge(t("Journée") + " " + f.round) : null,
        badge((f.kickoff || "").split(" ")[0]),
        f.live ? badge("LIVE", "live") : null,
      ]),
      el("div", { class: "hero__grid" }, [
        heroSide(f.home_key), centre, heroSide(f.away_key),
      ]),
      line,
      el("div", { class: "hero__cta" }, [
        f.match_id ? el("a", { class: "btn btn--primary",
                               href: `match.html?id=${f.match_id}`,
                               text: t("Voir la rencontre") }) : null,
        el("a", { class: "btn", href: "classement.html", text: t("Classement") }),
      ]),
    ]),
  ]);
}

function miniTable() {
  const rows = standings();
  if (!rows.length) return null;
  const body = rows.map(r => {
    const key = teams().find(c => c.name === r.team)?.key;
    return el("tr", {}, [
      el("td", { class: "rank", text: r.rank }),
      el("td", {}, [
        el("a", { class: "team-chip", href: `club.html?c=${encodeURIComponent(key)}` }, [
          crestOf(key, "sm"),
          el("span", { class: "truncate", text: r.team }),
        ]),
      ]),
      el("td", { class: "n", text: r.played }),
      el("td", { class: "n num", text: r.points }),
    ]);
  });
  return el("section", { class: "page section" }, [
    el("div", { class: "rail__head", style: { paddingInline: "0" } }, [
      el("h2", { text: t("Classement") }),
      el("a", { class: "rail__more", href: "classement.html",
                text: t("Tout voir") + " ›" }),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "table__wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "#" }), el("th", { text: t("Équipe") }),
            el("th", { class: "n", text: "J" }), el("th", { class: "n", text: "Pts" }),
          ])]),
          el("tbody", {}, body),
        ]),
      ]),
    ]),
  ]);
}

function strip() {
  const s = seasonTotals();
  return el("section", { class: "page section" }, [
    el("div", { class: "eyebrow", style: { marginBottom: "var(--s-4)" },
                text: t("Le championnat en un coup d'œil") }),
    el("div", { class: "stats-strip" }, [
      stat(t("rencontres jouées"), s.matches),
      stat(t("buts marqués"), s.goals),
      stat(t("moyenne par match"), s.average.toFixed(2)),
      stat(t("clubs"), s.clubs),
    ]),
  ]);
}

boot(async host => {
  const s = site();
  document.title = `${t("Division 1 koweïtienne")} — ${s.season || ""}`.trim();

  const next = upcoming().slice(0, 10);
  const last = played().slice(0, 10);

  append(host, [
    hero(featured()),
    strip(),
    railOrGrid("Derniers résultats", last.map(fixtureCard),
               { more: "calendrier.html" }),
    railOrGrid("Prochaines rencontres", next.map(fixtureCard),
               { more: "calendrier.html" }),
    railOrGrid("Meilleurs buteurs",
               scorers().slice(0, 12).map((r, i) => scorerCard(r, i + 1)),
               { more: "classement.html#buteurs" }),
    railOrGrid("Les clubs", teams().map(c => clubCard(c.key)),
               { more: "clubs.html" }),
    miniTable(),
  ]);
}, { rows: 4 });
