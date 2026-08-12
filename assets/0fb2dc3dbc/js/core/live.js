/* Le direct, quand il y en a un.
 *
 * Le site est statique : publié sur GitHub Pages, il n'a aucun flux, et le
 * marqueur « live » n'y dit que « ça se joue en ce moment », déduit de
 * l'horloge. Mais servi par `serve.py`, la même page a un serveur derrière
 * elle, et ce serveur tient un relevé à jour dans `GET /api/live`.
 *
 * ⚠️ C'est le SERVEUR qui collecte, jamais la page. Un onglet ne demande qu'un
 * instantané déjà pris : dix onglets ouverts coûtent donc exactement une
 * collecte par minute, et Forebet ne voit qu'un seul client. La page ne peut
 * pas non plus choisir ce qui est relevé — `serve.py` ne suit que les
 * rencontres de son propre calendrier.
 *
 * La règle de conception qui compte ici : **l'absence de direct n'est pas une
 * erreur**. Sur GitHub Pages `api/live` répond 404, et il ne doit rien en
 * paraître — pas de bandeau rouge, pas de message d'échec. On essaie une fois,
 * et si le point d'entrée n'existe pas on se tait pour de bon.
 */

import { isLive } from "./data.js";

/* Relatif, pas absolu : `/api/live` viserait la racine du domaine, alors que le
   site publié vit sous `/football-stats-scraper/`. En local les deux
   coïncident, ce qui aurait masqué l'erreur jusqu'au déploiement. */
const ENDPOINT = "api/live";

/* Le serveur relève une fois par minute ; on demande plus souvent que ça pour
   que l'affichage ne traîne pas d'un relevé, et parce que c'est la demande qui
   maintient le collecteur en vie (`LIVE_IDLE_STOP` vaut 180 s côté serveur —
   au-delà il s'arrête, à raison : plus personne ne regarde). */
const POLL = 15000;

/* Un 404 est définitif, un `Failed to fetch` ne l'est pas : le serveur peut
   redémarrer sous la page. On tolère donc quelques ratés d'affilée. */
const TOLERANCE = 3;

let snapshot = null;
const listeners = new Set();
let timer = null, misses = 0, dead = false;

/** Le dernier relevé connu pour une rencontre, ou `null`. */
export function liveBlock(matchId) {
  return (snapshot?.live || {})[String(matchId)] || null;
}

/** L'heure du dernier relevé, en `HH:MM`. */
export function liveStamp() {
  const iso = snapshot?.collected;
  return iso ? iso.split("T")[1].slice(0, 5) : null;
}

async function tick() {
  if (dead) return;
  try {
    const res = await fetch(ENDPOINT, { cache: "no-store" });
    // 404 : il n'y a pas de serveur derrière cette page. Ce n'est pas une
    // panne, c'est le mode normal du site publié.
    if (res.status === 404) return stop(true);
    if (!res.ok) throw new Error(res.status);
    const next = await res.json();
    misses = 0;
    // On ne prévient que si quelque chose a bougé : re-dessiner un bloc
    // identique toutes les quinze secondes ferait clignoter la page et
    // perdrait la sélection de texte de qui est en train de lire.
    const changed = JSON.stringify(next.live || {}) !==
                    JSON.stringify(snapshot?.live || {});
    snapshot = next;
    // Un abonné qui échoue ne doit pas emporter les autres ni arrêter le
    // suivi — mais son erreur est tracée. Avalée en silence, un bloc cesserait
    // de se mettre à jour sans que rien ne le dise.
    if (changed) listeners.forEach(cb => {
      try { cb(next); } catch (err) { console.error("direct :", err); }
    });
  } catch (e) {
    if (++misses >= TOLERANCE) stop(true);
  }
}

function stop(permanent = false) {
  clearInterval(timer);
  timer = null;
  if (permanent) dead = true;
}

function start() {
  if (dead || timer) return;
  timer = setInterval(tick, POLL);
  tick();
}

/** S'abonner au direct. Rend une fonction qui désabonne.
 *
 *  N'ouvre rien si aucune rencontre du calendrier ne se joue : inutile de
 *  réveiller un collecteur pour une page consultée à trois heures du matin.
 *  L'onglet caché suspend la demande — c'est elle qui tient le collecteur
 *  éveillé, et personne ne regarde un onglet au second plan. */
export function watchLive(cb, { fixtures = [] } = {}) {
  if (!fixtures.some(f => isLive(f))) return () => {};
  listeners.add(cb);

  const wake = () => (document.hidden ? stop() : start());
  document.addEventListener("visibilitychange", wake);
  wake();

  return () => {
    listeners.delete(cb);
    document.removeEventListener("visibilitychange", wake);
    if (!listeners.size) stop();
  };
}
