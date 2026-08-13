# Instructions pour Claude

Ce fichier est la mémoire du projet. `PROGRESS.md` (~1800 lignes) contient le
détail et le pourquoi ; **le lire avant toute décision d'architecture**. Ici ne
figurent que les règles qu'on ne peut pas deviner en lisant le code, et les
pièges qui ont déjà coûté du temps.

On écrit **en français**, code, commentaires, commits et réponses.

## Ce que fait le projet

Collecte et publie les statistiques de la **Division 1 koweïtienne** (2e
division, 8 clubs). Trois sorties alimentées par une seule collecte : le **site**
(`index.html` + 5 pages, données par `fetch`, **exige un serveur**),
**`console.html`** (outil interne, fichier unique, hors ligne, générateur de
brief Instagram) et **`output/`** (JSON par match).

Objectif énoncé : **présenter le projet à des clubs koweïtiens**, et produire du
contenu Instagram.

## ⚠️ Les cinq règles à ne jamais enfreindre

1. **On édite `src/`, JAMAIS `assets/`.** `build_site.py` recopie `src/` sous
   `assets/<empreinte-de-contenu>/` et réécrit les pages. Un navigateur cache
   chaque module ES **par URL** : après un déploiement il peut mêler un module
   neuf et un périmé, ce qui donne un **écran noir**. Un `?v=` sur l'entrée **ne
   corrige pas** le problème — ne pas retenter cette piste. Relancer
   `python build_site.py` après toute modification de `src/`.

2. **Des statistiques, pas des pronostics.** Forebet propose dix marchés ;
   `parse_match.py` les extrait encore mais aucune sortie ne les diffuse. Une
   première console bâtie autour d'eux a été refaite. Ne rien publier qui
   prédise un score.

3. **Ne jamais deviner un appariement de joueur.** `match: "none"` est un
   résultat valide, pas une erreur à corriger au jugé. Un joueur peut
   simplement manquer chez Sofascore.

4. **Ne jamais retoucher une capture d'écran**, même fausse. Celle de
   Sulaibikhat annonce « BURGAN » pour un match contre Sporty : l'erreur est
   notée dans la provenance, l'image reste telle quelle. Une pièce
   justificative corrigée ne prouve plus rien.

5. **Toujours demander confirmation avant `git push`**, en résumant les
   modifications. Les commits sont en français, style
   `feat(portée): description`.

## Commandes

```bash
python daily.py                              # rafraîchissement quotidien complet
python build_site.py --fixtures --scope all  # régénère site.json + assets + pages
python serve.py                              # sert le site sur :8800, + /api/live
python fetch_players.py --club yarmouk       # fiches d'un club (hors daily.py)
```

Clés de club : `yarmouk`, `sulaibikhat`, `sahel`, `jazira`, `khaitan`,
`burgan`, `shamiya`, `sporty`.

Il faut **Google Chrome installé** : Sofascore répond 403 à `urllib`, mais pas à
un `fetch()` exécuté dans une page sofascore.com. `browser.py` pilote Chrome en
CDP sur le port 9333.

⚠️ **`fetch_players.py` n'est pas dans `daily.py`**, retiré volontairement : 230
requêtes lentes pour une donnée figée, et comme toute étape en échec annule la
publication, sa fragilité emportait les scores. Il **cumule** désormais au lieu
d'écraser — avant, une passe `--club` effaçait les sept autres clubs.

## Qui fait autorité, source par source

| Donnée | Autorité | Remarque |
|---|---|---|
| Qui reçoit | **Flashscore** (`hosts.py`) | tranché le 11/08/2026, ne pas re-débattre |
| Classement des buteurs | **`fetch_scorers.py`** | jamais un classement dérivé des effectifs |
| Statistiques de match | Forebet `get_evs_n.php` | ~la moitié des rencontres |
| Chronologies, effectifs | Sofascore | tournoi `20044`, saison 25/26 `75693` |
| Compositions | les clubs, à la main | voir plus bas |

## ❌ Ne pas re-sonder — vérifié endpoint par endpoint

Sofascore, sur cette division : `lineups`, `best-players`, `graph`, `odds`,
`tv`, `shotmap`, `average-positions`, `incidents` → **tous 404**.
`event/{id}/statistics` ne contient que « Red cards ». `/standings/` est
interdit par `robots.txt`.

**Il n'y a donc ni coordonnées, ni xG, ni notes** : mplsoccer et les outils du
même genre sont inutilisables ici. L'endpoint des buteurs accepte
`fields=assists,appearances,minutesPlayed` et renvoie ces clés **à `null`** — ne
pas croire y avoir trouvé les minutes.

**Forebet n'envoie aucun en-tête CORS** (vérifié depuis l'origine `github.io`) :
la page publiée sur GitHub Pages ne peut pas collecter. Ne pas promettre de
rafraîchissement en ligne.

## Compositions : le seul circuit humain

