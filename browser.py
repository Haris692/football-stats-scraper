"""Couche de récupération HTML pour Forebet.

Forebet est protégé par un challenge Cloudflare « managed ». Ni urllib/requests
ni un Chromium piloté par Playwright ne le franchissent (testé le 05/08/2026 :
`Un instant…` en boucle). En revanche, un Chrome *normal* lancé avec
`--remote-debugging-port` passe le challenge, et on peut s'y attacher ensuite en
CDP pour lire le DOM. C'est ce que fait ce module.

Le HTML est mis en cache sur disque : tant qu'une page cachée n'est pas plus
vieille que `max_age_hours`, aucune requête réseau n'est émise.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# La console Windows est en cp1252 par défaut : sans ça, le moindre accent ou
# flèche dans un message de log fait planter le script.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
PROFILE_DIR = ROOT / ".chrome-profile"
DEBUG_PORT = 9333

# Délai aléatoire entre deux requêtes réseau, comme prévu au cahier des charges.
MIN_DELAY = 2.0
MAX_DELAY = 5.0

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise RuntimeError(
        "Chrome introuvable. Renseigne le chemin dans CHROME_CANDIDATES (browser.py)."
    )


def cache_path(url: str, ext: str = "html") -> Path:
    """Nom de fichier lisible + hash court, pour retrouver une page à l'œil."""
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower().split("forebet.com/")[-1]).strip("-")
    slug = slug[:80] or "page"
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return CACHE_DIR / f"{slug}-{digest}.{ext}"


def read_cache(url: str, max_age_hours: float, ext: str = "html") -> str | None:
    path = cache_path(url, ext)
    if not path.exists():
        return None
    if max_age_hours >= 0 and (time.time() - path.stat().st_mtime) > max_age_hours * 3600:
        return None
    return path.read_text(encoding="utf-8", errors="replace")


