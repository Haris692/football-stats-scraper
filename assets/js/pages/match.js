/* La fiche d'une rencontre.

   Le générateur de brief Instagram n'est PAS ici : c'est un outil de
   production, il reste dans `console.html`. Un site public montre le match,
   pas la chaîne éditoriale qui sert à en parler. */

import { el, append, param, qsa } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { match as matchOf, team, nameOf, fixtures } from "../core/data.js";
import { crestOf, badge, dot, methodNote } from "../components/pieces.js";

const LABELS = {
  possession: "Possession", shots: "Tirs", shots_on: "Tirs cadrés",
  shots_off: "Tirs non cadrés", corners: "Corners", yellow: "Cartons jaunes",
  red: "Cartons rouges", substitutions: "Remplacements", goals: "Buts",
};
const GROUPS = [
  ["Attaque", ["goals", "shots", "shots_on", "shots_off"]],
  ["Jeu", ["corners", "substitutions"]],
  ["Discipline", ["yellow", "red"]],
];
const GOAL_LABEL = {
  "goal/regular": "But", "goal/penalty": "But sur penalty",
  "goal/ownGoal": "But contre son camp",
  "card/yellow": "Carton jaune", "card/red": "Carton rouge",
  "card/yellowRed": "Second jaune",
};

const stamp = e => `${e.minute}${e.added ? "+" + e.added : ""}`;
const minuteOf = e => (e.minute || 0) + (e.added || 0);

/* ------------------------------------------------------------ le bandeau */

function boardSide(m, side) {
  const key = side === "home" ? m.home_key : m.away_key;
  // Le classement de l'ANNUAIRE, pas celui figé dans la fiche : chaque page
  // Forebet embarque la table à sa date, et deux fiches voisines n'affichaient
  // donc pas le même rang pour le même club.
  const row = team(key)?.standing;
  return el("a", {
    class: `board__team board__team--${side}`,
    href: `club.html?c=${encodeURIComponent(key)}`,
  }, [
    crestOf(key, "lg"),
    el("div", { style: { minWidth: 0 } }, [
      el("div", { class: "board__name truncate", text: nameOf(key) }),
      row ? el("div", { class: "muted", style: { fontSize: "var(--t--1)" },
                        text: `${row.rank}ᵉ · ${row.points} pts` }) : null,
    ]),
  ]);
}

function board(m, fx) {
  const score = (fx?.score || m.match_stats?.full_time || "").split(/\s*[-–]\s*/);
  const centre = score.length === 2
    ? el("div", { class: "board__score" }, [
        el("span", { text: score[0] }), el("span", { class: "sep", text: "–" }),
        el("span", { text: score[1] }),
      ])
    : el("div", { class: "board__score",
                  text: (m.kickoff || "").split(" ")[1] || "—" });

  return el("div", { class: "board" }, [
    el("div", { class: "page board__in" }, [
      el("div", { class: "board__line" },
        [boardSide(m, "home"), centre, boardSide(m, "away")]),
      el("div", { class: "board__meta" }, [
        el("span", { text: m.kickoff }),
        m.round ? el("span", { text: `${t("Journée")} ${m.round}` }) : null,
        m.match_stats?.venue ? el("span", { text: m.match_stats.venue }) : null,
        fx?.live ? badge("LIVE", "live") : null,
      ]),
    ]),
  ]);
}

/* ------------------------------------------------------- le fil du match */

