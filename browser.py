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

import base64
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
from urllib.parse import urlsplit

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

# Sentinelle écrite dans le cache pour une ressource absente : une absence est
# une réponse, et la redemander à chaque passe coûte pour rien.
NOT_FOUND = "__http_404__"

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


def chrome_user_data_dir() -> Path:
    """Le dossier de profils du Chrome de l'utilisateur, selon le système."""
    if sys.platform == "win32":
        return Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Google/Chrome"
    return Path.home() / ".config/google-chrome"


def debug_port_open(port: int = None) -> bool:
    """Un Chrome écoute-t-il déjà en CDP ?"""
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port or DEBUG_PORT)) == 0


def chrome_is_running() -> bool:
    """Y a-t-il déjà un Chrome ouvert ?

    Un Chrome démarré sans `--remote-debugging-port` ne peut plus ouvrir ce port
    ensuite : relancer l'exécutable rend juste la main à l'instance existante.
    Autant le dire tout de suite plutôt que d'attendre trente secondes.
    """
    try:
        if sys.platform == "win32":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                                 capture_output=True, text=True, timeout=10).stdout
            return "chrome.exe" in out.lower()
        out = subprocess.run(["pgrep", "-x", "chrome"],
                             capture_output=True, text=True, timeout=10)
        return out.returncode == 0
    except Exception:
        return False      # dans le doute, on laisse la tentative se faire


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
                 max_age_hours: float = 6.0, verbose: bool = True,
                 user_data_dir: str | Path | None = None,
                 profile_name: str | None = None):
        # `headless_profile` : utilise un profil Chrome dédié au scraper plutôt que
        # celui de l'utilisateur (évite de perturber ses onglets et ses cookies).
        #
        # `user_data_dir` / `profile_name` : pour travailler dans le VRAI profil
        # de l'utilisateur — sessions ouvertes, cookies, extensions. Utile pour
        # photographier une page derrière une authentification.
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None
        self.profile_name = profile_name
        self.profile_dir = (self.user_data_dir if self.user_data_dir
                            else (PROFILE_DIR if headless_profile else None))
        self.keep_open = keep_open
        self.max_age_hours = max_age_hours
        self.verbose = verbose
        self._proc = None
        self._pw = None
        self._browser = None
        self._page = None
        self._owns_page = False
        self._last_err = None
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
            if not self.user_data_dir:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
            args.insert(2, f"--user-data-dir={self.profile_dir}")
        if self.profile_name:
            args.insert(2, f"--profile-directory={self.profile_name}")

        self._pw = sync_playwright().start()

        # Un Chrome déjà lancé avec le port ouvert : on s'y raccroche plutôt que
        # d'en démarrer un second, qui échouerait à ouvrir le même port.
        if self._try_connect(attempts=1):
            self._log(f"→ Chrome déjà en écoute sur le port {DEBUG_PORT}")
        else:
            # Seul le profil habituel pose problème : un `--user-data-dir`
            # distinct démarre sa propre instance même si Chrome est ouvert.
            if (self.user_data_dir == chrome_user_data_dir()
                    and chrome_is_running()):
                raise RuntimeError(
                    "Chrome est déjà ouvert avec ton profil, et un Chrome déjà "
                    "lancé ne peut pas ouvrir le port de débogage après coup.\n"
                    "  → ferme complètement Chrome (toutes les fenêtres) puis "
                    "relance la commande,\n"
                    "  → ou démarre Chrome avec "
                    f"--remote-debugging-port={DEBUG_PORT} et relance."
                )
            self._log(f"→ lancement de Chrome (port CDP {DEBUG_PORT})…")
            self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
            if not self._try_connect(attempts=30):
                # Cas le plus fréquent sous Windows : un Chrome subsistait en
                # arrière-plan (zone de notification, « applications en arrière-
                # plan »). Relancer l'exécutable lui rend la main et le drapeau
                # est ignoré — une fenêtre s'ouvre, mais aucun port.
                if chrome_is_running():
                    raise RuntimeError(
                        "Chrome s'est ouvert mais sans port de débogage : un "
                        "processus Chrome subsistait et a repris la main.\n"
                        "  → ferme TOUT Chrome, y compris l'icône de la zone de "
                        "notification (au besoin `Stop-Process -Name chrome "
                        "-Force`), puis relance.\n"
                        f"  → contrôle : curl.exe http://127.0.0.1:{DEBUG_PORT}"
                        "/json/version doit répondre du JSON."
                    )
                raise RuntimeError(
                    f"Impossible de s'attacher à Chrome en CDP : {self._last_err}")

        ctx = self._browser.contexts[0]
        # ⚠️ Dans le vrai profil, `ctx.pages[0]` est un onglet DE L'UTILISATEUR :
        # le réutiliser reviendrait à le faire naviguer ailleurs, donc à lui
        # faire perdre ce qu'il avait sous les yeux. On ouvre le nôtre.
        self._owns_page = bool(self.user_data_dir) or not ctx.pages
        self._page = ctx.new_page() if self._owns_page else ctx.pages[0]
        return self._page

    def _try_connect(self, attempts: int) -> bool:
        self._last_err = None
        for i in range(attempts):
            if i:
                time.sleep(1)  # Chrome met quelques secondes à ouvrir le port
            try:
                self._browser = self._pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{DEBUG_PORT}")
                return True
            except Exception as exc:      # port pas encore ouvert
                self._last_err = exc
        return False

    def page(self):
        """L'onglet piloté, Chrome lancé si besoin.

        Exposé pour les usages qui ne passent pas par `get()` — capture d'écran,
        exécution de script — et qui n'ont donc rien à faire du cache HTML.
        """
        return self._ensure_page()

    def close(self):
        # Dans le profil de l'utilisateur, on referme seulement l'onglet qu'on a
        # ouvert : le reste de la fenêtre est à lui.
        if self.user_data_dir and self._owns_page and self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass

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
        # On ne tue jamais le Chrome de l'utilisateur : soit il tournait déjà et
        # ce n'est pas le nôtre, soit on l'a lancé sur son profil et ses fenêtres
        # habituelles s'y sont rouvertes. Il le fermera lui-même.
        if (self._proc is not None and not self.keep_open
                and not self.user_data_dir):
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
        """Amène la page sur l'origine visée, challenge résolu.

        Indispensable avant tout `fetch()` : sur une page encore bloquée sur
        « Un instant… », la requête part sans le cookie de clearance et revient
        en 403 — ce qui ressemble à tort à un endpoint interdit.

        ⚠️ On compare l'origine à **celle du `referer`**, pas à forebet.com.
        Comparer à forebet valait tant qu'un `CdpBrowser` ne servait qu'une
        source à la fois : un appel Sofascore émis depuis une page restée sur
        Forebet passait le test, sautait la navigation, et son `fetch()`
        cross-origin revenait en « Failed to fetch ». C'est exactement ce qui
        arrive au collecteur du direct, qui enchaîne les deux (constaté le
        17/08/2026 en branchant l'horloge de repli).
        """
        page = self._ensure_page()
        target = referer or "https://www.forebet.com/"
        origin = urlsplit(target).netloc
        if origin not in (page.url or "") or not self._wait_challenge(page, 3):
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
                # ⚠️ Une absence est une information, et elle se met en cache
                # comme le reste : sans ça, chaque collecte redemandait tous
                # les endpoints inexistants — et sur cette division il y en a
                # beaucoup. Le sentinelle est relu ici pour lever la même
                # erreur, sans requête.
                if cached.startswith(NOT_FOUND):
                    raise RuntimeError(f"HTTP 404 sur {url}")
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
            # Un 404 est une réponse définitive : « cet endpoint n'existe pas
            # pour cette ressource ». Le retenter deux fois de plus, avec les
            # pauses, triplait le coût de chaque trou de couverture — et il y en
            # a beaucoup sur cette division.
            if result and result.get("status") == 404:
                break
            self._log(f"    tentative {attempt + 1} : "
                      f"{result.get('error') or 'HTTP ' + str(result.get('status'))}")
            time.sleep(2 + attempt * 2)

        if not result or result.get("error"):
            raise RuntimeError(f"fetch impossible : {(result or {}).get('error')}")
        if result["status"] == 404:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path(url, "json").write_text(NOT_FOUND, encoding="utf-8")
            raise RuntimeError(f"HTTP 404 sur {url}")
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

    def get_bytes(self, url: str, force: bool = False,
                  max_age_hours: float | None = None,
                  referer: str | None = None) -> bytes | None:
        """Le même chemin que `get_json`, pour un binaire.

        Les photos de joueurs de Sofascore répondent **403 à une requête
        directe** (vérifié en `curl`) et 200 à un `fetch()` exécuté dans une
        page du site : même origine, mêmes cookies. On les rapatrie donc comme
        le reste, en passant par le navigateur, et on transporte les octets en
        base64 parce qu'un `page.evaluate` ne rend que du JSON.
        """
        age = self.max_age_hours if max_age_hours is None else max_age_hours
        if not force:
            cached = cache_path(url, "b64")
            if cached.exists():
                fresh = (time.time() - cached.stat().st_mtime) / 3600 <= age
                if fresh:
                    self._log(f"  cache  {url}")
                    raw = cached.read_text(encoding="utf-8")
                    return base64.b64decode(raw) if raw.strip() else None

        self._throttle()
        self._log(f"  réseau {url}")
        script = """async (u) => {
            try {
                const res = await fetch(u, { credentials: "include" });
                if (res.status !== 200) return { status: res.status };
                const buf = new Uint8Array(await res.arrayBuffer());
                let s = "";
                for (let i = 0; i < buf.length; i++) s += String.fromCharCode(buf[i]);
                return { status: 200, b64: btoa(s) };
            } catch (e) {
                return { error: String(e) };
            }
        }"""
        self._land_on_forebet(referer)
        try:
            result = self._page.evaluate(script, url)
        except Exception as exc:
            raise RuntimeError(f"fetch impossible : {exc}") from exc
        if result.get("error"):
            raise RuntimeError(f"fetch impossible : {result['error']}")

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if result.get("status") != 200:
            # Une absence est une réponse : on la met en cache pour ne pas la
            # redemander à chaque collecte.
            cache_path(url, "b64").write_text("", encoding="utf-8")
            return None
        cache_path(url, "b64").write_text(result["b64"], encoding="utf-8")
        return base64.b64decode(result["b64"])

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
