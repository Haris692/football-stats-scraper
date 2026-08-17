/* La fiche d'un joueur.

   ⚠️ **Ce n'est pas Football Manager, et la page ne fait pas semblant.**
   Aucune source ne publie de note, de minutes jouées, de passes, de tacles ni
   de heatmap sur cette division — tous ces endpoints répondent 404, vérifié le
   11/08/2026. Il n'y aura donc jamais de radar à cinq axes ici, et en inventer
   un à partir des buts serait une décoration qui ment.

   Ce que la page a de vrai, en revanche, aucun autre site ne l'a rassemblé :
   l'identité complète (âge, taille, pied fort, poste détaillé), la **valeur
   marchande**, la **carrière club par club**, les compétitions traversées — et
   un **profil de buteur que nous calculons nous-mêmes** depuis nos 195 buts
   datés : à quelle minute il marque, sa part de penaltys, contre qui. */

import { el, append, param } from "../core/dom.js";
import { t, lang } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { players, player, nameOf, team } from "../core/data.js";
import { crestOf, badge, methodNote, stat, photoOf } from "../components/pieces.js";

const POSITIONS = {
  G: "Gardien", GK: "Gardien",
  D: "Défenseur", DC: "Défenseur central", DL: "Latéral gauche",
  DR: "Latéral droit", DM: "Milieu défensif",
  M: "Milieu", MC: "Milieu central", ML: "Milieu gauche", MR: "Milieu droit",
  AM: "Milieu offensif", F: "Attaquant", ST: "Avant-centre",
  LW: "Ailier gauche", RW: "Ailier droit",
};
const FEET = { Left: "Gauche", Right: "Droit", Both: "Les deux" };

const money = (v, cur) => v
  ? new Intl.NumberFormat(lang === "en" ? "en-GB" : "fr-FR",
      { style: "currency", currency: cur || "EUR", maximumFractionDigits: 0 }).format(v)
  : null;

function notFound(host) {
  append(host, el("section", { class: "page section" }, [
    el("div", { class: "empty" }, [
      el("h3", { text: t("Ce joueur n'existe pas") }),
      el("a", { class: "btn btn--primary", href: "clubs.html", text: t("Clubs") }),
    ]),
  ]));
}

function hero(p) {
  const club = team(p.club);
  const poste = (p.positions || [])[0] || p.position;
  return el("section", { class: "club-hero" }, [
    el("div", { class: "page club-hero__in" }, [
      photoOf(p, "xl"),
      el("div", { class: "club-hero__title" }, [
        el("a", { class: "eyebrow", href: `club.html?c=${encodeURIComponent(p.club)}`,
                  text: club ? nameOf(p.club) : "" }),
        el("h1", { text: p.name }),
        // Le nom arabe vient de la source. Il n'est pas décoratif : ce
        // championnat est koweïtien, et c'est sous ce nom-là que le joueur est
        // connu chez lui.
        p.name_ar ? el("div", { class: "player__ar", dir: "rtl", text: p.name_ar }) : null,
        el("div", { class: "hero__line" }, [
          poste ? el("span", {}, [el("b", { text: t(POSITIONS[poste] || poste) })]) : null,
          p.number ? el("span", { text: `n° ${p.number}` }) : null,
          p.age ? el("span", {}, [el("b", { text: p.age }), " " + t("ans")]) : null,
          p.country ? el("span", { text: p.country }) : null,
        ]),
      ]),
    ]),
  ]);
}

function identity(p) {
  const tiles = [
    p.age ? stat(t("Âge"), p.age, p.birth ? p.birth.slice(0, 10).split("-").reverse().join("/") : null) : null,
    p.height ? stat(t("Taille"), `${p.height} cm`) : null,
    p.foot ? stat(t("Pied fort"), t(FEET[p.foot] || p.foot)) : null,
    stat(t("Buts cette saison"), p.goals_season ?? 0),
    p.market_value ? stat(t("Valeur estimée"),
                          money(p.market_value, p.market_currency)) : null,
  ].filter(Boolean);
  if (!tiles.length) return null;
  return el("section", { class: "page section" }, [
    el("h2", { text: t("Carte d'identité") }),
    el("div", { class: "stats-strip", style: { marginTop: "var(--s-4)" } }, tiles),
    methodNote(t("Identité, poste détaillé et valeur estimée : Sofascore. La " +
      "valeur est une estimation de la source, pas un montant de transaction.")),
  ]);
}

