/* Le chargement des données, et les quelques questions qu'on leur pose partout.

   Deux fichiers, chargés EN PARALLÈLE : `site.json` (~280 Ko) porte tout ce qui
   s'affiche, `crests.json` (~380 Ko) ne porte que des images. Les séparer évite
   qu'un score attende des écussons. La page se dessine dès que le premier
   arrive ; les écussons se posent ensuite, dans un emplacement déjà réservé —
   rien ne saute. */

import { t } from "./i18n.js";

let SITE = null;
let CRESTS = {};

/** La racine du site, déduite de l'emplacement de CE module et non de la page
 *  courante. Trois niveaux à remonter : `assets/js/core/`. Passer par
 *  `import.meta.url` rend le site déployable dans un sous-dossier — ce qui est
 *  exactement le cas sur GitHub Pages (`/football-stats-scraper/`). */
const base = new URL("../../../", import.meta.url).href;

async function json(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${res.status} sur ${path}`);
  return res.json();
}

/** Charge le socle. Les écussons arrivent après, sans bloquer le rendu. */
export async function load() {
  SITE = await json(`${base}data/site.json`);
  json(`${base}data/crests.json`)
    .then(c => {
      CRESTS = c;
      // Les emplacements sont déjà là et à la bonne taille : on ne fait que
      // remplir. Aucun décalage de mise en page.
      document.dispatchEvent(new CustomEvent("crests"));
    })
    .catch(() => { /* un site sans écussons reste lisible */ });
  return SITE;
}

export const site = () => SITE;
export const crest = key => CRESTS[key] || null;

/* ---------------------------------------------------------------- lectures */

export const team = key => (SITE.teams || {})[key] || null;
export const teams = () => Object.values(SITE.teams || {});
export const match = id => (SITE.matches || {})[String(id)] || null;

export const fixtures = () => SITE.fixtures || [];
export const standings = () => SITE.standings || [];
export const scorers = () => SITE.scorers || [];

/** Le nom affichable d'un club, par sa clé. Toujours passer par ici : les
 *  sources écrivent « Yarmouk (KUW) », « Yarmouk SC » et « Yarmouk » selon
 *  l'humeur, et on n'en affiche qu'un. */
export const nameOf = key => (team(key)?.name) || key;

/** Les rencontres d'un club, dans l'ordre du calendrier.
 *
 *  Fusionne les deux couvertures : `fixtures` (fenêtre récente, avec fiche
 *  détaillée et identifiant cliquable) et `season_events` (la saison entière
 *  depuis septembre, réorientée contre Flashscore au moment du build). La
 *  fenêtre récente prime — elle seule mène à une fiche. */
export function seasonOf(key) {
  const rows = fixtures()
    .filter(f => f.home_key === key || f.away_key === key)
    .map(f => ({
      iso: f.kickoff_iso, kickoff: f.kickoff, round: f.round,
      home_key: f.home_key, away_key: f.away_key, score: f.score,
      played: f.played, live: f.live, match_id: f.match_id,
    }));

  const seen = new Set(rows.map(r => (r.iso || "").slice(0, 10)));
  for (const e of (SITE.season_events || [])) {
    if (e.home !== key && e.away !== key) continue;
    if (seen.has((e.kickoff_iso || "").slice(0, 10))) continue;
    rows.push({
      iso: e.kickoff_iso, kickoff: e.kickoff, round: e.round,
      home_key: e.home, away_key: e.away,
      score: e.finished ? `${e.home_score} - ${e.away_score}` : null,
      played: e.finished, match_id: null,
    });
  }
  rows.sort((a, b) => (a.iso || "").localeCompare(b.iso || ""));
  return rows;
}

export function fixturesOf(key) {
  return fixtures().filter(f => f.home_key === key || f.away_key === key);
}

/** Rendu d'une rencontre du point de vue d'un club : a-t-il gagné ? */
export function outcome(fixture, key) {
  if (!fixture.played || !fixture.score) return null;
  const [h, a] = fixture.score.split(/\s*-\s*/).map(Number);
  if (!Number.isFinite(h) || !Number.isFinite(a)) return null;
  const mine = fixture.home_key === key ? h : a;
  const theirs = fixture.home_key === key ? a : h;
  return mine > theirs ? "V" : mine < theirs ? "D" : "N";
}

/** Les rencontres jouées, de la plus récente à la plus ancienne. */
export function played() {
  return fixtures().filter(f => f.played && f.score)
    .sort((a, b) => (b.kickoff_iso || "").localeCompare(a.kickoff_iso || ""));
}

/** Les rencontres à venir, de la plus proche à la plus lointaine. */
export function upcoming() {
  return fixtures().filter(f => !f.played)
    .sort((a, b) => (a.kickoff_iso || "").localeCompare(b.kickoff_iso || ""));
}

/** La rencontre à mettre à la une. Dans l'ordre : une qui se joue maintenant,
 *  sinon celle du jour, sinon la dernière jouée. On ne met jamais en avant une
 *  rencontre lointaine : la une doit être ce qui vient de se passer. */
export function featured() {
  const live = fixtures().find(f => f.live);
  if (live) return live;
  const today = fixtures().filter(f => (f.kickoff || "").startsWith(SITE.today));
  if (today.length) {
    return today.find(f => !f.played) || today[today.length - 1];
  }
  return played()[0] || upcoming()[0] || fixtures()[0] || null;
}

/** Le total des buts et des matchs de la saison, pour les chiffres d'entête.
 *  Calculé depuis les rencontres Sofascore, seules à couvrir toute la saison. */
export function seasonTotals() {
  const done = (SITE.season_events || []).filter(e => e.finished);
  const goals = done.reduce(
    (n, e) => n + (e.home_score || 0) + (e.away_score || 0), 0);
  return {
    matches: done.length,
    goals,
    average: done.length ? Math.round(goals / done.length * 100) / 100 : 0,
    clubs: teams().length,
  };
}

/** Message d'échec de chargement. Le cas le plus fréquent est réel et précis :
 *  quelqu'un a ouvert `index.html` en double-cliquant, et `fetch` ne marche pas
 *  en `file://`. Le dire vaut mieux qu'un « une erreur est survenue ». */
export function loadError(err) {
  const local = location.protocol === "file:";
  return local
    ? t("Le site a besoin d'un serveur pour lire ses données : ouvre-le via une adresse http, pas en double-cliquant le fichier.")
    : `${t("Les données n'ont pas pu être chargées.")} (${err.message})`;
}
