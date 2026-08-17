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
# `assets/` et les pages en font partie : `build_site.py` republie les fichiers
# servis sous une empreinte de contenu, et réécrit les pages pour la pointer.
# Une modification de `src/` non commitée à la main serait sinon perdue.
PUBLISHED = ["data/site.json", "data/crests.json", "data/events.json",
             "data/squads.json", "data/scorers.json", "assets",
             "index.html", "match.html", "clubs.html", "club.html",
             "classement.html", "calendrier.html", "joueur.html",
             "data/players.site.json", "data/players.json", "data/photos"]

STEPS = [
    # Les effectifs bougent peu, mais les buts accrochés à chaque joueur
    # changent à chaque journée — ils alimentent la fiche de club.
    (["fetch_squads.py"], "effectifs"),
    # Le classement des buteurs, à sa source. Une seule requête, et il ne
    # dérive plus des effectifs : c'est ce qui l'empêche de perdre un joueur
    # parti en cours de saison (voir `fetch_scorers`).
    (["fetch_scorers.py"], "classement des buteurs"),
    # Les journées passées sortent du cache ; seules la journée courante et les
    # suivantes repartent sur le réseau.
    (["fetch_events.py"], "rencontres, chronologies et journées"),
    # ⚠️ `fetch_players.py` N'EST PAS ICI, et retiré volontairement le
    # 12/08/2026. Ce que ce script doit publier chaque matin, c'est le
    # résultat des matchs de la veille et leur détail — pas la date de
    # naissance des joueurs, qui ne change jamais d'un jour à l'autre.
    #
    # L'étape coûtait 230 requêtes et des dizaines de minutes, et comme toute
    # étape en échec annule la publication (voir `main`), sa fragilité
    # emportait des données qui n'avaient rien à voir : le 12/08 les
    # rencontres du 11 étaient collectées à 08:33 et ne sont jamais arrivées
    # sur le site, parce que les fiches joueurs ont expiré après.
    #
    # Les fiches se collectent donc à la main, quand un effectif a bougé :
    #     python fetch_players.py --club yarmouk
    # Elles restent publiées (`PUBLISHED` les emporte) : le lendemain d'une
    # collecte manuelle, le rafraîchissement les pousse avec le reste.
    #
    # ⚠️ `build_site.py`, pas `build_console.py` : depuis le passage au site
    # multi-pages, `index.html` est une page statique versionnée qu'aucune
    # collecte ne réécrit. Ce sont les JSON de `data/` qui changent.
    (["build_site.py", "--fixtures", "--scope", "all"], "données du site"),
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


def resynchroniser(dry: bool) -> bool:
    """Aligner l'arbre sur `origin/main` AVANT de collecter.

    Deux postes publient désormais (le portable et le Dell en 24/7). Le 17/08,
    le daily du portable a été refusé parce que le Dell avait poussé le sien du
    14/08 : la collecte avait tourné, le commit était écrit, et rien n'est
    parti. Se remettre à jour d'abord évite le refus au lieu de le constater.

    ⚠️ **Ici et pas dans `publish()`** : à ce moment l'arbre est propre. Après
    la collecte, `data/*.json` est modifié, et un `merge` qui touche ces mêmes
    fichiers refuserait d'écraser le travail en cours.

    Une divergence — les deux postes ont commité — n'est pas résolue ici. La
    trancher demande de savoir laquelle des deux collectes fait foi, et `-X
    ours` appliqué à l'aveugle emporterait aussi du code poussé d'ailleurs.
    """
    if dry:
        log("(à blanc) resynchronisation sautée")
        return True

    if git("fetch", "origin").returncode:
        # Pas de réseau : la collecte reste utile pour le site servi en local
        # et pour `/api/live`. On continue, et le push dira ce qu'il en est.
        log("fetch impossible — on collecte quand même, sans garantie de push")
        return True

    compte = git("rev-list", "--left-right", "--count", "origin/main...HEAD")
    if compte.returncode:
        log(f"état git illisible : {(compte.stderr or '').strip()[:200]}")
        return True
    retard, avance = (int(n) for n in compte.stdout.split())

    if not retard:
        return True
    if avance:
        log(f"divergence : {avance} commit(s) ici, {retard} sur origin/main")
        log("à trancher à la main (l'autre poste a publié) — rien n'est collecté")
        return False

    done = git("merge", "--ff-only", "origin/main")
    if done.returncode:
        log(f"resynchronisation refusée : {(done.stderr or done.stdout).strip()[:200]}")
        return False
    log(f"resynchronisé sur origin/main ({retard} commit(s) repris)")
    return True


def publish(dry: bool, push: bool) -> bool:
    """Commite ce qui a bougé, et rien s'il n'a rien bougé.

    Une collecte qui ne change rien — pas de match depuis la veille — ne doit
    pas laisser un commit vide par jour dans l'historique.

    Rend False si la publication a échoué, pour que le planificateur voie
    autre chose qu'un succès.
    """
    existing = [p for p in PUBLISHED if (ROOT / p).exists()]
    changed = git("diff", "--name-only", "--", *existing).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard", "--",
                    *existing).stdout.split()
    touched = sorted(set(changed) | set(untracked))

    if not touched:
        log("rien de nouveau : aucun commit")
        return True
    log(f"modifié : {', '.join(touched)}")
    if dry:
        log("(à blanc) commit et push sautés")
        return True

    git("add", "--", *touched)
    stamp = datetime.now().strftime("%d/%m/%Y")
    message = (f"chore: rafraichissement quotidien du {stamp}\n\n"
               f"Collecte automatique de 8 h (daily.py).\n"
               f"Fichiers touches : {', '.join(touched)}.\n\n"
               f"Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    done = git("commit", "-m", message)
    if done.returncode:
        log(f"commit refusé : {(done.stderr or done.stdout).strip()[:200]}")
        return False
    log("commit écrit")

    if not push:
        log("push non demandé — le commit reste local")
        return True
    done = git("push", "origin", "main")
    if done.returncode:
        log(f"push refusé : {(done.stderr or done.stdout).strip()[:200]}")
        return False
    log("poussé sur origin/main")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Rafraîchissement quotidien.")
    parser.add_argument("--no-push", action="store_true",
                        help="commiter sans publier")
    parser.add_argument("--dry-run", action="store_true",
                        help="annoncer les étapes sans rien exécuter")
    args = parser.parse_args()

    log("— rafraîchissement quotidien —")
    if not args.no_push and not resynchroniser(args.dry_run):
        return 1
    for command, label in STEPS:
        log(f"· {label}")
        if not run([sys.executable, *command], args.dry_run):
            # On s'arrête à la première étape ratée : régénérer la page à
            # partir d'une collecte incomplète publierait une régression
            # silencieuse, ce qui est pire que de ne rien publier.
            log("étape en échec — on n'ira pas plus loin, rien n'est publié")
            return 1

    publie = publish(args.dry_run, push=not args.no_push)
    log("terminé")
    return 0 if publie else 1


if __name__ == "__main__":
    sys.exit(main())
