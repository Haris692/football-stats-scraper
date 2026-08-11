/* La coquille : barre haute, pied de page, thème, langue.
   Identique sur les six pages — c'est elle qui fait qu'on ne se demande jamais
   si on a changé de site en changeant de page. */

import { el, mount, qs } from "./dom.js";
import { t, lang, setLang, other } from "./i18n.js";
import { site, loadError } from "./data.js";

const PAGES = [
  ["index.html", "Accueil"],
  ["calendrier.html", "Calendrier"],
  ["classement.html", "Classement"],
  ["clubs.html", "Clubs"],
];

const THEME = "kd1-theme";

function currentTheme() {
  try { return localStorage.getItem(THEME) || "dark"; } catch (e) { return "dark"; }
}

export function applyTheme() {
  document.documentElement.dataset.theme = currentTheme();
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  try { localStorage.setItem(THEME, next); } catch (e) { /* ignore */ }
  applyTheme();
}

/** Le fichier de la page courante, pour marquer le lien actif. */
function here() {
  const file = location.pathname.split("/").pop() || "index.html";
  // Une fiche de match ou de club appartient visuellement à sa rubrique : on
  // n'allume pas « Accueil » quand on lit un club.
  if (file === "match.html") return "calendrier.html";
  if (file === "club.html") return "clubs.html";
  return file;
}

export function renderShell() {
  applyTheme();
  document.documentElement.lang = lang;

  const active = here();
  const nav = el("header", { class: "nav" }, [
    el("div", { class: "nav__in" }, [
      el("a", { class: "brand", href: "index.html" }, [
        el("b", { text: "KD1" }),
        el("span", { text: t("Division 1 koweïtienne") }),
      ]),
      el("nav", { class: "nav__links", "aria-label": t("Accueil") },
        PAGES.map(([href, label]) => el("a", {
          class: "nav__link", href,
          "aria-current": href === active ? "page" : null,
          text: t(label),
        }))),
      el("div", { class: "nav__tools" }, [
        el("button", {
          class: "btn btn--ghost btn--sm", type: "button",
          text: other().toUpperCase(),
          "aria-label": other() === "en" ? "Switch to English" : "Passer en français",
          onClick: () => setLang(other()),
        }),
        el("button", {
          class: "btn btn--ghost btn--sm", type: "button", text: t("Thème"),
          onClick: toggleTheme,
        }),
      ]),
    ]),
  ]);

  const skip = el("a", { class: "skip", href: "#main", text: t("Aller au contenu") });
  document.body.prepend(nav);
  document.body.prepend(skip);
}

export function renderFooter() {
  const s = site();
  const foot = el("footer", { class: "foot" }, [
    el("div", { class: "page" }, [
      el("div", { class: "foot__grid" }, [
        el("div", {}, [
          el("div", { class: "eyebrow", text: t("Division 1 koweïtienne") }),
          el("p", { text: t("Sources : Forebet, Sofascore, Flashscore.") }),
          el("p", { text: t("Aucun pronostic : cette console publie des relevés, pas des prédictions.") }),
        ]),
        el("div", {}, [
          el("div", { class: "eyebrow", text: "Version" }),
          el("p", { class: "mono", text: s ? s.generated : "—" }),
          el("p", {}, [
            el("a", { href: "https://github.com/Haris692/football-stats-scraper",
                      rel: "noopener", target: "_blank", text: "github.com/Haris692" }),
          ]),
        ]),
      ]),
    ]),
  ]);
  document.body.append(foot);
}

/** Le squelette d'attente : la forme du contenu, pas une roue qui tourne. */
export function skeleton(host, rows = 3) {
  mount(host, el("div", { class: "page section stack" },
    Array.from({ length: rows }, (_, i) => el("div", {
      class: "skel",
      style: { height: i === 0 ? "180px" : "88px" },
      "aria-hidden": "true",
    }))));
  host.setAttribute("aria-busy", "true");
}

/** L'écran d'échec. Il dit ce qui s'est passé et ce qu'on peut faire — jamais
 *  « une erreur est survenue ». */
export function failure(host, err) {
  host.removeAttribute("aria-busy");
  mount(host, el("div", { class: "page section" }, [
    el("div", { class: "empty" }, [
      el("h3", { text: t("Les données n'ont pas pu être chargées.") }),
      el("p", { text: loadError(err) }),
      el("button", {
        class: "btn btn--primary", type: "button", text: t("Réessayer"),
        onClick: () => location.reload(),
      }),
    ]),
  ]));
}

/** Point d'entrée commun : coquille, squelette, chargement, rendu, pied.
 *  Chaque page ne fournit que sa fonction de rendu. */
export async function boot(render, { rows = 3 } = {}) {
  renderShell();
  const host = qs("#main");
  skeleton(host, rows);
  try {
    const { load } = await import("./data.js");
    await load();
    host.removeAttribute("aria-busy");
    host.replaceChildren();
    await render(host);
    renderFooter();
  } catch (err) {
    failure(host, err);
  }
}
