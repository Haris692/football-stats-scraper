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

Ce même dossier contient les deux façades, servies ensemble : la **console**
interne (`console.html`, fichier unique, générateur de brief Instagram) et le
**site** public (`index.html` et ses cinq pages). Depuis le 11/08/2026, le site
consomme lui aussi `/api/live` — servi ici, son score et ses statistiques se
mettent à jour seuls pendant la rencontre ; publié sur GitHub Pages, il ne
trouve pas ce point d'entrée et retombe sans bruit sur ses données figées.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from browser import CdpBrowser
from build_console import assemble, build, data_file_for, make_payload
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
        # Un match dont `ft_score` est rempli ne sera plus sondé.
        self._finished: set[int] = set()
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
            if not mid or int(mid) in self._finished:
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
        for mid, block in stats.items():
            if block.get("full_time"):
                self._finished.add(int(mid))
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
                cls.collector = LiveCollector(data_file_for(ROOT / PAGE))
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
    args = parser.parse_args()

    if not (ROOT / PAGE).exists():
        print(f"{PAGE} n'existe pas encore — lance d'abord "
              f"`python build_console.py --fixtures --scope all`.", file=sys.stderr)
        return 1

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
          f"le site tout seul.\nCtrl+C pour arrêter.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