function timeline(m) {
  const line = m.timeline || [];
  if (!line.length) return null;
  const end = Math.max(96, ...line.map(minuteOf));

  const track = el("div", { class: "tl__track" });
  for (let q = 15; q < end; q += 15) {
    if (q === 45) continue;
    track.append(el("div", { class: "tl__q", style: { left: `${q / end * 100}%` } }));
  }
  track.append(el("div", { class: "tl__half",
    style: { left: `${45 / end * 100}%` }, title: t("Mi-temps") }));

  // Deux buts trop proches écriraient leurs minutes l'une sur l'autre : on
  // garde la pastille, on lâche le chiffre, qui reste dans l'infobulle.
  const lastLabel = { home: -99, away: -99 };
  line.forEach(e => {
    const at = minuteOf(e);
    const mk = el("div", {
      class: `tl__mk tl__mk--${e.side}` +
        (e.type === "card" ? " tl__mk--card" : "") +
        (e.class === "red" ? " tl__mk--red" : ""),
      style: { left: `${at / end * 100}%` },
      title: [`${stamp(e)}'`, t(GOAL_LABEL[`${e.type}/${e.class}`] || e.type),
              e.player, nameOf(e.side === "home" ? m.home_key : m.away_key)]
        .filter(Boolean).join(" · "),
    }, [el("span", { class: "tl__pip" })]);
    if (e.type === "goal" && at - lastLabel[e.side] >= 5) {
      mk.append(el("span", { class: "tl__stamp" }, [
        `${stamp(e)}'`,
        e.score ? el("span", { class: "at", text: " " + e.score.replace("-", "–") }) : null,
      ]));
      lastLabel[e.side] = at;
    }
    track.append(mk);
  });

  const goals = line.filter(e => e.type === "goal");
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [el("h2", { text: t("Chronologie") })]),
    track,
    el("div", { class: "tl__scale" }, [
      el("span", { text: "0'" }), el("span", { text: "45'" }),
      el("span", { text: end > 96 ? "90+" : "90'" }),
    ]),
    goals.length ? el("div", { class: "tl__who" }, goals.map(g => el("span", {}, [
      dot(g.side),
      el("b", { text: g.player || nameOf(g.side === "home" ? m.home_key : m.away_key) }),
      ` ${stamp(g)}'`,
      g.class === "penalty" ? " (pén.)" : g.class === "ownGoal" ? " (csc)" : "",
    ]))) : null,
    methodNote(t("Buts et cartons à la minute où la source les situe. Domicile " +
      "au-dessus de la ligne, extérieur au-dessous. Source : Sofascore, seule à " +
      "nommer les buteurs de cette division.")),
  ]);
}

/* ------------------------------------------------------ l'homme du match */

function motm(m) {
  const picks = m.motm;
  if (!picks || (!picks.home && !picks.away)) return null;
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [el("h2", { text: t("Homme du match") })]),
    el("div", { class: "motm" }, ["home", "away"].map(side => {
      const p = picks[side];
      if (!p) return null;
      return el("div", { class: "motm__row" }, [
        dot(side),
        el("div", {}, [
          el("div", { class: "motm__head" }, [
            el("b", { text: p.player }),
            badge(p.source === "auto" ? t("d'après les buts") : t("observé"),
                  p.source === "auto" ? "flood" : null),
          ]),
          el("div", { class: "motm__why", text: p.why }),
        ]),
      ]);
    }).filter(Boolean)),
    methodNote(t("Aucune statistique individuelle n'existe sur cette division : " +
      "ni note, ni minutes jouées, ni arrêts du gardien. Un meilleur joueur ne " +
      "se calcule donc pas. « D'après les buts » signale un doublé, seul cas où " +
      "les chiffres tranchent ; « observé » veut dire que quelqu'un a regardé " +
      "la rencontre. Un jugement n'est jamais présenté comme une mesure.")),
  ]);
}

/* --------------------------------------------------- barres comparatives */

function bars(rows, { hint } = {}) {
  const grid = el("div", { class: "h2h" });
  for (const [label, h, a] of rows) {
    // L'intitulé de groupe passe EN PREMIER : il n'a ni valeur à gauche ni
    // valeur à droite, et le test des lignes vides l'avalerait.
    if (label instanceof Node) { grid.append(label); continue; }
    if ((h === null || h === undefined) && (a === null || a === undefined)) continue;
    const H = Number(h) || 0, A = Number(a) || 0;
    const max = Math.max(H, A) || 1;
    grid.append(
      el("span", { class: "h2h__v h2h__v--l", text: h ?? "—" }),
      el("span", { class: "h2h__bar h2h__bar--home" }, [
        el("span", { class: "h2h__fill h2h__fill--home", style: { width: `${H / max * 100}%` } }),
      ]),
      el("span", { class: "h2h__label", text: label }),
      el("span", { class: "h2h__bar" }, [
        el("span", { class: "h2h__fill h2h__fill--away", style: { width: `${A / max * 100}%` } }),
      ]),
      el("span", { class: "h2h__v", text: a ?? "—" }),
    );
  }
  return grid.children.length ? grid : null;
}

