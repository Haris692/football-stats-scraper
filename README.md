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
| `fetch_squads.py` | effectifs des 8 clubs, via Sofascore (230 joueurs) |
| `crests.py` | écussons des clubs et couleurs dominantes qu'on en extrait |
| `build_console.py` | assemble `console.html` |
| `build_json.py` | assemble `output/` |
| `serve.py` | sert la console en local et lui donne un vrai bouton « Rafraîchir » |
| `shoot.py` | captures d'écran d'une page web vers un dossier (outil autonome) |

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

**Sofascore complète Forebet, il ne le remplace pas** : il apporte les
effectifs, les entraîneurs et le classement des buteurs — mais **aucun tir**.
Le partage est donc : Forebet pour les statistiques de match, Sofascore pour les
gens. Les compositions n'existent nulle part pour ce championnat.

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
`data/squads.json` **n'est plus une saisie manuelle** : `fetch_squads.py` le
remplit depuis Sofascore (230 joueurs sur 8 clubs, avec poste, numéro, pays et
buts). Le relancer après un mercato :

```
python fetch_squads.py --summary
python build_console.py --fixtures --scope all
```

## Cache

`cache/` garde les pages HTML et les réponses JSON, sous un nom lisible suivi
d'un hash court. Rien n'est retéléchargé tant que l'entrée n'a pas dépassé son
âge maximum — 6 h par défaut, 30 jours pour les statistiques d'un match terminé
(qui ne bougeront plus), 12 min pour un match à venir ou en cours.

Le vider est sans risque : tout se retélécharge. `.chrome-profile/` est le profil
Chrome dédié au scraper ; le supprimer oblige à repasser le challenge Cloudflare.

## Captures d'écran (`shoot.py`)

Outil à part, sans rapport avec la collecte : il photographie les pages qu'on
lui donne et range les images dans un dossier. Il réutilise le Chrome piloté de
`browser.py` — donc un profil dédié, tes onglets ne bougent pas.

```
python shoot.py example.com
python shoot.py a.com b.com --out captures/lundi --full
python shoot.py monsite.fr --size 1440x900 --size 390x844     # desktop + mobile
python shoot.py monsite.fr --element "main" --scale 2          # un bloc, en retina
python shoot.py monsite.fr --hide "#cookie-banner" --dark
```

| option | effet |
|---|---|
| `--out DIR` | dossier de sortie (défaut : `captures/`) |
| `--full` | page entière et non la seule partie visible |
| `--element SEL` | ne capturer qu'un élément (sélecteur CSS) |
| `--size LxH` | taille de rendu, **répétable** |
| `--scale N` | densité de pixels ; `2` pour du retina |
| `--wait SEL` | attendre ce sélecteur avant de déclencher |
| `--delay S` | attendre S secondes de plus |
| `--hide SEL` | retirer des éléments avant la photo, **répétable** |
| `--dark` | forcer le thème sombre de la page |
| `--format` / `--quality` | `png` (défaut) ou `jpeg` |
| `--name` | nom de fichier imposé (une seule URL, une seule taille) |
| `--profile [NOM]` | utiliser **ton** profil Chrome (`Default`, `Profile 1`…) |
| `--user-data-dir D` | dossier de profils, si le tien n'est pas à l'emplacement habituel |

### Utiliser ton profil Chrome

Par défaut l'outil ouvre un profil dédié, vierge : il ne voit que ce qu'un
visiteur anonyme verrait. `--profile` lui donne **le tien** — tes sessions, donc
les pages derrière une authentification.

```
python shoot.py monsite.fr --profile              # profil « Default »
python shoot.py monsite.fr --profile "Profile 1"  # un autre profil
```

⚠️ **Chrome doit être fermé au moment du lancement.** Un Chrome déjà démarré ne
peut plus ouvrir son port de débogage : relancer l'exécutable rend simplement la
main à l'instance existante. L'outil le détecte et te le dit au lieu d'attendre.

L'alternative, si tu ne veux rien fermer : démarre Chrome **une fois** avec

```
chrome.exe --remote-debugging-port=9333
```

Il s'utilise ensuite normalement, et toutes les captures suivantes s'y
raccrocheront.

Deux garde-fous, parce que ce Chrome-là est le tien :

- **on ouvre notre propre onglet** au lieu de réutiliser le premier — sinon ta
  page en cours partirait ailleurs ;
- **on ne ferme jamais ton navigateur** à la fin, seulement l'onglet ouvert.

À savoir : une capture prise avec ton profil peut contenir des informations
personnelles (nom de compte, notifications, contenu privé). Regarde l'image
avant de la partager.

