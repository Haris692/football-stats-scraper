/* La fiche d'une rencontre.

   Le générateur de brief Instagram n'est PAS ici : c'est un outil de
   production, il reste dans `console.html`. Un site public montre le match,
   pas la chaîne éditoriale qui sert à en parler. */

import { el, append, param, qsa } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { match as matchOf, team, nameOf, fixtures, isLive } from "../core/data.js";
import { crestOf, badge, dot, methodNote, liveMark } from "../components/pieces.js";
import { watchLive, liveBlock, liveStamp } from "../core/live.js";

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

function board(m, fx, live) {
  // Le relevé en direct passe AVANT le score figé : sur une rencontre en cours
  // `fx.score` est vide, et sur une rencontre finie il n'y a pas de relevé.
  const running = live && live.home?.goals != null && live.away?.goals != null;
  const score = running
    ? [String(live.home.goals), String(live.away.goals)]
    : (fx?.score || m.match_stats?.full_time || "").split(/\s*[-–]\s*/);

  const board__score = el("div", { class: "board__score" }, [
    el("span", { text: score[0] }), el("span", { class: "sep", text: "–" }),
    el("span", { text: score[1] }),
  ]);
  const centre = running
    // En direct, le marqueur reste au-dessus du score : c'est lui qui dit que
    // le chiffre du dessous va encore bouger.
    ? el("div", { class: "kick-stack" }, [liveMark(true), board__score])
    : score.length === 2
      ? board__score
      : el("div", { class: "kick-stack" }, [
          fx && isLive(fx) ? liveMark() : null,
          el("div", { class: "board__score",
                      text: (m.kickoff || "").split(" ")[1] || "—" }),
        ]);

  return el("div", { class: "board" }, [
    el("div", { class: "page board__in" }, [
      el("div", { class: "board__line" },
        [boardSide(m, "home"), centre, boardSide(m, "away")]),
      el("div", { class: "board__meta" }, [
        el("span", { text: m.kickoff }),
        m.round ? el("span", { text: `${t("Journée")} ${m.round}` }) : null,
        m.match_stats?.venue ? el("span", { text: m.match_stats.venue }) : null,

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

function matchStats(m, live, stamp) {
  // Le relevé du serveur l'emporte sur celui figé dans les données : il est
  // forcément plus récent, et sur une rencontre en cours c'est le seul.
  const s = live || m.match_stats;
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
      live ? badge(stamp ? `${t("Direct")} · ${stamp}` : t("Direct"), "live") : null,
      live && live.unstable ? badge(t("score incertain"), "flood") : null,
      s.half_time ? badge(`${t("Mi-temps")} ${s.half_time}`) : null,
    ]),
    poss,
    el("div", { style: { marginTop: "var(--s-5)" } }, [bars(rows)]),
    live
      // Deux choses à dire, et la seconde est la plus importante : ce relevé
      // n'a PAS de minute de jeu. La source n'en publie pas, et laisser croire
      // qu'un « direct » sait où en est le match serait le tromper.
      ? methodNote(t("Relevé pendant la rencontre, une fois par minute, par le " +
          "serveur qui sert cette page — jamais par le navigateur. La source ne " +
          "donne ni la minute de jeu ni le statut : ces chiffres disent où en " +
          "est le match, pas depuis combien de temps. Il arrive aussi qu'elle " +
          "réattribue un but d'un camp à l'autre en début de rencontre, et le " +
          "relevé est alors marqué incertain."))
      : methodNote(t("Relevé de cette rencontre, pas de la saison. Source : Forebet " +
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
      ...groups[k].map(p => el("a", {
        class: "player", href: `joueur.html?p=${p.id}`,
      }, [
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
  // La note change de sens dès qu'un club a fourni sa feuille : dire « aucune
  // source ne publie de composition » sous une composition affichée plus haut
  // se contredirait. Ce qui reste vrai dans les deux cas, c'est que CETTE
  // carte-ci montre la saison, pas le jour.
  const sheet = m.lineups && (m.lineups.home || m.lineups.away);
  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [el("h2", { text: t("Effectifs") })]),
    methodNote(sheet
      ? t("Effectifs de la saison, pas la composition du jour — celle-ci est " +
          "plus haut, telle que le club l'a publiée.")
      : t("Effectifs de la saison, pas les compositions du jour : aucune " +
          "source ne publie de feuille de match pour ce championnat.")),
    el("div", { class: "squad", style: { marginTop: "var(--s-5)" } }, cols),
  ]);
}

/* ---------------------------------------------------- compositions du jour */

/* Une ligne de feuille de match. Le nom affiché est celui du site — pour qu'un
   joueur porte le même nom partout — mais quand le club l'écrit autrement,
   l'infobulle garde sa version : c'est SA feuille.

   ⚠️ Un joueur sans `id` n'est pas une erreur d'appariement à corriger : il
   peut manquer chez Sofascore. Il s'affiche alors sans lien, jamais rapproché
   d'un homonyme au jugé. */
function sheetLine(p) {
  const inner = [
    el("span", { class: "player__no", text: p.number || "—" }),
    el("span", { class: "player__n truncate", text: p.name }),
    p.captain ? el("span", { class: "sheet__mark", text: "C",
                             title: t("Capitaine") }) : null,
    p.position === "G" ? el("span", { class: "sheet__mark", text: "G",
                                      title: t("Gardien") }) : null,
  ];
  const title = p.as_published && p.as_published !== p.name
    ? `${t("Publié par le club comme")} : ${p.as_published}` : null;
  return p.id
    ? el("a", { class: "player", href: `joueur.html?p=${p.id}`, title }, inner)
    : el("span", { class: "player player--flat", title:
        title || t("Ce joueur ne figure dans aucune fiche : la source ne l'a pas.") },
        inner);
}

/* `titled` : l'en-tête de colonne ne sert qu'à séparer deux feuilles. Quand un
   seul club a fourni la sienne, le badge de la carte le nomme déjà, et répéter
   l'écusson trois centimètres plus bas ne dit rien de neuf. */
function sheetCol(side, sheet, titled) {
  const starters = sheet.starters || [], subs = sheet.subs || [];
  if (!starters.length && !subs.length) return null;
  return el("div", {}, [
    titled ? el("div", { style: { display: "flex", gap: "var(--s-2)", alignItems: "center",
                         marginBottom: "var(--s-3)" } }, [
      crestOf(sheet.club, "sm"), el("b", { text: nameOf(sheet.club) }),
    ]) : null,
    starters.length ? el("div", { class: "squad__grp", text: t("Titulaires") }) : null,
    // L'ordre est celui du visuel du club, gardien d'abord : c'est ainsi qu'une
    // feuille se lit. Ne pas re-trier par poste, on perdrait l'information.
    ...starters.map(sheetLine),
    subs.length ? el("div", { class: "squad__grp", style: { marginTop: "var(--s-4)" },
                              text: t("Remplaçants") }) : null,
    ...subs.map(sheetLine),
  ]);
}

function lineups(m) {
  const sheets = m.lineups || {};
  const sides = ["home", "away"].filter(s => sheets[s]);
  const cols = sides
    .map(s => sheetCol(s, sheets[s], sides.length > 1)).filter(Boolean);
  if (!cols.length) return null;

  // La provenance n'est pas un ornement : c'est la seule chose qui distingue
  // une feuille de match d'une liste inventée. Elle nomme le club, le support,
  // et elle dit ce que le document NE contient pas.
  const src = ["home", "away"].map(s => sheets[s]?.source).filter(Boolean);
  const who = [...new Set(src.map(o => o.by).filter(Boolean))].join(" · ");
  const media = [...new Set(src.map(o => o.medium).filter(Boolean))].join(" · ");
  const unmatched = ["home", "away"].flatMap(s =>
    [...(sheets[s]?.starters || []), ...(sheets[s]?.subs || [])])
    .filter(p => !p.id).length;

  return el("section", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("h2", { text: t("Composition") }),
      who ? badge(who, "club") : null,
    ]),
    methodNote(
      `${t("Fournie par le club, pas relevée : aucune source automatique ne " +
           "publie de feuille de match sur cette division. Ce document est le " +
           "visuel d'avant-match du club, lu et apparié à la main.")}` +
      ` ${t("Il donne donc le onze et le banc, jamais les changements — on " +
            "n'en tire aucune minute jouée.")}` +
      (media ? ` ${t("Support")} : ${media}.` : "") +
      (unmatched ? ` ${unmatched} ${t("joueur(s) n'ont pas de fiche : la " +
        "source ne les connaît pas, ils sont nommés sans lien.")}` : "")),
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
  const nothing = () => el("div", { class: "empty" }, [
    el("h3", { text: t("Pas encore joué") }),
    el("p", { text: `${t("Journée")} ${m.round || "—"} · ${m.kickoff}` }),
  ]);

  /* Deux emplacements que le direct redessine, et eux seuls. Re-construire la
     page entière toutes les quinze secondes ferait sauter l'onglet choisi, la
     position de lecture et la sélection de texte — pour un chiffre qui bouge
     une fois par heure. */
  const boardSlot = el("div", {}, [board(m, fx)]);
  const statsSlot = el("div", { class: "stack" },
    [matchStats(m) || (line ? null : nothing())].filter(Boolean));

  append(host, [
    boardSlot,
    el("div", { class: "page section" },
      tabs({
        match: [line, statsSlot, motm(m)],
        // La composition passe devant les effectifs de saison : quand elle
        // existe, c'est elle qu'on vient chercher.
        equipes: [lineups(m), compare(m), h2h(m), squads(m)],
      })),
  ]);

  // Servi par `serve.py`, le score et les statistiques se mettent à jour tout
  // seuls. Publié sur GitHub Pages, `watchLive` ne trouve pas son point
  // d'entrée et il ne se passe simplement rien — c'est voulu.
  watchLive(() => {
    const live = liveBlock(m.match_id);
    if (!live) return;
    boardSlot.replaceChildren(board(m, fx, live));
    statsSlot.replaceChildren(matchStats(m, live, liveStamp()));
  }, { fixtures: fx ? [fx] : [] });
}, { rows: 3 });
