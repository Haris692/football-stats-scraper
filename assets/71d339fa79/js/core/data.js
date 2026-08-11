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
 *  courante — ce qui rend le site déployable dans un sous-dossier, cas de
 *  GitHub Pages (`/football-stats-scraper/`).
 *
 *  ⚠️ On coupe à `/assets/` au lieu de compter les niveaux à remonter. Les
 *  fichiers servis vivent sous `assets/<empreinte>/js/core/`, et l'empreinte
 *  ajoute un niveau : un `../../../` codé en dur pointait une version sur deux
 *  à côté. Couper sur le repère ne dépend d'aucune profondeur. */
const base = import.meta.url.replace(/assets\/.*$/, "");

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

/** La date du jour au format des données, `JJ/MM/AAAA`.
 *
 *  ⚠️ Prise sur l'horloge du VISITEUR, pas sur `SITE.today`, qui est la date de
 *  génération. Les deux coïncident le jour où le site est régénéré ; le
 *  lendemain, `SITE.today` afficherait « aujourd'hui » sur les matchs de la
 *  veille. Un site public est lu n'importe quand. */
export function todayKey(now = new Date()) {
  const p = n => String(n).padStart(2, "0");
  return `${p(now.getDate())}/${p(now.getMonth() + 1)}/${now.getFullYear()}`;
}

const dayOf = f => (f.kickoff || "").split(" ")[0];
const byTime = (a, b) => (a.kickoff_iso || "").localeCompare(b.kickoff_iso || "");

/* Une rencontre est tenue pour « en cours » dans cette fenêtre autour du coup
   d'envoi. Large après, parce que rien ne dit qu'un match est fini : c'est le
   score final qui, en arrivant, l'en sort. Mêmes bornes que `serve.py`, pour
   que l'outil interne et le site ne se contredisent pas. */
const LIVE_BEFORE = 5 * 60000;
const LIVE_AFTER = 150 * 60000;

/** La rencontre se joue-t-elle en ce moment ?
 *
 *  ⚠️ Déduit de l'HORLOGE, pas d'un flux. Le site est statique : il ne peut pas
 *  interroger la source, et le drapeau `live` que posait `serve.py` n'existe
 *  pas ici. Ce que le marqueur dit, c'est « cette rencontre est en train de se
 *  jouer » — pas « ce score est suivi en direct ». La différence est écrite
 *  dans l'infobulle du marqueur, elle ne doit pas se perdre.
 *
 *  Un drapeau explicite dans les données l'emporte : servi par `serve.py`, il
 *  vaut mieux qu'une déduction. */
export function isLive(f, now = Date.now()) {
  if (f.live) return true;
  if (f.played || f.score) return false;
  const ko = Date.parse(f.kickoff_iso || "");
  return Number.isFinite(ko) && now >= ko - LIVE_BEFORE && now <= ko + LIVE_AFTER;
}

/** Toutes les rencontres d'un jour donné, dans l'ordre des coups d'envoi. */
export function fixturesOn(day) {
  return fixtures().filter(f => dayOf(f) === day).sort(byTime);
}

/** Ce que la une doit montrer. Une journée de cette division compte **deux à
 *  quatre rencontres jouées le même soir** : mettre une seule affiche en avant
 *  passait les autres sous silence. On renvoie donc un groupe, et son motif.
 *
 *  Dans l'ordre : les rencontres du jour, sinon la prochaine journée, sinon les
 *  dernières jouées. Ainsi la une a toujours quelque chose de pertinent, quel
 *  que soit le jour où l'on ouvre le site. */
export function headline() {
  const today = fixturesOn(todayKey());
  if (today.length) return { kind: "today", fixtures: today };

  const next = upcoming();
  if (next.length) {
    const day = dayOf(next[0]);
    return { kind: "next", fixtures: next.filter(f => dayOf(f) === day) };
  }

  const last = played();
  if (last.length) {
    const day = dayOf(last[0]);
    return { kind: "last", fixtures: fixturesOn(day).filter(f => f.played) };
  }
  return { kind: "none", fixtures: [] };
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