class CdpBrowser:
    """Session Chrome réutilisable. À utiliser comme context manager.

    with ForebetBrowser() as b:
        html = b.get(url)
    """

    def __init__(self, headless_profile: bool = True, keep_open: bool = False,
                 max_age_hours: float = 6.0, verbose: bool = True):
        # `headless_profile` : utilise un profil Chrome dédié au scraper plutôt que
        # celui de l'utilisateur (évite de perturber ses onglets et ses cookies).
        self.profile_dir = PROFILE_DIR if headless_profile else None
        self.keep_open = keep_open
        self.max_age_hours = max_age_hours
        self.verbose = verbose
        self._proc = None
        self._pw = None
        self._browser = None
        self._page = None
        self._last_request = 0.0

    # -- cycle de vie ----------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _ensure_page(self):
        if self._page is not None:
            return self._page

        from playwright.sync_api import sync_playwright

        chrome = find_chrome()
        args = [
            chrome,
            f"--remote-debugging-port={DEBUG_PORT}",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=fr-FR",
            "about:blank",
        ]
        if self.profile_dir:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            args.insert(2, f"--user-data-dir={self.profile_dir}")

        self._log(f"→ lancement de Chrome (port CDP {DEBUG_PORT})…")
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._pw = sync_playwright().start()
        last_err = None
        for _ in range(30):  # Chrome met quelques secondes à ouvrir le port
            time.sleep(1)
            try:
                self._browser = self._pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{DEBUG_PORT}"
                )
                break
            except Exception as exc:  # port pas encore ouvert
                last_err = exc
        if self._browser is None:
            raise RuntimeError(f"Impossible de s'attacher à Chrome en CDP : {last_err}")

        ctx = self._browser.contexts[0]
        self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return self._page

    def page(self):
        """L'onglet piloté, Chrome lancé si besoin.

        Exposé pour les usages qui ne passent pas par `get()` — capture d'écran,
        exécution de script — et qui n'ont donc rien à faire du cache HTML.
        """
        return self._ensure_page()

    def close(self):
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        if self._proc is not None and not self.keep_open:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._proc = self._browser = self._pw = self._page = None

    # -- récupération ----------------------------------------------------
    def _throttle(self):
        elapsed = time.time() - self._last_request
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def get(self, url: str, wait_for: str | None = None, force: bool = False) -> str:
        """Renvoie le HTML de `url`, depuis le cache si possible."""
        if not force:
            cached = read_cache(url, self.max_age_hours)
            if cached is not None:
                self._log(f"  cache  {url}")
                return cached

        page = self._ensure_page()
        self._throttle()
        self._log(f"  réseau {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Le challenge Cloudflare se résout tout seul en quelques secondes ;
        # on attend un sélecteur réel de la page plutôt qu'un délai fixe.
        if wait_for:
            page.wait_for_selector(wait_for, timeout=60000)
        else:
            for _ in range(60):
                if "Un instant" not in page.title() and "Just a moment" not in page.title():
                    break
                time.sleep(1)

        html = page.content()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path(url).write_text(html, encoding="utf-8")
        return html

    CHALLENGE_TITLES = ("Un instant", "Just a moment")

    def _wait_challenge(self, page, timeout: int = 60) -> bool:
        """Attend que le challenge Cloudflare se résolve de lui-même."""
        for _ in range(timeout):
            try:
                title = page.title()
            except Exception:
                time.sleep(1)  # navigation en cours : le contexte JS a sauté
                continue
            if not any(t in title for t in self.CHALLENGE_TITLES):
                return True
            time.sleep(1)
        return False

    def _land_on_forebet(self, referer: str | None = None) -> None:
        """Amène la page sur forebet.com, challenge résolu.

        Indispensable avant tout `fetch()` : sur une page encore bloquée sur
        « Un instant… », la requête part sans le cookie de clearance et revient
        en 403 — ce qui ressemble à tort à un endpoint interdit.
        """
        page = self._ensure_page()
        target = referer or "https://www.forebet.com/"
        if "forebet.com" not in (page.url or "") or not self._wait_challenge(page, 3):
            page.goto(target, wait_until="domcontentloaded", timeout=60000)
            if not self._wait_challenge(page):
                raise RuntimeError(
                    "challenge Cloudflare non résolu après 60 s — relancer plus tard"
                )
        # Le challenge se termine par un rechargement : sans cette attente, le
        # `fetch()` suivant part dans un contexte JS sur le point d'être détruit
        # (« Execution context was destroyed »).
        try:
            page.wait_for_load_state("load", timeout=30000)
        except Exception:
            pass

    def get_json(self, url: str, force: bool = False, max_age_hours: float | None = None,
                 referer: str | None = None):
        """Renvoie le JSON servi par un endpoint Forebet.

        Pas de `page.goto` : Chrome enroberait la réponse dans un `<pre>` et
        `page.content()` ramènerait du HTML. On passe donc par un `fetch()`
        exécuté *dans* une page forebet.com — même origine, donc la requête
        emporte le cookie de clearance Cloudflare.

        Cache dans `cache/*.json`, avec sa propre durée de vie : les stats d'un
        match en cours changent toutes les minutes, celles d'un match terminé
        plus jamais. À l'appelant de choisir.
        """
        age = self.max_age_hours if max_age_hours is None else max_age_hours
        if not force:
            cached = read_cache(url, age, ext="json")
            if cached is not None:
                self._log(f"  cache  {url}")
                if not cached.strip():
                    return None  # réponse vide déjà connue, voir plus bas
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass  # cache abîmé : on refait la requête

        self._throttle()
        self._log(f"  réseau {url}")
        script = """async (u) => {
            try {
                const res = await fetch(u, { credentials: "include" });
                const text = await res.text();
                return { status: res.status, text };
            } catch (e) {
                return { error: String(e) };
            }
        }"""
        result = None
        for attempt in range(3):
            self._land_on_forebet(referer)
            try:
                result = self._page.evaluate(script, url)
            except Exception as exc:
                # Rechargement du challenge en pleine évaluation : on repose la
                # page et on retente.
                self._log(f"    tentative {attempt + 1} : {exc}")
                time.sleep(2 + attempt * 2)
                continue
            if result and not result.get("error") and result.get("status") == 200:
                break
            self._log(f"    tentative {attempt + 1} : "
                      f"{result.get('error') or 'HTTP ' + str(result.get('status'))}")
            time.sleep(2 + attempt * 2)

        if not result or result.get("error"):
            raise RuntimeError(f"fetch impossible : {(result or {}).get('error')}")
        if result["status"] != 200:
            raise RuntimeError(f"HTTP {result['status']} sur {url}")

        # Un corps vide n'est pas une panne : c'est la façon dont Forebet dit
        # « rien à donner sur ce match » (rencontre à venir, ou compétition non
        # couverte par son fournisseur de statistiques). On le met en cache tel
        # quel et on renvoie None, sans faire remonter d'erreur de parsing.
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path(url, "json").write_text(result["text"], encoding="utf-8")
        if not result["text"].strip():
            return None
        return json.loads(result["text"])

    def grab_images(self, page_url: str, selector: str = "a.team-logo img") -> dict:
        """Extrait des images **déjà affichées** par une page, sans requête.

        Un `fetch()` sur `/images/icons/*.png` se prend un 403 même exécuté
        depuis la page — Cloudflare filtre aussi les requêtes programmatiques.
        En revanche le navigateur, lui, a bien affiché ces images en rendant la
        page. On les récupère donc en les redessinant dans un canvas : aucune
        requête supplémentaire, donc rien à bloquer. Même origine, donc le
        canvas n'est pas « taint » et `toDataURL` fonctionne.

        Renvoie {texte alternatif: data URI}.
        """
        page = self._ensure_page()
        self._throttle()
        self._log(f"  écussons {page_url}")
        page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(selector, timeout=30000)
        except Exception:
            return {}

        return page.evaluate(
            """async (sel) => {
                const nodes = [...document.querySelectorAll(sel)];
                await Promise.all(nodes.map(img => img.complete && img.naturalWidth
                    ? null
                    : new Promise(done => {
                        img.addEventListener("load", done, { once: true });
                        img.addEventListener("error", done, { once: true });
                        setTimeout(done, 8000);
                      })));
                const out = {};
                for (const img of nodes) {
                    if (!img.naturalWidth) continue;
                    try {
                        const c = document.createElement("canvas");
                        c.width = img.naturalWidth;
                        c.height = img.naturalHeight;
                        c.getContext("2d").drawImage(img, 0, 0);
                        out[img.alt || img.src] = c.toDataURL("image/png");
                    } catch (e) { /* canvas taint : on saute */ }
                }
                return out;
            }""",
            selector,
        )

    def fetch_data_uri(self, url: str) -> str | None:
        """Renvoie une ressource binaire (image…) en `data:` URI.

        Un téléchargement direct par `urllib` se prend un 403 : Cloudflare
        protège aussi les images. On passe donc par un `fetch()` exécuté *dans*
        la page, en même origine, qui hérite du cookie de clearance obtenu au
        moment du challenge.
        """
        page = self._ensure_page()
        if "forebet.com" not in (page.url or ""):
            page.goto("https://www.forebet.com/", wait_until="domcontentloaded",
                      timeout=60000)
        for attempt in range(3):
            result = page.evaluate(
                """async (u) => {
                    try {
                        const res = await fetch(u, { cache: "force-cache" });
                        if (!res.ok) return { error: "HTTP " + res.status };
                        const blob = await res.blob();
                        if (!blob.size) return { error: "réponse vide" };
                        const uri = await new Promise(done => {
                            const fr = new FileReader();
                            fr.onload = () => done(fr.result);
                            fr.onerror = () => done(null);
                            fr.readAsDataURL(blob);
                        });
                        return uri ? { uri } : { error: "lecture impossible" };
                    } catch (e) {
                        return { error: String(e) };
                    }
                }""",
                url,
            )
            if result and result.get("uri"):
                return result["uri"]
            # Forebet coupe les requêtes trop rapprochées : on laisse retomber.
            self._log(f"    tentative {attempt + 1} : {result.get('error') if result else 'aucune réponse'}")
            time.sleep(2 + attempt * 2)
        return None


# La classe n'a en fait rien de spécifique à Forebet : c'est un vrai Chrome
# piloté en CDP, utile pour toute source qui refuse une requête directe.
# L'ancien nom reste exposé pour ne rien casser.
ForebetBrowser = CdpBrowser