const group = label => el("div", { class: "h2h__group", text: label });

function matchStats(m) {
  const s = m.match_stats;
  if (!s) return null;

  const rows = [];
  for (const [title, keys] of GROUPS) {
    const present = keys.filter(k => (s.fields || []).includes(k) &&
      (s.home?.[k] !== null || s.away?.[k] !== null));
    if (!present.length) continue;
    rows.push([group(t(title))]);
    present.forEach(k => rows.push([t(LABELS[k] || k), s.home[k], s.away[k]]));
  }

  const poss = s.home?.possession != null ? el("div", {}, [
    el("div", { class: "poss__row" }, [
      el("span", { text: `${s.home.possession} %` }),
      el("span", { class: "muted", text: t("Possession") }),
      el("span", { text: `${s.away.possession} %` }),
    ]),
    el("div", { class: "poss" }, [
      el("span", { style: { width: `${s.home.possession}%` } }),
      el("span", { style: { width: `${s.away.possession}%` } }),
    ]),
  ]) : null;

  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("h2", { text: t("Statistiques du match") }),
      s.half_time ? badge(`${t("Mi-temps")} ${s.half_time}`) : null,
    ]),
    poss,
    el("div", { style: { marginTop: "var(--s-5)" } }, [bars(rows)]),
    methodNote(t("Relevé de cette rencontre, pas de la saison. Source : Forebet " +
      "— la seule à publier possession et tirs sur cette division. Les " +
      "rubriques absentes ne sont pas à zéro : elles ne sont pas couvertes.")),
  ]);
}

/* ------------------------------------------------------------- comparatif */

function compare(m) {
  const H = m.stats?.home || {}, A = m.stats?.away || {};
  const others = m.stats?.others || {};
  const pick = (label, k) => [t(label), others[k]?.home?.total, others[k]?.away?.total];

  const rows = [
    [group(t("Attaque"))],
    [t("Buts"), H.goals?.scored, A.goals?.scored],
    [t("Tirs"), H.shots?.total, A.shots?.total],
    [group(t("Défense"))],
    [t("Buts contre"), H.goals?.conceded, A.goals?.conceded],
  ];
  if (others["Corners"]) rows.push([group(t("Jeu"))], pick("Corners", "Corners"));

  const hs = team(m.home_key)?.season, as = team(m.away_key)?.season;
  if (hs || as) {
    rows.push([group(t("Bilan de saison") || "Bilan de saison")]);
    rows.push([t("Matchs sans encaisser"), hs?.clean_sheets, as?.clean_sheets]);
    rows.push([t("Buts sur penalty"), hs?.penalty_goals, as?.penalty_goals]);
  }

  const grid = bars(rows);
  if (!grid) return null;
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("h2", { text: t("Comparatif") }),
      el("span", { class: "muted", style: { fontSize: "var(--t--1)" } }, [
        dot("home"), " " + nameOf(m.home_key) + "  ", dot("away"), " " + nameOf(m.away_key),
      ]),
    ]),
    grid,
    methodNote(t("Chiffres de la saison entière, pas de cette rencontre. Chaque " +
      "ligne est mise à l'échelle indépendamment : la longueur compare les deux " +
      "équipes entre elles, pas une ligne à l'autre.")),
  ]);
}

/* ------------------------------------------------------------- face à face */

function h2h(m) {
  const block = (m.result_blocks || []).find(b => /face/i.test(b.title || ""));
  if (!block?.matches?.length) return null;
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [el("h2", { text: t("Face à face") })]),
    el("div", { class: "table__wrap" }, [
      el("table", { class: "table" }, [
        el("tbody", {}, block.matches.map(r => el("tr", {}, [
          el("td", { class: "mono", style: { color: "var(--text-3)" }, text: r.date }),
          el("td", { class: "truncate", text: r.home }),
          el("td", { class: "n num", text: r.score }),
          el("td", { class: "truncate", text: r.away }),
        ]))),
      ]),
    ]),
  ]);
}

/* ---------------------------------------------------------------- effectifs */

const POS = { G: "Gardiens", D: "Défenseurs", M: "Milieux", F: "Attaquants" };

