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

Le rafraîchissement est **déclenché à la main**, jamais périodique : c'est une
exigence reprise du projet `kuwait-football`, et ça évite de marteler la source.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from build_console import assemble, build, data_file_for, make_payload

ROOT = Path(__file__).resolve().parent
PAGE = "console.html"


class Handler(SimpleHTTPRequestHandler):
    """Fichiers statiques, plus un point d'entrée `/api/refresh`."""

    options: SimpleNamespace
    # Une collecte à la fois : deux clics rapprochés lanceraient deux Chrome et
    # se disputeraient le même port CDP.
    lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):  # le log par défaut est trop bavard
        if "/api/" in (self.path or ""):
            print(f"  {self.command} {self.path}", flush=True)

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
    args = parser.parse_args()

    if not (ROOT / PAGE).exists():
        print(f"{PAGE} n'existe pas encore — lance d'abord "
              f"`python build_console.py --fixtures --scope all`.", file=sys.stderr)
        return 1

    # Les options que `assemble()` attend. `force=True` : cliquer sur
    # « Rafraîchir » veut dire « va rechercher », pas « ressers-moi le cache ».
    Handler.options = SimpleNamespace(
        urls=[], file=[], fixtures=True, scope=args.scope, force=True,
        no_calendar=False, no_stats=False,
    )

    url = f"http://127.0.0.1:{args.port}/{PAGE}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"console servie sur {url}")
    print("le bouton « Rafraîchir » y relance une collecte complète — "
          "compter une minute.\nCtrl+C pour arrêter.")
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
