/* La fiche d'un club : son bilan, son effectif, ses rencontres.
   Adressée par `club.html?c=<clé>` — une clé, pas un nom : les sources écrivent
   « Yarmouk (KUW) », « Yarmouk SC » et « Yarmouk », et une URL doit survivre à
   ça. */

import { el, append, param } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { team, nameOf, seasonOf, outcome } from "../core/data.js";
import { crestOf, badge, clubColor, stat, methodNote } from "../components/pieces.js";
import { fixtureCard } from "../components/cards.js";

const POS = { G: "Gardiens", D: "Défenseurs", M: "Milieux", F: "Attaquants" };
const ORDER = ["G", "D", "M", "F", "?"];

function notFound(host) {
  append(host, el("section", { class: "page section" }, [
    el("div", { class: "empty" }, [
      el("h3", { text: t("Ce club n'existe pas") }),
      el("a", { class: "btn btn--primary", href: "clubs.html", text: t("Clubs") }),
    ]),
  ]));
}

function hero(c) {
  const r = c.standing;
  return el("section", {
    class: "club-hero",
    style: clubColor(c.key) ? { "--club": clubColor(c.key) } : {},
  }, [
    el("div", { class: "page club-hero__in" }, [
      crestOf(c.key, "xl"),
      el("div", { class: "club-hero__title" }, [
        el("div", { class: "eyebrow", text: t("Division 1 koweïtienne") }),
        el("h1", { text: nameOf(c.key) }),
        el("div", { class: "hero__line" }, [
          r ? el("span", {}, [el("b", { text: `${r.rank}ᵉ` }), ` · ${r.points} pts`]) : null,
          c.manager ? el("span", {}, [t("Entraîneur") + " : ", el("b", { text: c.manager })]) : null,
          c.city ? el("span", { text: c.city }) : null,
          el("span", {}, [el("b", { text: (c.players || []).length }), " " + t("joueurs")]),
        ]),
      ]),
    ]),
  ]);
}

function record(c) {
  const r = c.standing, s = c.season || {};
  if (!r && !s.matches) return null;
  return el("section", { class: "page section" }, [
    el("h2", { text: t("Carte d'identité") }),
    el("div", { class: "stats-strip", style: { marginTop: "var(--s-4)" } }, [
      r ? stat(t("Points"), r.points, `${r.played} ${t("Joués").toLowerCase()}`) : null,
      r ? stat(t("Victoires"), r.wins) : null,
      r ? stat(t("Nuls"), r.draws) : null,
      r ? stat(t("Défaites"), r.losses) : null,
      stat(t("Buts pour"), s.goals_scored ?? r?.goals_for),
      stat(t("Buts contre"), s.goals_conceded ?? r?.goals_against),
      s.clean_sheets !== undefined ? stat(t("Matchs sans encaisser"), s.clean_sheets) : null,
      s.penalty_goals !== undefined ? stat(t("Buts sur penalty"), s.penalty_goals) : null,
    ].filter(Boolean)),
  ]);
}

function squad(c) {
  const players = c.players || [];
  if (!players.length) return null;

  const groups = {};
  players.forEach(p => {
    const k = ORDER.includes(p.position) ? p.position : "?";
    (groups[k] = groups[k] || []).push(p);
  });

  return el("section", { class: "page section" }, [
    el("h2", { text: t("Effectif") }),
    methodNote(t("Effectif de la saison, pas une composition : aucune source ne " +
      "publie de feuille de match sur cette division. Les buts sont la seule " +
      "statistique individuelle qui existe — ni minutes, ni passes, ni notes. " +
      "Source : Sofascore.")),
    el("div", { class: "squad", style: { marginTop: "var(--s-5)" } },
      ORDER.filter(k => groups[k]).map(k => el("div", {}, [
        el("div", { class: "squad__grp", text: t(POS[k] || "Poste inconnu") }),
        ...groups[k].map(p => el("div", { class: "player" }, [
          el("span", { class: "player__no", text: p.number || "—" }),
          el("span", { class: "player__n truncate", text: p.name || "?" }),
          p.country_code ? badge(p.country_code) : null,
          p.goals ? el("span", { class: "player__g", text: p.goals }) : null,
        ])),
      ]))),
  ]);
}

function matches(c) {
  const all = seasonOf(c.key);
  const done = all.filter(f => f.played).reverse();   // plus récent d'abord
  const next = all.filter(f => !f.played);

  const form = done.slice(0, 6).map(f => {
    const r = outcome(f, c.key);
    return el("span", {
      class: "badge",
      style: r === "V" ? { color: "var(--good)", borderColor: "var(--good)" }
           : r === "D" ? { color: "var(--bad)", borderColor: "var(--bad)" } : {},
      text: r || "—",
    });
  });

  const block = (title, list) => list.length ? el("div", { class: "section" }, [
    el("div", { class: "rail__head", style: { paddingInline: "0" } }, [
      el("h2", { text: t(title) }),
    ]),
    el("div", { class: "grid-cards" }, list.map(r => fixtureCard({
      ...r, kickoff_iso: r.iso, match_id: r.match_id,
    }))),
  ]) : null;

  return el("section", { class: "page" }, [
    form.length ? el("div", { class: "section" }, [
      el("div", { class: "eyebrow", text: t("Parcours") }),
      el("div", { style: { display: "flex", gap: "var(--s-2)", marginTop: "var(--s-3)" } }, form),
    ]) : null,
    block("Résultats", done),
    block("Prochaines rencontres", next),
  ]);
}

boot(async host => {
  const c = team(param("c"));
  if (!c) return notFound(host);
  document.title = `${nameOf(c.key)} — ${t("Division 1 koweïtienne")}`;
  append(host, [hero(c), record(c), matches(c), squad(c)]);
});
