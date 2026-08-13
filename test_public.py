"""Ce que la façade publique de `serve.py` sert, et surtout ce qu'elle refuse.

Le port public est le seul point du projet exposé à Internet. Ce fichier fixe
son contrat : le site et le direct passent, tout le reste du dossier — l'outil
interne, le code, `.git/`, les pièces justificatives des clubs — répond 404.

Ce sont des cas de sécurité, pas de confort : un `PUBLIC_PAGES` élargi par
mégarde doit faire échouer ce test, pas fuiter en silence.

    python test_public.py
"""

from __future__ import annotations

import http.client
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from serve import PUBLIC_QUOTA_LIVE, PublicHandler, live_data_file

ROOT = Path(__file__).resolve().parent


def un_asset() -> str:
    """Une feuille de style d'`assets/`, empreinte comprise.

    Cherchée, jamais codée en dur : l'empreinte change à chaque
    `build_site.py`, et un chemin figé ferait échouer le test au premier build.
    """
    for css in sorted((ROOT / "assets").rglob("*.css")):
        return "/" + css.relative_to(ROOT).as_posix()
    return "/assets/introuvable.css"


# (méthode, chemin, statut attendu, pourquoi)
def cas() -> list[tuple[str, str, int, str]]:
    return [
        # -- ce que le site demande vraiment ---------------------------------
        ("GET", "/", 200, "la racine rend index.html"),
        ("GET", "/index.html", 200, "page du site"),
        ("GET", "/calendrier.html", 200, "page du site"),
        ("GET", "/classement.html", 200, "page du site"),
        ("GET", "/club.html", 200, "page du site"),
        ("GET", "/clubs.html", 200, "page du site"),
        ("GET", "/joueur.html", 200, "page du site"),
        ("GET", "/match.html", 200, "page du site"),
        ("GET", "/data/site.json", 200, "donnée du site"),
        ("GET", "/data/crests.json", 200, "écussons"),
        ("GET", "/data/players.site.json", 200, "fiches joueurs"),
        ("GET", un_asset(), 200, "feuille de style empreintée"),
        ("GET", "/api/live", 200, "le direct"),
        ("HEAD", "/index.html", 200, "HEAD autorisé sur le site"),

        # -- ce qui ne doit jamais sortir ------------------------------------
        ("GET", "/console.html", 404, "OUTIL INTERNE"),
        ("GET", "/console.data.json", 404, "données de l'outil interne"),
        ("GET", "/serve.py", 404, "code source"),
        ("GET", "/build_site.py", 404, "code source"),
        ("GET", "/PROGRESS.md", 404, "notes de travail"),
        ("GET", "/CLAUDE.md", 404, "notes de travail"),
        ("GET", "/README.md", 404, "notes de travail"),
        ("GET", "/requirements.txt", 404, "inventaire des dépendances"),
        ("GET", "/.git/config", 404, "dépôt git"),
        ("GET", "/.gitignore", 404, "dépôt git"),
        ("GET", "/daily.log", 404, "trace d'exécution"),
        ("GET", "/.chrome-profile/Default/Cookies", 404, "COOKIES DE SESSION"),

        # -- donnée interne : seuls trois JSON sont publiés -------------------
        ("GET", "/data/lineups.json", 404, "donnée non publiée"),
        ("GET", "/data/squads.json", 404, "donnée non publiée"),
        ("GET", "/data/players.json", 404, "donnée non publiée"),
        ("GET", "/data/events.json", 404, "donnée non publiée"),
        ("GET", "/data/inbox/LISEZ-MOI.txt", 404, "PIÈCES JUSTIFICATIVES"),

        # -- aucun listing de dossier ----------------------------------------
        ("GET", "/data/", 404, "listing de dossier"),
        ("GET", "/data", 404, "listing de dossier"),
        ("GET", "/assets/", 404, "listing de dossier"),
        ("GET", "/src/", 404, "listing de dossier"),

        # -- traversée et pièges Windows -------------------------------------
        ("GET", "/../serve.py", 404, "traversée"),
        ("GET", "/%2e%2e/serve.py", 404, "traversée encodée"),
        ("GET", "/..%2fserve.py", 404, "traversée encodée"),
        ("GET", "/data/photos/../site.json", 404, "traversée dans un sous-arbre"),
        # NTFS rend la source d'un fichier par son flux par défaut, et Windows
        # ignore les points finaux : deux façons de manquer l'égalité exacte
        # tout en ouvrant le bon fichier.
        ("GET", "/index.html::$DATA", 404, "flux ADS NTFS"),
        ("GET", "/index.html.", 404, "point final Windows"),
        # Encodé, parce qu'un espace brut ne franchit même pas le client HTTP :
        # c'est `%20` qu'un attaquant enverrait, et c'est après décodage que le
        # nom redevient dangereux.
        ("GET", "/index.html%20", 404, "espace final Windows"),
        ("GET", r"/\serve.py", 404, "séparateur Windows"),

        # -- lecture seule ----------------------------------------------------
        # Une collecte complète lance Chrome pour une minute et sollicite
        # Forebet : « à la main, jamais périodique » ne survivrait pas à une
        # boucle anonyme.
        ("POST", "/api/refresh", 405, "COLLECTE COMPLÈTE"),
        ("POST", "/", 405, "écriture"),
        ("PUT", "/index.html", 501, "verbe non implémenté"),
        ("DELETE", "/index.html", 501, "verbe non implémenté"),
    ]