Aucune source ne publie de feuille de match. Les clubs publient leur onze sur
Instagram. Haris dépose les captures dans
`data/inbox/<match_id>-<domicile>-<extérieur>-<jj>-<mm>/` (ignoré par git,
pièces justificatives). Claude lit, apparie aux effectifs Sofascore, **soumet
les doutes plutôt que de deviner**, écrit `data/lineups.json` (versionné),
régénère et propose le push.

- **Un dossier vide, ou un seul club sur deux, signifie que le club n'a rien
  publié.** L'absence est une donnée : le côté vaut `null`. Ne pas relancer
  Haris pour « compléter ».
- Le numéro ne suffit pas : 152 joueurs sur 228 seulement en portent un.
- **Le club nomme souvent le père, Sofascore la famille** (`Musaed Trad` =
  `Musaed Al Enezi`). C'est une convention, pas une faute de frappe.
- **Ce sont des visuels d'avant-match : aucune minute jouée.** Les visuels de
  **changements** valent le plus, et manquent toujours.

## Les pièges qui ont déjà coûté du temps

**Un cache sans date est un gel.** `fetch_fixtures.load_league_html()` rendait
son cache dès qu'il existait. Or la page ligue est la seule à porter `score` et
`played` : le site affichait « à venir » des rencontres jouées la veille.
Corrigé par `LEAGUE_MAX_AGE_HOURS = 1.0`.

**Un faux crédible est le pire des faux.** Le classement des buteurs, dérivé des
effectifs, perdait les 8 joueurs partis en cours de saison — et leurs 33 buts,
dont le premier de la division. Rien n'était vide, rien n'était en erreur, le
tableau était juste faux.

**`name_ar` de Sofascore n'est pas une clé d'appariement.** Présent sur toutes
les fiches, donc tentant, mais c'est une translittération automatique : le club
écrit `العنزي` là où Sofascore écrit `العنيزي`. Pire, « Abdulrahman Sherhan » y
porte `دانيال لوغو`, le nom d'un autre joueur. Indice, jamais autorité.

**Sofascore a des doublons de joueurs.** Yarmouk a deux fiches du même gardien
(`809501` / `2072650`, même n°34, nés à quatre jours d'écart) et deux João
Vitor. Départager par compétition inscrite et nom arabe exact, jamais au jugé.

## Direction artistique et conventions de code

DA « **le tableau d'affichage à 19 h 25** » : fond `#0c1310`, accent `#f2c14e`,
**Bahnschrift**. Le site ne joue qu'en soirée, sous les projecteurs.

- **Aucune valeur brute hors de `src/css/tokens.css`.** Si une couleur n'y est
  pas, elle n'existe pas.
- Un composant = une classe racine. `el()` refuse le HTML en chaîne.
- Les liens vers un club passent par sa **clé**, jamais par son nom.
- Le helper des notes de méthode s'appelle **`methodNote`** — `note` était pris.
- **Domicile toujours bleu, extérieur toujours orange.** La couleur suit
  l'équipe, jamais son rang ni son résultat. Les couleurs extraites des écussons
  pilotent le prompt Instagram, **pas** les graphiques.
- Interface : trois onglets, tableau d'affichage collant, notes de méthode
  **repliées** (`<details class="note">`), rail des minutes. Tranché, ne pas
  re-débattre.

## Le direct

`serve.py` tient un fil de fond unique qui relève les matchs en cours une fois
par minute ; la page lit un instantané (`GET /api/live`), elle ne collecte pas.
Le chemin est **relatif** (`api/live`) : 404 signifie « pas de serveur », et on
se tait. Rien de tout ça sur GitHub Pages.

⚠️ Chrome n'est lancé que si un match est en cours **et** que quelqu'un regarde
(`LIVE_IDLE_STOP = 180.0`). Au repos, le serveur tient dans 43 Mo.

## Auto-hébergement (décidé le 13/08/2026)

Le projet doit tourner en 24/7 sur un **Dell Pro Micro** sous Windows, qui
servira **le site entier et l'API** — même origine obligatoire, puisque
`live.js` appelle `api/live` en relatif. GitHub Pages reste une vitrine
statique de repli. Exposition prévue par **Cloudflare Tunnel**.

Machine sous Windows, donc **aucun portage** : `schedule_daily.ps1` et le
lancement Chrome fonctionnent tels quels. Ne pas proposer systemd, cron ni
Chromium ARM.

**Reste à faire avant la mise en ligne** : une revue de sécurité de `serve.py`
(c'est un `SimpleHTTPRequestHandler` écrit pour localhost), puis le tunnel.

## Points ouverts

1. Les **visuels de changements** — seul chemin vers les minutes jouées.
2. Le flux **SSE `/glvs/`**, débranché : il apporterait la minute de jeu, absente
   de `gmc=1`. À faire consommer par `serve.py`, pas par la page.
3. Quatre **diffuseurs** manquants dans `data/broadcasts.json`.
4. Les buteurs sans fiche joueur (`fetch_players.py --club` sur sulaibikhat,
   burgan, sporty).
5. **`shoot.py` n'est documenté nulle part** — trou de suivi connu.
