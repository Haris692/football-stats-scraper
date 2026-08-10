# football-stats-scraper

Collecte et met en forme les **statistiques de la Division 1 koweïtienne**
(2e division : Yarmouk, Sulaibikhat, Sahel, Al Jazira, Khaitan, Burgan,
Al Shamiya, Sporty), à partir de [Forebet](https://www.forebet.com).

Deux sorties, alimentées par la même collecte :

- **`console.html`** — une console autonome, à ouvrir dans un navigateur. Aucune
  requête à l'ouverture, aucun asset externe : elle fonctionne hors ligne, y
  compris en `file://`. Elle embarque aussi un générateur de brief pour un
  carrousel Instagram de 4 slides.
- **`output/`** — le même contenu en JSON, un fichier par match plus un index,
  pour être consommé par un autre programme.

Le projet publie des **relevés, pas des pronostics**. Forebet en propose dix
marchés ; `parse_match.py` continue de les extraire, mais ni la console ni
l'export ne les diffusent. Aucune sortie ne prédit de score.

## Installation

```
pip install -r requirements.txt
```

Il faut aussi **Google Chrome** installé (le vrai, pas le Chromium de
Playwright). Forebet est derrière un challenge Cloudflare qu'aucune requête
directe ne franchit : `browser.py` lance un Chrome normal avec
`--remote-debugging-port=9333` et s'y attache en CDP, ce qui passe. Inutile de
lancer `playwright install` — le navigateur téléchargé par Playwright ne sert
pas ici.

Le détail des tentatives écartées (urllib, curl, Playwright classique) est dans
`PROGRESS.md` : ne pas les refaire.

## Usage courant

```
python build_console.py --fixtures --scope all      # console complète
python build_json.py    --fixtures --scope all      # export JSON
```

`--fixtures` part de la page ligue, y lit les rencontres, puis récupère la fiche
de chacune. `--scope` choisit lesquelles : `upcoming` (défaut), `played`, `all`.

Options communes aux deux commandes :

| option | effet |
|---|---|
| `--force` | ignorer le cache disque et tout retélécharger |
| `--no-calendar` | ne pas compléter avec le calendrier Flashscore |
| `--no-stats` | ne pas récupérer les statistiques relevées des matchs |
| `--file <html>` | partir d'une page déjà enregistrée (répétable) |
| `<url> …` | partir d'URL de pages match précises |

Sans `--fixtures` ni argument, les deux scripts reprennent toutes les pages
match déjà en cache.

## Les scripts, un par un

| fichier | rôle |
|---|---|
| `browser.py` | récupération : Chrome + CDP, cache disque, throttling 2-5 s |
| `fetch_fixtures.py` | rencontres de la page ligue Forebet |
| `fetch_flashscore.py` | calendrier plus lointain (Forebet ne montre que 2 jours) |
| `parse_match.py` | parseur d'une fiche match : classement, forme, face à face |
| `fetch_stats.py` | statistiques relevées d'un match (possession, tirs, corners) |
| `crests.py` | écussons des clubs et couleurs dominantes qu'on en extrait |
| `build_console.py` | assemble `console.html` |
| `build_json.py` | assemble `output/` |

Chacun s'exécute seul et accepte `--help`. `parse_match.py` et `fetch_stats.py`
ont un `--summary` qui affiche un résumé lisible en console : c'est le moyen de
contrôler une extraction à l'œil sans ouvrir le JSON.

⚠️ Sous PowerShell, ne pas piper la sortie JSON dans `Select-Object -First N` :
la fermeture du tube fait sortir Python en 255, ce qui n'est pas une erreur de
parsing. Utiliser `--out` ou `--summary`.

## Ce que la source donne, et ce qu'elle ne donne pas

Sur cette division, Forebet renseigne **possession, tirs (total / cadrés / non
cadrés), corners, cartons, remplacements**, et parfois la chronologie des buts.
Restent vides : passes, fautes, tacles, arrêts, hors-jeu, compositions, noms des
buteurs.

Un zéro servi par la source ne veut donc pas dire zéro — il veut souvent dire
« non couvert ». `fetch_stats.py` supprime les rubriques nulles des deux côtés
plutôt que d'afficher « 0 faute », et la console nomme explicitement ce qu'elle
tait. Les **attaques dangereuses dépassent parfois les attaques totales** : le
couple est alors marqué `suspect` et n'est pas publié.

## Saisie manuelle

Aucune source automatique n'a été trouvée pour deux besoins. Les fichiers
correspondants sont donc à remplir à la main :

- **`data/broadcasts.json`** — la chaîne qui diffuse un match. Tant qu'une case
  est vide, la console affiche les chaînes habituelles comme une possibilité non
  confirmée, et le brief Instagram n'imprime rien : on ne publie pas une
  diffusion incertaine.
- **`data/squads.json`** (à créer) — les effectifs. La seule source complète
  trouvée est soccer365, dont le `robots.txt` interdit nommément ClaudeBot : ce
  fichier ne peut être qu'une collecte manuelle.

## Cache

`cache/` garde les pages HTML et les réponses JSON, sous un nom lisible suivi
d'un hash court. Rien n'est retéléchargé tant que l'entrée n'a pas dépassé son
âge maximum — 6 h par défaut, 30 jours pour les statistiques d'un match terminé
(qui ne bougeront plus), 12 min pour un match à venir ou en cours.

Le vider est sans risque : tout se retélécharge. `.chrome-profile/` est le profil
Chrome dédié au scraper ; le supprimer oblige à repasser le challenge Cloudflare.

## Publication

La console est publiée sur **GitHub Pages** :
<https://haris692.github.io/football-stats-scraper/>

C'est un **instantané**, figé à la date écrite en pied de page : la page ne
recharge rien à l'ouverture. La republier, c'est refaire une collecte et
recommitter :

```
python build_console.py --fixtures --scope all --out index.html
git commit -am "chore: console du JJ/MM"
git push
```

`index.html` est donc le seul artefact de build que le dépôt garde ;
`console.html` et `output/` restent ignorés.

## Le reste

`PROGRESS.md` tient le journal du projet : sources évaluées et écartées **avec
la preuve**, pièges de parsing, sélecteurs relevés, et les points encore
ouverts. À lire avant de re-sonder une source — la plupart l'ont déjà été.
