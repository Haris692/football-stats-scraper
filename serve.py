"""Sert la console en local et lui donne un bouton « Rafraîchir » qui collecte.

Sur GitHub Pages, ce bouton ne peut pas relancer de collecte : Forebet n'envoie
aucun en-tête CORS (vérifié le 10/08/2026 depuis l'origine github.io — les deux
URL répondent `TypeError: Failed to fetch`), et son challenge Cloudflare suppose
de toute façon un vrai navigateur piloté. La page publiée se rabat donc sur son
`data.json`.

Ici, c'est Python qui collecte — exactement la même chaîne que
`build_console.py` — et la page ne fait qu'un appel de même origine.

    python serve.py                 # http://127.0.0.1:8800
    python serve.py --port 9000 --scope played

La **collecte complète** est déclenchée à la main, jamais périodique : c'est une
exigence reprise du projet `kuwait-football`, et ça évite de marteler la source.

Le **direct** (`GET /api/live`) est la seule exception, et il est taillé pour
rester dans l'esprit de la règle : un unique fil de fond relève les seuls
matchs en cours, une fois par minute, et s'arrête de lui-même dès que plus
aucune page ne le demande. La page interroge ce fil, pas Forebet — le nombre
d'onglets ouverts ne change donc rien à ce que la source encaisse.

Chaque relevé croise **deux** points d'entrée : `get_evs_n.php` pour les
statistiques, match par match, et `/gsv/` (`fetch_clock`) pour l'horloge, une
seule requête pour tout le monde. Le second est arrivé le 17/08/2026 et apporte
ce que le premier n'a jamais eu : la **minute de jeu**, le temps additionnel, et
un statut franc — `FT` clôt la rencontre, `Postp.` la retire du suivi.

Ce même dossier contient les deux façades, servies ensemble : la **console**
interne (`console.html`, fichier unique, générateur de brief Instagram) et le
**site** public (`index.html` et ses cinq pages). Depuis le 11/08/2026, le site
consomme lui aussi `/api/live` — servi ici, son score et ses statistiques se
mettent à jour seuls pendant la rencontre ; publié sur GitHub Pages, il ne
trouve pas ce point d'entrée et retombe sans bruit sur ses données figées.

## Le port public, pour l'auto-hébergement

`--public-port` ouvre un **second écouteur** dans le même processus :

    python serve.py --public-port 8801   # 8800 local complet, 8801 exposable

Il ne sert que ce que le site demande vraiment (voir `PUBLIC_PAGES`), en lecture
seule, sans `/api/refresh` et sans listing de dossier. C'est lui que le
Cloudflare Tunnel doit viser, **jamais 8800** : le port local sert aussi la
console interne, le code, `PROGRESS.md`, `.git/`, `data/inbox/` et le profil
Chrome — donc ses cookies de session.

Deux écouteurs mais **un seul processus**, à dessein : ils partagent
`Handler.lock` et l'unique `LiveCollector`, sinon deux Chrome se disputeraient
le port CDP 9333. Et la séparation est celle du réseau, pas celle d'un en-tête
`CF-Connecting-IP` — qu'on ne peut de toute façon pas croire tant qu'on n'a pas
vérifié d'où vient la connexion.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

from browser import CdpBrowser
from build_console import assemble, build, data_file_for, make_payload
from fetch_clock import fetch as fetch_clock
from fetch_stats import fetch as fetch_stats

ROOT = Path(__file__).resolve().parent
PAGE = "console.html"
SITE_PAGE = "index.html"

# -- direct ------------------------------------------------------------------
#
# Une rencontre est tenue pour « en cours » dans cette fenêtre autour du coup
# d'envoi. Large après, parce que rien dans la source ne dit qu'un match est
# fini : ni statut, ni minute (vérifié le 10/08/2026, l'en-tête ne porte que
# les scores). C'est `ft_score` qui, en se remplissant, clôt la rencontre.
LIVE_BEFORE = timedelta(minutes=5)
LIVE_AFTER = timedelta(minutes=150)
# Intervalle entre deux relevés. La page, elle, interroge `serve.py` bien plus
# souvent : elle lit un instantané déjà pris, elle ne déclenche rien.
LIVE_INTERVAL = 60.0
# Sans demande de la page pendant ce délai, le collecteur s'arrête. Fermer
# l'onglet doit suffire à ne plus solliciter Forebet — sinon un `serve.py`
# oublié le sonderait toute la soirée.
LIVE_IDLE_STOP = 180.0


def live_data_file() -> Path:
    """Le fichier où le collecteur lit les rencontres à suivre.

    `console.data.json` d'abord : c'est lui que « Rafraîchir » réécrit, donc le
    plus frais quand la console tourne. À défaut `data/site.json`, qui porte les
    mêmes `match_id` et `kickoff_iso` et qui, lui, est versionné.

    Sans ce repli, un poste qui ne sert que le site public n'aurait aucune
    rencontre à suivre : il attendrait un fichier que seul l'outil interne
    produit, et que `.gitignore` écarte du dépôt. Le choix est refait à chaque
    démarrage du collecteur, pas figé au lancement du serveur.
    """
    console = data_file_for(ROOT / PAGE)
    return console if console.exists() else ROOT / "data" / "site.json"


def _kickoff(fixture: dict) -> datetime | None:
    """L'heure de coup d'envoi, en heure locale — comme la page."""
    raw = fixture.get("kickoff_iso")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class LiveCollector(threading.Thread):
    """Relève en tâche de fond les statistiques des matchs en cours.

    Un seul fil, un seul Chrome, un seul relevé par intervalle : la page ne
    déclenche pas la collecte, elle lit le dernier instantané. Dix onglets
    ouverts sollicitent donc Forebet exactement autant qu'un seul — c'est ce
    qui rend le direct compatible avec la règle « ne pas marteler la source ».
    """

    def __init__(self, data_file: Path, interval: float = LIVE_INTERVAL):
        super().__init__(daemon=True, name="live")
        self.data_file = data_file
        self.interval = interval
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._last_ask = time.time()
        self._fixtures: list[dict] = []
        self._fixtures_mtime = None
        # Les rencontres qu'on ne sonde plus, pour deux raisons distinctes :
        # `ft_score` rempli (elle est finie) ou horloge à « Postp. » (elle ne
        # se jouera pas ce soir). Sans la seconde, une rencontre reportée était
        # sondée pendant les 150 minutes de `LIVE_AFTER`, pour rien.
        self._closed: set[int] = set()
        self._snapshot = {"state": "démarrage", "live": {}, "collected": None,
                          "watching": []}

    # -- ce que voit la page ---------------------------------------------
    def touch(self) -> None:
        self._last_ask = time.time()

    def snapshot(self) -> dict:
        self.touch()
        with self._lock:
            return dict(self._snapshot)

    def _publish(self, **fields) -> None:
        with self._lock:
            self._snapshot = {**self._snapshot, **fields}

    # -- quels matchs relever --------------------------------------------
    def fixtures(self) -> list[dict]:
        """Les rencontres du `data.json`, relues quand le fichier change.

        C'est le serveur qui décide ce qu'il relève, jamais la page : sans ça,
        un onglet pourrait lui faire interroger n'importe quel identifiant.
        """
        try:
            mtime = self.data_file.stat().st_mtime
        except OSError:
            return []
        if mtime != self._fixtures_mtime:
            try:
                blob = json.loads(self.data_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return self._fixtures
            self._fixtures = blob.get("fixtures") or []
            self._fixtures_mtime = mtime
        return self._fixtures

    def live_ids(self) -> list[int]:
        now = datetime.now()
        out = []
        for fixture in self.fixtures():
            mid = fixture.get("match_id")
            if not mid or int(mid) in self._closed:
                continue
            kickoff = _kickoff(fixture)
            if kickoff and kickoff - LIVE_BEFORE <= now <= kickoff + LIVE_AFTER:
                out.append(int(mid))
        return out

    # -- boucle -----------------------------------------------------------
    def run(self) -> None:
        browser = None
        try:
            while time.time() - self._last_ask < LIVE_IDLE_STOP:
                ids = self.live_ids()
                if not ids:
                    browser = self._drop(browser)
                    self._publish(state="aucun match en cours", watching=[])
                else:
                    browser = self._cycle(ids, browser)
                self._wake.wait(self.interval)
        finally:
            self._drop(browser)
            self._publish(state="arrêté")
            # Tracé : sans ça, on ne peut pas distinguer « le collecteur tourne
            # encore » de « il s'est arrêté et vient de repartir ».
            print(f"  direct : collecteur arrêté après "
                  f"{int(time.time() - self._last_ask)} s sans demande", flush=True)

    def _cycle(self, ids: list[int], browser):
        # `/api/refresh` a la priorité : les deux pilotent le même Chrome sur le
        # même port CDP. Plutôt que de se disputer l'onglet, le direct saute un
        # tour — il en reprendra un dans une minute.
        if not Handler.lock.acquire(blocking=False):
            self._publish(state="collecte complète en cours — tour sauté")
            return browser
        try:
            if browser is None:
                browser = CdpBrowser(verbose=False)
            # L'horloge d'abord, et une seule requête pour toutes les
            # rencontres : elle est légère (~8 Ko), et la prendre avant les
            # statistiques fait que la minute continue de tourner même si
            # `get_evs_n` tousse. Elle ne lève rien — au pire elle rend {}.
            clocks = fetch_clock(browser=browser)
            # `force` : un relevé en direct qu'on servirait depuis le cache
            # n'aurait aucun intérêt.
            stats = fetch_stats(ids, browser=browser, force=True)
        except Exception as exc:
            print(f"  direct : relevé impossible ({exc})", file=sys.stderr, flush=True)
            self._publish(state=f"indisponible : {exc}", watching=ids)
            return self._drop(browser)
        finally:
            Handler.lock.release()

        live = {str(mid): block for mid, block in stats.items()}
        # Une rencontre peut avoir une horloge sans avoir de statistiques :
        # Forebet ne couvre les relevés que d'un match sur deux sur cette
        # division. Elle mérite quand même sa minute, donc son propre bloc.
        for mid in ids:
            clock = clocks.get(mid)
            if clock is None:
                continue
            live.setdefault(str(mid), {"source": "forebet/gsv"})["clock"] = clock
            if clock["status"] == "reporte":
                self._closed.add(mid)
        for mid, block in stats.items():
            if block.get("full_time"):
                self._closed.add(int(mid))
        self._publish(
            state="ok",
            live=self._flag_flips(live),
            watching=ids,
            collected=datetime.now().isoformat(timespec="seconds"),
        )
        return browser

    def _flag_flips(self, live: dict) -> dict:
        """Marque les relevés dont le score a reculé d'un relevé à l'autre.

        Constaté le 10/08/2026 sur Sahel - Al Shamiya : l'unique but a été
        attribué à un camp puis à l'autre, `ht_score` passant de « 0-1 » à
        « 1-0 » — identifiants d'équipe corrects des deux côtés, donc c'est la
        source qui s'est reprise, pas le parseur. Un but ne se démarque pas :
        quand le compte baisse, la page doit pouvoir le dire au lieu
        d'afficher le nouveau score comme s'il était sûr.
        """
        previous = (self._snapshot.get("live") or {})
        for mid, block in live.items():
            was = previous.get(mid)
            if not was:
                continue
            for side in ("home", "away"):
                before = (was.get(side) or {}).get("goals")
                now = (block.get(side) or {}).get("goals")
                if before is not None and now is not None and now < before:
                    block["unstable"] = True
            # Une fois constaté, le doute ne s'efface plus de la rencontre.
            if was.get("unstable"):
                block["unstable"] = True
        return live

    @staticmethod
    def _drop(browser):
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        return None


class Handler(SimpleHTTPRequestHandler):
    """Fichiers statiques, plus un point d'entrée `/api/refresh`."""

    options: SimpleNamespace
    # Une collecte à la fois : deux clics rapprochés lanceraient deux Chrome et
    # se disputeraient le même port CDP. Le collecteur du direct s'y plie aussi.
    lock = threading.Lock()
    # Le collecteur du direct, démarré à la première demande de la page.
    collector: LiveCollector | None = None
    collector_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):  # le log par défaut est trop bavard
        # `/api/live` est interrogé toutes les quinze secondes : le tracer
        # noierait le reste.
        if "/api/" in (self.path or "") and "/api/live" not in (self.path or ""):
            print(f"  {self.command} {self.path}", flush=True)

    # -- direct -----------------------------------------------------------
    @classmethod
    def live_collector(cls) -> LiveCollector:
        """Le collecteur, démarré à la demande.

        Rien ne tourne tant que personne ne regarde : c'est la page qui, en
        demandant le direct, met le fil en route. Il s'arrête tout seul quand
        elle cesse de demander (voir `LIVE_IDLE_STOP`).
        """
        with cls.collector_lock:
            if cls.collector is None or not cls.collector.is_alive():
                cls.collector = LiveCollector(live_data_file())
                cls.collector.start()
                print("  direct : collecteur démarré", flush=True)
            cls.collector.touch()
            return cls.collector

    def do_GET(self):
        if self.path.split("?")[0] == "/api/live":
            snapshot = self.live_collector().snapshot()
            snapshot["now_iso"] = datetime.now().isoformat(timespec="seconds")
            snapshot["interval"] = LIVE_INTERVAL
            self._json(200, snapshot)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/refresh":
            self.send_error(404)
            return
        if not self.lock.acquire(blocking=False):
            self._json(409, {"error": "une collecte est déjà en cours"})
            return
        try:
            payload = self._collect()
        except Exception as exc:
            # L'erreur remonte telle quelle à la page : sans ça, le bouton
            # échouerait en silence et on chercherait dans le mauvais sens.
            print(f"  échec de la collecte : {exc}", file=sys.stderr, flush=True)
            self._json(500, {"error": str(exc)})
        else:
            self._json(200, payload)
        finally:
            self.lock.release()

    def _collect(self) -> dict:
        matches, fixtures = assemble(self.options)
        if not matches:
            raise RuntimeError("aucun match récupéré")
        # On réécrit la page et son data.json au passage : le rafraîchissement
        # doit survivre à la fermeture de l'onglet, sinon on aurait collecté
        # pour rien.
        build(matches, fixtures, ROOT / PAGE, data_file_for(ROOT / PAGE))
        return make_payload(matches, fixtures)

    def _json(self, status: int, body: dict) -> None:
        blob = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        # Le navigateur ne doit jamais resservir une collecte périmée.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)

    def end_headers(self):
        if self.command == "GET" and self.path.split("?")[0].endswith(
                (".html", ".json")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


# -- façade publique ---------------------------------------------------------
#
# Ce que le site demande vraiment, relevé fichier par fichier dans
# `src/js/core/data.js` (les trois JSON, les portraits) et `live.js` (le direct).
# Tout ce qui n'est pas dans cette liste est refusé : c'est une **liste
# blanche**, pas une liste noire. Un fichier ajouté au dépôt n'est donc jamais
# exposé par mégarde — il faut venir l'écrire ici.
PUBLIC_PAGES = frozenset({
    "index.html", "calendrier.html", "classement.html",
    "club.html", "clubs.html", "joueur.html", "match.html",
})
PUBLIC_DATA = frozenset({
    "data/site.json", "data/crests.json", "data/players.site.json",
})

# Quotas par client, sur une fenêtre glissante. Le site charge une page en une
# rafale (modules, JSON, portraits) puis se tait : le quota statique est large.
# Le direct, lui, est demandé toutes les 15 s par onglet — 12 par minute laisse
# la place à deux ou trois onglets sans ouvrir la porte au martèlement.
PUBLIC_QUOTA_FILES = (240, 60.0)
PUBLIC_QUOTA_LIVE = (12, 60.0)


class RateLimit:
    """Compte les demandes par client sur une fenêtre glissante."""

    def __init__(self, quota: int, window: float):
        self.quota = quota
        self.window = window
        self._seen: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, who: str) -> bool:
        now = time.time()
        with self._lock:
            # Purge : sans elle, un point d'entrée public accumulerait une
            # entrée par adresse vue depuis le démarrage.
            if len(self._seen) > 1024:
                for key in [k for k, v in self._seen.items()
                            if not v or now - v[-1] > self.window]:
                    del self._seen[key]
            hits = self._seen.setdefault(who, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.quota:
                return False
            hits.append(now)
            return True


class PublicHandler(SimpleHTTPRequestHandler):
    """Le site et le direct, rien d'autre, en lecture seule.

    Volontairement séparé de `Handler` plutôt que dérivé : hériter aurait fait
    porter à cette classe tout ce que l'autre sait servir, et une liste blanche
    qui hérite d'un « sert tout » finit toujours par fuir. Ici, la seule façon
    d'exposer un fichier est de l'inscrire dans `PUBLIC_PAGES`.
    """

    files = RateLimit(*PUBLIC_QUOTA_FILES)
    live = RateLimit(*PUBLIC_QUOTA_LIVE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_request(self, code="-", size="-"):
        """Une ligne par refus, rien pour le reste.

        C'est ce qu'on relit après une nuit d'exposition. Tracer les succès
        noierait le fichier : une page tire ses modules, ses trois JSON et
        jusqu'à vingt-cinq portraits, et le direct revient toutes les quinze
        secondes par onglet.
        """
        if isinstance(code, int) and code >= 400:
            # Le chemin vient du dehors : on le borne et on retire les sauts de
            # ligne, sinon une URL choisie écrirait de fausses lignes de trace.
            demande = (self.path or "")[:120].replace("\r", "").replace("\n", "")
            print(f"  public : {code} {self.command} {demande} "
                  f"({self._who()})", flush=True)

    def log_message(self, fmt, *args):
        pass

    # -- identité du demandeur --------------------------------------------
    def _who(self) -> str:
        """L'adresse du client.

        Derrière un tunnel, la connexion vient toujours de 127.0.0.1 : sans
        `CF-Connecting-IP`, tout le monde partagerait le même quota. Cloudflare
        réécrit cet en-tête à chaque passage, un client ne peut pas le choisir —
        mais il n'est digne de foi que **parce que** ce port n'est atteignable
        que par le tunnel. Exposer 8801 en direct invaliderait ce raisonnement.
        """
        forwarded = self.headers.get("CF-Connecting-IP")
        if forwarded:
            return forwarded.split(",")[0].strip()[:45]
        return self.client_address[0]

    # -- ce qui est servi --------------------------------------------------
    def _relative(self) -> str | None:
        """Le chemin demandé ramené à une clé simple, ou `None` s'il est louche."""
        path = unquote(self.path.split("?")[0].split("#")[0])
        # `::` vise les flux ADS de NTFS (`page.html::$DATA` rend la source),
        # `\` est un séparateur sous Windows là où l'URL n'en connaît qu'un.
        if "\\" in path or "::" in path or "\x00" in path:
            return None
        parts = []
        for seg in path.split("/"):
            if seg in ("", "."):
                continue
            # Windows ignore les points et espaces finaux : `index.html.` ouvre
            # le même fichier en manquant la comparaison exacte.
            if seg == ".." or seg != seg.rstrip(". "):
                return None
            parts.append(seg)
        return "/".join(parts) or "index.html"

    @staticmethod
    def _allowed(rel: str) -> bool:
        if rel in PUBLIC_PAGES or rel in PUBLIC_DATA:
            return True
        # Sous-arbres : l'empreinte de contenu d'`assets/` change à chaque
        # build, on ne peut pas l'énumérer. L'extension borne ce qu'on y sert.
        if rel.startswith("assets/") and rel.endswith((".css", ".js")):
            return True
        if rel.startswith("data/photos/") and rel.endswith(".webp"):
            return True
        # Aucun dossier ne peut correspondre : le listing est donc impossible,
        # sans avoir à désarmer `list_directory`.
        return False

    def _deny(self, status: int) -> None:
        """Refuse sans rien apprendre au demandeur.

        Toujours le même corps : distinguer « interdit » de « absent »
        dessinerait la carte de ce qui existe.
        """
        body = json.dumps({"error": "introuvable"}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # -- verbes ------------------------------------------------------------
    def do_GET(self):
        rel = self._relative()
        if rel is None:
            self._deny(404)
            return
        if rel == "api/live":
            if not self.live.allow(self._who()):
                self._deny(429)
                return
            self._json_live()
            return
        # Le quota se prend avant la liste blanche : un scanner qui tape mille
        # chemins absents doit être freiné comme les autres.
        if not self.files.allow(self._who()):
            self._deny(429)
            return
        if not self._allowed(rel):
            self._deny(404)
            return
        super().do_GET()

    def do_HEAD(self):
        rel = self._relative()
        if rel is None or rel == "api/live" or not self._allowed(rel):
            self._deny(404)
            return
        super().do_HEAD()

    def do_POST(self):
        # `/api/refresh` n'existe pas ici : une collecte complète lance Chrome
        # pour une minute et sollicite Forebet. C'est la règle « à la main,
        # jamais périodique » — elle ne survivrait pas à une boucle anonyme.
        self._deny(405)

    def _json_live(self) -> None:
        snapshot = Handler.live_collector().snapshot()
        state = snapshot.get("state") or ""
        # `state` porte `str(exc)` en cas de panne : chemins et internes.
        # Dehors, on dit qu'on ne sait pas, et la trace reste dans la console.
        if state.startswith("indisponible"):
            state = "indisponible"
        body = json.dumps({
            "state": state,
            "live": snapshot.get("live") or {},
            "watching": snapshot.get("watching") or [],
            "collected": snapshot.get("collected"),
            "now_iso": datetime.now().isoformat(timespec="seconds"),
            "interval": LIVE_INTERVAL,
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # Le site ne charge que ses propres fichiers : les écussons et les
        # portraits sont servis d'ici, pas cherchés chez la source.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; "
                         "style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        if self.command in ("GET", "HEAD") and self.path.split("?")[0].endswith(
                (".html", ".json")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sert la console en local, avec un bouton « Rafraîchir » qui collecte.")
    parser.add_argument("--port", type=int, default=8800)
    parser.add_argument("--scope", choices=["upcoming", "all", "played"],
                        default="all",
                        help="quelles fiches récupérer à chaque rafraîchissement "
                             "(défaut : toutes)")
    parser.add_argument("--no-open", action="store_true",
                        help="ne pas ouvrir le navigateur au démarrage")
    # Le site et la console sont servis tous les deux — c'est le même dossier.
    # Ce choix ne porte que sur la page ouverte au démarrage. Le site consomme
    # `/api/live` depuis le 11/08/2026 : servi ici, son score bouge tout seul,
    # ce que la version publiée sur GitHub Pages ne peut pas faire.
    parser.add_argument("--site", action="store_true",
                        help="ouvrir le site public plutôt que la console interne")
    parser.add_argument("--public-port", type=int, default=None,
                        help="ouvrir en plus un port exposable : le site et le "
                             "direct seuls, en lecture seule. C'est celui-ci "
                             "que le tunnel doit viser, jamais --port.")
    args = parser.parse_args()

    if args.public_port == args.port:
        print("--public-port doit différer de --port : le port exposé ne sert "
              "ni la console, ni le code, ni /api/refresh.", file=sys.stderr)
        return 1

    if not (ROOT / PAGE).exists():
        # Le port public ne sert jamais la console : refuser de démarrer sans
        # elle condamnerait l'auto-hébergement à dépendre d'un fichier que
        # `.gitignore` écarte, donc absent d'un clone frais.
        if not args.public_port:
            print(f"{PAGE} n'existe pas encore — lance d'abord "
                  f"`python build_console.py --fixtures --scope all`.",
                  file=sys.stderr)
            return 1
        print(f"{PAGE} n'existe pas : la console ne sera pas servie. "
              f"Le site et le direct, si.", file=sys.stderr)
        args.site = True

    # Les options que `assemble()` attend. `force=True` : cliquer sur
    # « Rafraîchir » veut dire « va rechercher », pas « ressers-moi le cache ».
    Handler.options = SimpleNamespace(
        urls=[], file=[], fixtures=True, scope=args.scope, force=True,
        no_calendar=False, no_stats=False, no_hosts=False,
    )

    page = SITE_PAGE if args.site else PAGE
    url = f"http://127.0.0.1:{args.port}/{page}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"servi sur http://127.0.0.1:{args.port}/ — "
          f"console : /{PAGE} · site : /{SITE_PAGE}")
    print("dans la console, « Rafraîchir » relance une collecte complète — "
          "compter une minute.")
    print(f"le direct suit les matchs en cours, relevés toutes les "
          f"{int(LIVE_INTERVAL)} s, des DEUX côtés : la console par son bouton, "
          f"le site tout seul.")

    # Le port public vit dans un fil : le collecteur et le verrou de collecte
    # sont des attributs de classe, les deux écouteurs les partagent donc sans
    # rien avoir à se dire.
    public = None
    if args.public_port:
        public = ThreadingHTTPServer(("127.0.0.1", args.public_port), PublicHandler)
        threading.Thread(target=public.serve_forever, daemon=True,
                         name="public").start()
        print(f"port public sur http://127.0.0.1:{args.public_port}/ — "
              f"site et direct seuls, lecture seule. C'est CE port que le "
              f"tunnel doit viser.")
    print("Ctrl+C pour arrêter.")

    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")
    finally:
        server.server_close()
        if public is not None:
            public.shutdown()
            public.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