/** Le profil de buteur : la seule statistique individuelle qui soit à nous. */
function scoring(p) {
  const s = p.scoring;
  if (!s || !s.goals) return null;

  const max = Math.max(...s.buckets) || 1;
  const bars = el("div", { class: "mins" }, s.buckets.map((n, i) => el("div", {
    class: "mins__col", title: `${s.bucket_labels[i]}' — ${n}`,
  }, [
    el("div", { class: "mins__bar", style: { height: `${n / max * 100}%` } },
       [el("span", { class: "mins__n", text: n || "" })]),
    el("div", { class: "mins__l", text: s.bucket_labels[i] }),
  ])));

  const rivals = Object.entries(s.against).sort((a, b) => b[1] - a[1]);

  return el("section", { class: "page section" }, [
    el("h2", { text: t("Profil de buteur") }),
    methodNote(t("Calculé par nous, à partir de la chronologie de chaque " +
      "rencontre : la source ne publie que le total de buts. Ni minutes " +
      "jouées, ni tirs, ni notes n'existent sur cette division — cette page " +
      "n'en invente pas.")),
    el("div", { class: "stats-strip", style: { marginTop: "var(--s-4)" } }, [
      stat(t("Buts"), s.goals),
      s.penalties ? stat(t("Dont penaltys"), s.penalties) : null,
      s.first ? stat(t("Premier but"), s.first) : null,
      s.last ? stat(t("Dernier but"), s.last) : null,
    ].filter(Boolean)),
    el("div", { class: "card", style: { marginTop: "var(--s-5)" } }, [
      el("div", { class: "card__head" }, [
        el("h3", { text: t("Quand il marque") }),
        el("span", { class: "muted", style: { fontSize: "var(--t--1)" },
                     text: t("minutes") }),
      ]),
      bars,
    ]),
    rivals.length ? el("div", { class: "card", style: { marginTop: "var(--s-4)" } }, [
      el("div", { class: "card__head" }, [el("h3", { text: t("Contre qui") })]),
      el("div", { class: "rivals" }, rivals.map(([k, n]) => el("a", {
        class: "rivals__row", href: `club.html?c=${encodeURIComponent(k)}`,
      }, [
        crestOf(k, "sm"),
        el("span", { class: "truncate", text: nameOf(k) }),
        el("b", { class: "num", text: n }),
      ]))),
    ]) : null,
  ]);
}

function careerTable(p) {
  const rows = p.career || [];
  if (!rows.length) return null;
  return el("section", { class: "page section" }, [
    el("h2", { text: t("Carrière") }),
    el("div", { class: "card", style: { marginTop: "var(--s-4)" } }, [
      el("div", { class: "table__wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: t("Date") }), el("th", { text: t("De") }),
            el("th", { text: t("Vers") }), el("th", { text: t("Indemnité") }),
          ])]),
          el("tbody", {}, rows.map(r => el("tr", {}, [
            el("td", { class: "mono muted", text: r.date || "—" }),
            el("td", { class: "truncate", text: r.from || "—" }),
            el("td", { class: "truncate", text: r.to || "—" }),
            // La source n'est pas normalisée : « Free », « Unknown », un
            // montant. On recopie plutôt que d'inventer une catégorie.
            el("td", { class: "muted", text: r.fee || "—" }),
          ]))),
        ]),
      ]),
    ]),
  ]);
}

function competitions(p) {
  const rows = p.competitions || [];
  if (!rows.length) return null;
  return el("section", { class: "page section" }, [
    el("h2", { text: t("Compétitions traversées") }),
    methodNote(t("Les championnats où la source lui connaît des statistiques. " +
      "Cela ne dit ni le nombre de matchs ni les buts hors de cette division.")),
    el("div", { class: "grid-cards", style: { marginTop: "var(--s-4)" } },
      rows.map(r => el("div", { class: "card" }, [
        el("div", { class: "eyebrow", text: r.country || "" }),
        el("div", { style: { fontWeight: 600, marginTop: "var(--s-1)" },
                    text: r.competition }),
        el("div", { class: "muted mono", style: { fontSize: "var(--t--1)" },
                    text: r.year || "" }),
      ]))),
  ]);
}

boot(async host => {
  await players();
  const p = player(param("p"));
  if (!p) return notFound(host);
  document.title = `${p.name} — ${t("Division 1 koweïtienne")}`;
  append(host, [hero(p), identity(p), scoring(p), careerTable(p), competitions(p)]);
});