Sans `--wait`, l'outil attend que le réseau se calme — sinon on photographie une
page à moitié peinte. `--hide` **retire** les éléments du DOM plutôt que de
cliquer dessus : cliquer sur un bandeau de cookies, ce serait accepter quelque
chose à ta place.

Il **ne suit aucun lien** : il capture exactement les adresses demandées. C'est
un appareil photo, pas un robot d'exploration.

⚠️ **Deux pièges de densité, réglés mais à connaître** si tu touches au code.
`page.screenshot()` de Playwright **ignore** la densité imposée par l'émulation :
il ne sait produire que du 1x ou la densité réelle de l'écran — sur un écran
Windows à 150 %, un `--scale 2` sortait en 1,5x. La capture passe donc par CDP
`Page.captureScreenshot`, qui la respecte au pixel près. Et les métriques
doivent être **réappliquées après la navigation** : `page.goto` les remet à
celles de la fenêtre.

`captures/` est ignoré par git.

## Langue

La console s'affiche en **français ou en anglais**. La langue est choisie à
l'ouverture d'après le navigateur : sa **première** langue déclarée décide — un
visiteur en `en-GB, fr` lit le français mais préfère l'anglais, on lui sert donc
l'anglais. Tout ce qui n'est pas francophone bascule en anglais.

Le bouton **FR / EN** de la barre du haut force la langue, et le choix est
retenu (`localStorage`). Il affiche la langue vers laquelle il bascule.

Le bouton **Brief : FR / EN** est **séparé**, et c'est voulu : le carrousel
Instagram est du contenu éditorial destiné à un compte donné, sa langue est un
choix de publication. Elle n'a pas à changer parce qu'un visiteur de passage a
un navigateur anglais. Par défaut, l'interface suit le navigateur et le brief
reste en français.

Côté code, le dictionnaire `EN` est indexé **par la chaîne française elle-même**
plutôt que par une clé abstraite : `t("Comparatif")` se lit sans aller consulter
la table, et une entrée oubliée retombe sur le français au lieu d'afficher une
clé nue. Les phrases à trous vivent dans `PH`, écrites en entier dans les deux
langues — une traduction ne se fabrique pas en recollant des fragments traduits
séparément.

⚠️ Les libellés de rubriques (`Corners`, `Hors-jeu`, `Six mètres`…) viennent des
pages **françaises** de Forebet : ce sont des **clés de données**, pas de
l'interface. On les traduit à l'affichage, jamais dans la clé.

## Le bouton « Rafraîchir »

La console a un bouton **Rafraîchir**. Il ne fait pas la même chose partout, et
il le dit sous la barre d'outils :

- **Servie par `serve.py`**, la page déclenche une **vraie collecte**. C'est
  Python qui pilote Chrome, franchit le challenge Cloudflare, réécrit
  `console.html` et `data.json`, puis renvoie la charge utile fraîche. La page
  se redessine sans être rechargée. Compter environ une minute.

  ```
  python serve.py            # http://127.0.0.1:8800, ouvre le navigateur
  python serve.py --port 9000 --scope played
  ```

- **Publiée sur GitHub Pages, ou ouverte en `file://`**, elle ne peut pas :
  **Forebet n'envoie aucun en-tête CORS** (vérifié le 10/08/2026 depuis
  l'origine `github.io` : `TypeError: Failed to fetch` sur la page ligue comme
  sur l'endpoint statistiques). Le bouton va alors chercher le `data.json`
  déposé à côté de la page. Il rapporte donc ce qui a été **publié** depuis la
  génération de la page — et annonce clairement quand il n'y a rien de plus
  récent.

Le fichier de données est écrit à chaque build, à côté de la page et **sous son
nom** : `index.html` → `index.data.json`, `console.html` → `console.data.json`.
Ainsi un build local n'écrase pas la donnée publiée. Il pèse 165 Ko contre
608 Ko pour la page : **les écussons en sont retirés**, puisque la page les a
déjà et qu'ils ne changent pas. La charge utile reste **aussi** embarquée dans
la page — la console doit continuer de s'ouvrir seule, hors ligne.
`--no-data-file` pour ne pas l'écrire.

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

`index.html` et `index.data.json` sont donc les seuls artefacts de build que le
dépôt garde ; `console.html`, `console.data.json` et `output/` restent ignorés.

## Le reste

`PROGRESS.md` tient le journal du projet : sources évaluées et écartées **avec
la preuve**, pièges de parsing, sélecteurs relevés, et les points encore
ouverts. À lire avant de re-sonder une source — la plupart l'ont déjà été.