def appel(port: int, methode: str, chemin: str) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(methode, chemin)
        rep = conn.getresponse()
        entetes = {k.lower(): v for k, v in rep.getheaders()}
        rep.read()
        return rep.status, entetes
    finally:
        conn.close()


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), PublicHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    erreurs = 0

    print("— ce qui passe, ce qui ne passe pas —")
    for methode, chemin, attendu, pourquoi in cas():
        try:
            code, _ = appel(port, methode, chemin)
        except Exception as exc:
            code = f"exception {exc}"
        if code != attendu:
            erreurs += 1
            print(f"  ÉCHEC {methode:6} {chemin:38} -> {code} "
                  f"(attendu {attendu} — {pourquoi})")

    print("— quota du direct —")
    # Le quota se prend par fenêtre glissante : une de plus que le quota doit
    # suffire à déclencher le refus, les cas ci-dessus en ayant déjà pris une.
    codes = [appel(port, "GET", "/api/live")[0]
             for _ in range(PUBLIC_QUOTA_LIVE[0] + 1)]
    if 429 not in codes:
        erreurs += 1
        print(f"  ÉCHEC {len(codes)} appels sans refus : {codes}")

    print("— en-têtes —")
    _, entetes = appel(port, "GET", "/index.html")
    for nom, attendu in (("x-content-type-options", "nosniff"),
                         ("referrer-policy", "no-referrer"),
                         ("cache-control", "no-store")):
        if entetes.get(nom) != attendu:
            erreurs += 1
            print(f"  ÉCHEC {nom} : {entetes.get(nom)!r} (attendu {attendu!r})")
    if "frame-ancestors 'none'" not in (entetes.get("content-security-policy") or ""):
        erreurs += 1
        print("  ÉCHEC la CSP n'interdit pas l'insertion en cadre")

    print("— repli du collecteur —")
    # Sans `console.data.json`, produit par l'outil interne et absent du dépôt,
    # le collecteur doit retomber sur `data/site.json` : sinon un poste qui ne
    # sert que le site public n'aurait aucune rencontre à suivre.
    if not live_data_file().exists():
        erreurs += 1
        print(f"  ÉCHEC {live_data_file()} n'existe pas")

    srv.shutdown()
    print(f"\n{len(cas())} cas — {erreurs} erreur(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
