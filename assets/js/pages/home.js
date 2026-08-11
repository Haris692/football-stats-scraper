/* L'accueil. Un club koweïtien qui ouvre ce lien doit comprendre en une
   seconde de quoi il s'agit : une rencontre en grand, avec son score. Pas un
   tableau de bord, pas un menu, pas une grille de widgets. */

import { el, append } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import {
  site, headline, played, upcoming, teams, scorers, standings,
  nameOf, seasonTotals, isLive, match as matchOf,
} from "../core/data.js";
import { crestOf, badge, clubColor, stat, liveMark } from "../components/pieces.js";
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

/** La ligne des buteurs d'une rencontre. C'est ce que Sofascore nous apporte et
 *  que personne d'autre n'a sur cette division : elle fait la différence entre
 *  « 2-2 » et une rencontre dont on a envie de lire le détail. */
function scorerLine(f, cls) {
  const detail = f.match_id ? matchOf(f.match_id) : null;
  const goals = (detail?.timeline || []).filter(e => e.type === "goal");
  if (!goals.length) return null;
  return el("div", { class: cls }, goals.map(g => el("span", {}, [
    el("b", { text: g.player || nameOf(g.side === "home" ? f.home_key : f.away_key) }),
    ` ${g.minute}${g.added ? "+" + g.added : ""}'`,
  ])));
}

/* Le centre d'une affiche : le score si on l'a, l'heure sinon. Une rencontre en
   cours porte le marqueur « live » JUSTE AU-DESSUS de son heure — c'est là que
   l'œil va chercher quand le match a commencé. */
const centrePiece = (f, cls) => {
  const score = (f.score || "").split(/\s*-\s*/);
  if (f.score) {
    return el("div", { class: cls.score }, [
      el("span", { text: score[0] }),
      el("span", { class: "sep", text: "–" }),
      el("span", { text: score[1] }),
    ]);
  }
  return el("div", { class: "kick-stack" }, [
    isLive(f) ? liveMark() : null,
    el("div", { class: cls.kick, text: (f.kickoff || "").split(" ")[1] || "—" }),
  ]);
};

/** Une rencontre seule : elle prend toute la une. */
function heroSolo(f) {
  return [
    el("div", { class: "hero__grid" }, [
      heroSide(f.home_key),
      centrePiece(f, { score: "hero__score", kick: "hero__kick" }),
      heroSide(f.away_key),
    ]),
    scorerLine(f, "hero__line"),
    el("div", { class: "hero__cta" }, [
      f.match_id ? el("a", { class: "btn btn--primary",
                             href: `match.html?id=${f.match_id}`,
                             text: t("Voir la rencontre") }) : null,
      el("a", { class: "btn", href: "classement.html", text: t("Classement") }),
    ]),
  ];
}

/** Plusieurs rencontres le même soir — le cas normal ici : une journée de cette
 *  division en compte deux à quatre. Chacune garde un panneau entier, cliquable
 *  d'un bout à l'autre ; aucune n'est reléguée. */
function heroPanel(f) {
  const side = key => el("div", { class: "hmatch__side" }, [
    crestOf(key, "lg"),
    el("div", { class: "hmatch__name", text: nameOf(key) }),
  ]);
  const inner = [
    el("div", { class: "hmatch__top" }, [
      // L'heure n'apparaît ici que si le centre porte déjà un score. Sur une
      // rencontre à venir, le centre EST l'heure : l'écrire deux fois la
      // faisait lire comme deux informations différentes.
      f.score ? el("span", { class: "mono", text: (f.kickoff || "").split(" ")[1] || "" }) : null,
      f.score ? badge(t("Score final")) : isLive(f) ? null : badge(t("À venir")),
    ]),
    el("div", { class: "hmatch__grid" }, [
      side(f.home_key),
      centrePiece(f, { score: "hmatch__score", kick: "hmatch__kick" }),
      side(f.away_key),
    ]),
    scorerLine(f, "hmatch__line"),
  ];
  return f.match_id
    ? el("a", { class: "hmatch", href: `match.html?id=${f.match_id}` }, inner)
    : el("div", { class: "hmatch" }, inner);
}

const HEADLINE = {
  today: "Aujourd'hui",
  next: "Prochaine journée",
  last: "Dernière journée",
};

function hero(group) {
  if (!group.fixtures.length) return null;
  const list = group.fixtures;
  const first = list[0];

  return el("section", { class: "hero" }, [
    el("div", { class: "page hero__in" }, [
      el("div", { class: "hero__meta" }, [
        el("span", { class: "eyebrow", text: t(HEADLINE[group.kind] || "À la une") }),
        first.round ? badge(t("Journée") + " " + first.round) : null,
        badge((first.kickoff || "").split(" ")[0]),
        list.some(isLive) ? badge("LIVE", "live") : null,
      ]),
      ...(list.length === 1
        ? heroSolo(first)
        : [el("div", { class: "hero__matches" }, list.map(heroPanel))]),
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
    hero(headline()),
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
