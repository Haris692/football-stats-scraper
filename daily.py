"""Le rafraîchissement de 8 h : collecter, régénérer, publier.

Une seule commande, pensée pour être lancée par le planificateur de tâches
Windows sans personne devant l'écran (`schedule_daily.ps1` l'y inscrit).

**Pourquoi une tâche locale et pas un agent dans le cloud** : la collecte a
besoin du Chrome de cette machine et de sa clearance Cloudflare, gardée dans
`.chrome-profile/`. Depuis ailleurs, Forebet répond un challenge que rien ne
peut résoudre. La planification doit donc vivre là où vit le profil.

⚠️ **Ce script revient sur la règle « déclenchement manuel strict, jamais
périodique »** héritée de `kuwait-football`. Elle visait à ne pas marteler la
source : une fois par jour, et en laissant le cache servir tout ce qui est
figé, reste très loin du martèlement. Le mode direct avait déjà déplacé cette
règle une première fois, pour la même raison.

    python daily.py                 # collecte, régénère, commite, pousse
    python daily.py --no-push       # tout sauf la publication
    python daily.py --dry-run       # dit ce qu'il ferait, ne fait rien

L'ordre compte : `fetch_events` avant `build_console`, parce que le build ne
collecte pas les rencontres Sofascore, il lit le `data/events.json` déjà écrit.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "daily.log"

# Ce que la publication emporte. Volontairement énuméré plutôt que `git add -A`
# : un `.chrome-profile` ou un `cache/` qui échapperait au `.gitignore` n'a
# rien à faire dans un commit automatique que personne ne relit.
PUBLISHED = ["index.html", "index.data.json", "data/events.json",
             "data/squads.json"]

STEPS = [
    # Les effectifs bougent peu, mais le classement des buteurs change à chaque
    # journée — et c'est lui qui alimente les buts par joueur.
    (["fetch_squads.py"], "effectifs et buteurs"),
    # Les journées passées sortent du cache ; seules la journée courante et les
    # suivantes repartent sur le réseau.
    (["fetch_events.py"], "rencontres, chronologies et journées"),
    (["build_console.py", "--fixtures", "--scope", "all", "--out", "index.html"],
     "console publiée"),
]


def log(message: str) -> None:
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run(command: list[str], dry: bool) -> bool:
    printable = " ".join(command)
    if dry:
        log(f"(à blanc) {printable}")
        return True
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode:
        log(f"ÉCHEC ({done.returncode}) {printable}")
        for line in (done.stderr or done.stdout or "").splitlines()[-12:]:
            log(f"    {line}")
        return False
    return True


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def publish(dry: bool, push: bool) -> None:
    """Commite ce qui a bougé, et rien s'il n'a rien bougé.

    Une collecte qui ne change rien — pas de match depuis la veille — ne doit
    pas laisser un commit vide par jour dans l'historique.
    """
    existing = [p for p in PUBLISHED if (ROOT / p).exists()]
    changed = git("diff", "--name-only", "--", *existing).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard", "--",
                    *existing).stdout.split()
    touched = sorted(set(changed) | set(untracked))

    if not touched:
        log("rien de nouveau : aucun commit")
        return
    log(f"modifié : {', '.join(touched)}")
    if dry:
        log("(à blanc) commit et push sautés")
        return

    git("add", "--", *touched)
    stamp = datetime.now().strftime("%d/%m/%Y")
    message = (f"chore: rafraichissement quotidien du {stamp}\n\n"
               f"Collecte automatique de 8 h (daily.py).\n"
               f"Fichiers touches : {', '.join(touched)}.\n\n"
               f"Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    done = git("commit", "-m", message)
    if done.returncode:
        log(f"commit refusé : {(done.stderr or done.stdout).strip()[:200]}")
        return
    log("commit écrit")

    if not push:
        log("push non demandé — le commit reste local")
        return
    done = git("push", "origin", "main")
    if done.returncode:
        log(f"push refusé : {(done.stderr or done.stdout).strip()[:200]}")
        return
    log("poussé sur origin/main")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rafraîchissement quotidien.")
    parser.add_argument("--no-push", action="store_true",
                        help="commiter sans publier")
    parser.add_argument("--dry-run", action="store_true",
                        help="annoncer les étapes sans rien exécuter")
    args = parser.parse_args()

    log("— rafraîchissement quotidien —")
    for command, label in STEPS:
        log(f"· {label}")
        if not run([sys.executable, *command], args.dry_run):
            # On s'arrête à la première étape ratée : régénérer la page à
            # partir d'une collecte incomplète publierait une régression
            # silencieuse, ce qui est pire que de ne rien publier.
            log("étape en échec — on n'ira pas plus loin, rien n'est publié")
            return 1

    publish(args.dry_run, push=not args.no_push)
    log("terminé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
