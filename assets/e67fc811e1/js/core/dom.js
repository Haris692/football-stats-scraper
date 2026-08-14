/* Fabrique d'éléments. Volontairement minuscule : tout le site se construit
   avec ces quatre fonctions, et aucune ne prend de HTML sous forme de chaîne —
   c'est ce qui garantit qu'un nom de joueur ou de club venu de la source ne
   peut jamais être interprété comme du balisage. */

export function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(opts)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") throw new Error("el() n'accepte pas de HTML brut");
    else if (k === "style") Object.assign(node.style, v);
    else if (k === "data") for (const [dk, dv] of Object.entries(v)) {
      if (dv !== null && dv !== undefined) node.dataset[dk] = dv;
    }
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    }
    else node.setAttribute(k, v === true ? "" : v);
  }
  append(node, children);
  return node;
}

export function append(parent, children) {
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child)) : child);
  }
  return parent;
}

export const qs = (sel, root = document) => root.querySelector(sel);
export const qsa = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Vide un hôte puis y pose du contenu. Remplacer plutôt qu'accumuler : un
 *  re-rendu qui oublie de nettoyer duplique en silence. */
export function mount(host, children) {
  host.replaceChildren();
  return append(host, children);
}

/** Le paramètre d'URL, seule source de « quelle page de quoi » du site.
 *  Pas de routeur côté client : six pages statiques se lient par des liens,
 *  et un lien vers un match doit rester copiable et partageable. */
export function param(name) {
  return new URLSearchParams(location.search).get(name);
}