function squadCol(key) {
  const c = team(key);
  const players = c?.players || [];
  if (!players.length) return null;
  const groups = {};
  players.forEach(p => {
    const k = ["G", "D", "M", "F"].includes(p.position) ? p.position : "?";
    (groups[k] = groups[k] || []).push(p);
  });
  return el("div", {}, [
    el("div", { style: { display: "flex", gap: "var(--s-2)", alignItems: "center",
                         marginBottom: "var(--s-3)" } }, [
      crestOf(key, "sm"), el("b", { text: nameOf(key) }),
    ]),
    c.manager ? el("div", { class: "muted", style: { fontSize: "var(--t--1)",
                    marginBottom: "var(--s-3)" }, text: `${t("Entraîneur")} : ${c.manager}` }) : null,
    ...["G", "D", "M", "F", "?"].filter(k => groups[k]).flatMap(k => [
      el("div", { class: "squad__grp", text: t(POS[k] || "Poste inconnu") }),
      ...groups[k].map(p => el("div", { class: "player" }, [
        el("span", { class: "player__no", text: p.number || "—" }),
        el("span", { class: "player__n truncate", text: p.name }),
        p.goals ? el("span", { class: "player__g", text: p.goals }) : null,
      ])),
    ]),
  ]);
}

function squads(m) {
  const cols = [squadCol(m.home_key), squadCol(m.away_key)].filter(Boolean);
  if (!cols.length) return null;
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [el("h2", { text: t("Effectifs") })]),
    methodNote(t("Effectifs de la saison, pas les compositions du jour : aucune " +
      "source ne publie de feuille de match pour ce championnat.")),
    el("div", { class: "squad", style: { marginTop: "var(--s-5)" } }, cols),
  ]);
}

/* --------------------------------------------------------------- onglets */

const TABS = [["match", "Le match"], ["equipes", "Les équipes"]];

function tabs(panels) {
  let current = "match";
  try { current = localStorage.getItem("kd1-tab") || "match"; } catch (e) {}
  if (!TABS.some(([id]) => id === current)) current = "match";

  const show = name => {
    current = name;
    try { localStorage.setItem("kd1-tab", name); } catch (e) {}
    qsa("[data-panel]").forEach(p => { p.hidden = p.dataset.panel !== name; });
    qsa(".tab").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  };

  const bar = el("div", { class: "tabs", role: "tablist" }, TABS.map(([id, label]) =>
    el("button", {
      class: "tab", type: "button", role: "tab", data: { tab: id },
      "aria-selected": String(id === current), text: t(label),
      onClick: () => show(id),
      onKeydown: ev => {
        const step = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
        if (!step) return;
        ev.preventDefault();
        const ids = TABS.map(([x]) => x);
        const next = ids[(ids.indexOf(id) + step + ids.length) % ids.length];
        show(next);
        document.querySelector(`.tab[data-tab="${next}"]`).focus();
      },
    })));

  for (const [id, parts] of Object.entries(panels)) {
    panels[id] = el("div", {
      class: "stack", role: "tabpanel", data: { panel: id },
      hidden: id !== current,
      style: { paddingTop: "var(--s-5)" },
    }, parts.filter(Boolean));
  }
  return [bar, ...Object.values(panels)];
}

/* ------------------------------------------------------------------ page */

boot(async host => {
  const m = matchOf(param("id"));
  if (!m) {
    append(host, el("section", { class: "page section" }, [
      el("div", { class: "empty" }, [
        el("h3", { text: t("Cette rencontre n'existe pas") }),
        el("a", { class: "btn btn--primary", href: "calendrier.html", text: t("Calendrier") }),
      ]),
    ]));
    return;
  }
  const fx = fixtures().find(f => f.match_id === m.match_id);
  document.title = `${nameOf(m.home_key)} – ${nameOf(m.away_key)} · ${t("Division 1 koweïtienne")}`;

  const line = timeline(m);
  const stats = matchStats(m);
  const nothing = !line && !stats ? el("div", { class: "empty" }, [
    el("h3", { text: t("Pas encore joué") }),
    el("p", { text: `${t("Journée")} ${m.round || "—"} · ${m.kickoff}` }),
  ]) : null;

  append(host, [
    board(m, fx),
    el("div", { class: "page section" },
      tabs({
        match: [line, stats, motm(m), nothing],
        equipes: [compare(m), h2h(m), squads(m)],
      })),
  ]);
}, { rows: 3 });
