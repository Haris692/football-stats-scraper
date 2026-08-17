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

## ⚠️ Les six règles à ne jamais enfreindre

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

6. **Ce qu'on expose passe par `--public-port`, jamais par `--port`.** Le port
   local sert la racine du dépôt : la console interne, le code, `PROGRESS.md`,
   `.git/`, `data/inbox/` et `.chrome-profile/` — donc les cookies de session du
   Chrome de collecte. Le port public ne sert qu'une **liste blanche**
   (`PUBLIC_PAGES`, `PUBLIC_DATA` dans `serve.py`). N'y ajouter un fichier
   qu'en sachant qu'il devient public, et faire passer `test_public.py`.

## Commandes

```bash
python daily.py                              # rafraîchissement quotidien complet
python build_site.py --fixtures --scope all  # régénère site.json + assets + pages
python serve.py                              # sert le site sur :8800, + /api/live
python serve.py --public-port 8801           # + une façade exposable (voir plus bas)
python fetch_players.py --club yarmouk       # fiches d'un club (hors daily.py)
python test_public.py                        # ce que la façade publique refuse
```

Auto-hébergement, côté Windows :

```powershell
powershell -ExecutionPolicy Bypass -File serve_247.ps1 -Register   # serveur + tunnel à l'ouverture de session
powershell -ExecutionPolicy Bypass -File schedule_daily.ps1        # daily.py à 8 h
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
- **Si la feuille porte les rôles** (`GK`, `RB`, `CAM`, `LW`…), les mettre dans
  `role` : le terrain place alors par rôle, côtés compris, et affiche le
  dispositif du club (« 4-2-3-1 »). Le basculement est **tout ou rien** — un
  seul titulaire sans rôle reconnu et la feuille entière retombe sur les postes
  Sofascore. Ajouter tout rôle nouveau à la table `ROLES` de `pitch.js`, jamais
  le deviner à la lecture de la chaîne. Et la note de méthode suit le dessin :
  trois versions dans `match.js`, sans quoi la page nie sa propre feuille.
- **Ne pas combler les numéros avec ceux de Sofascore** quand le club n'en
  publie pas : ils passeraient pour publiés. Les pastilles affichent « — »,
  c'est correct.
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

**Fait le 13/08/2026** — la revue de sécurité de `serve.py` et le tunnel de
test. Le détail est dans `PROGRESS.md` ; ici, ce qui ne se devine pas :

- `--public-port` ouvre un **second écouteur dans le même processus**. Un seul,
  parce que les deux façades partagent `Handler.lock` et l'unique
  `LiveCollector` : deux processus se disputeraient le port CDP 9333.
- **`/api/refresh` n'existe pas sur le port public.** Une collecte lance Chrome
  pour une minute — la règle « à la main, jamais périodique » ne survivrait pas
  à une boucle anonyme.
- Le collecteur lit ses rencontres dans `console.data.json`, **ou dans
  `data/site.json`** si l'outil interne n'a jamais tourné ici. Sans ce repli, un
  poste qui ne sert que le site public n'aurait aucun match à suivre.
- `serve_247.ps1` tient le serveur et le tunnel, et écrit l'adresse dans
  `tunnel.url` — **elle change à chaque relance**, c'est la limite d'un tunnel
  de test.
- **Vérifier l'état de la tâche, pas seulement que « ça répond ».**
  `FootballStatsScraper-Serve` doit être en **`Running`** : son script boucle
  sans fin, donc `Ready` signifie que le superviseur est mort — or `serve.py`
  et `cloudflared`, détachés, lui survivent et continuent de servir. Tout a
  l'air normal, mais plus rien ne relance quoi que ce soit (constaté le
  17/08). Le journal à lire est `superviseur.log`.
- **Chaque tunnel écrit dans son propre `tunnel-<horodatage>.log`.** Ne pas
  revenir à un journal unique qu'on vide avant de lancer : un `cloudflared`
  encore vivant le verrouille, et sous `ErrorActionPreference = "Stop"` cette
  ligne tue le superviseur.

**Répéter le direct sans match en cours** (fait le 14/08/2026, avant la J19) :
avancer le `kickoff_iso` d'une rencontre **déjà jouée** dans `data/site.json`, le
collecteur la croit en cours et son score connu sert de témoin. Sauvegarder le
fichier — il est versionné et public — et **comparer l'empreinte au retour**.
Laisser d'abord le collecteur s'éteindre (180 s sans demande) pour vider sa
mémoire des matchs clos. Mesuré : quatre rencontres simultanées coûtent **13 s**
dans un cycle de 60 s, le lancement de Chrome dominant. Un collecteur mort
repart au premier spectateur (`is_alive()`), le direct ne reste pas muet.

⚠️ **Deux postes publient** (le portable et le Dell), donc `daily.py` se
resynchronise sur `origin/main` **avant de collecter** — le seul moment où
l'arbre est propre. En retard : `merge --ff-only`. **En divergence : il
s'arrête et ne collecte rien**, à trancher à la main. Ne pas lui faire résoudre
ça tout seul : `-X ours` emporterait aussi du code poussé d'ailleurs. Et un
push refusé rend maintenant un code de sortie non nul — avant, la tâche
planifiée voyait un succès.

⚠️ **Lancer le projet avec `.venv/Scripts/python.exe`**, jamais le Python
global : il n'a aucune dépendance installée.

⚠️ **Rien ne démarre tant que personne n'est connecté.** Les deux tâches sont en
`LogonType Interactive`, à dessein : la collecte pilote un vrai Chrome, il lui
faut un bureau. Un tunnel nommé, sur un domaine Cloudflare, lèverait cette
contrainte et donnerait une URL stable.

⚠️ **Ne pas partir en chasse sur deux faux signaux.** Le préflight de
`cloudflared` annonce des « critical failures » sur `region2` alors que le
tunnel s'établit par `region1`. Et `Invoke-WebRequest` expire sur l'URL du
tunnel là où `curl.exe` répond en une seconde : vérifier avec `curl.exe` avant
de conclure à une panne.

## Points ouverts

1. Les **visuels de changements** — seul chemin vers les minutes jouées.
2. Le flux **SSE `/glvs/`**, débranché : il apporterait la minute de jeu, absente
   de `gmc=1`. À faire consommer par `serve.py`, pas par la page.
3. Quatre **diffuseurs** manquants dans `data/broadcasts.json`.
4. Les buteurs sans fiche joueur (`fetch_players.py --club` sur sulaibikhat,
   burgan, sporty).
5. **`shoot.py` n'est documenté nulle part** — trou de suivi connu.
6. **Le tunnel nommé** : il faut un domaine sur Cloudflare. C'est ce qui manque
   pour une URL stable et un démarrage indépendant de la session ouverte.
