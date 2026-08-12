# PROGRESS — football-stats-scraper (Forebet / Division 1 Koweït)

Session du 05/08/2026 — interrompue.
Session du 06/08/2026 — `parse_match.py` écrit et validé sur le cache.
Session du 10/08/2026 — statistiques de match branchées, `build_json.py`,
`requirements.txt` et `README.md` écrits. Le « reste à faire » est vide.

## Ce qui est acquis (ne pas re-tester)

### robots.txt : tout est autorisé
`https://www.forebet.com/robots.txt` → `User-agent: * / Disallow:` (vide).
Aucune restriction de chemin. Le blocage rencontré est purement technique.

### Forebet est derrière un challenge Cloudflare « managed »
Testé le 05/08/2026, **ne pas refaire ces essais** :
- `urllib` (stdlib) → 403
- `curl` avec User-Agent navigateur complet → 403, `Cf-Mitigated: challenge`
- Playwright + Chromium bundlé, non-headless, profil persistant → bloqué sur « Un instant… »
- Playwright + `channel="chrome"` (vrai Chrome piloté) → bloqué pareil

### La solution qui marche : Chrome normal + attache CDP
Lancer un **vrai Chrome** avec `--remote-debugging-port=9333` et un profil dédié,
puis s'y attacher avec `playwright.chromium.connect_over_cdp`. Le challenge passe
tout seul en quelques secondes. Validé : 10 lignes de match récupérées sur la page
ligue, 333 Ko de HTML sur la page match.
→ C'est ce qu'implémente `browser.py`. **Ne pas repartir sur `requests` ou sur un
`playwright.launch()` classique, ça ne passera pas.**

### Dépendances installées
`requests`, `beautifulsoup4`, `lxml`, `pandas`, `playwright` (+ `playwright install chromium`).
Note : la console Windows est en cp1252, `browser.py` reconfigure stdout/stderr en
UTF-8 à l'import, sinon le moindre accent dans un log fait planter le script.

## Fait

- `browser.py` — couche de récupération : lancement Chrome + CDP, cache disque
  (`cache/`, nom lisible + hash), throttling aléatoire 2-5 s, attente de sélecteur.
- `cache/` amorcé avec la page ligue et la page du match test.
- `parse_match.py` (06/08/2026) — parseur complet, validé sur le HTML en cache.
  Sections produites : en-tête (id, slug, url, tag compétition, équipes, coup
  d'envoi), `predictions` (les 10 marchés), `result_blocks` (5 blocs),
  `standings`, `stats` (buts, tirs, attaques, `others` indexé par libellé).
  CLI : `python parse_match.py --file cache/xxx.html --out out.json`, ou par URL
  (passe par le cache de `browser.py`, `--force` pour ignorer).
  `--summary` affiche un résumé lisible en console — c'est le moyen de contrôler
  une extraction à l'œil sans ouvrir le JSON.
  ⚠️ Ne pas piper la sortie JSON dans `Select-Object -First N` sous PowerShell :
  la fermeture du tube fait sortir Python en 255 (ce n'est pas une erreur de
  parsing). Utiliser `--out` ou `--summary`.

## Match de test

`https://www.forebet.com/fr/football/matches/al-shamiya-al-jazira-2487393`
Al Shamiya - Al Jazira, 06/08/2026 19:45, tour 17.
Pronostic réel relevé : **7 / 26 / 67**, score prédit **1-3**, moy. buts 3.20,
confiance 43°. (Les chiffres du plan d'origine — 21/12/67 — étaient illustratifs.)

## Sélecteurs déjà identifiés (le gros du travail de reverse engineering)

### Page ligue (`/fr/predictions-kuwait/1st-division`)
Une ligne de match = `div.rcnt` :
- lien match : `a[href]` → `/fr/football/matches/{slug}-{id}`
- `.homeTeam` / `.awayTeam` → noms
- `.date_bah` → `JJ/MM/AAAA HH:MM`
- `.fprc > span` ×3 → probabilités 1 / X / 2
- `.predict .forepr` → pronostic (1/X/2) ; `.predict .ex_sc` → score prédit
- `.avg_sc` → moyenne de buts ; `.prwth` → indice de confiance (« 43° »)

### Page match
- **Blocs de résultats** : `div.st_scrblock`, 5 dans l'ordre :
  0 = Face à Face, 1 = 6 derniers matchs équipe dom., 2 = 6 derniers matchs équipe ext.,
  3 = matchs à domicile, 4 = matchs à l'extérieur.
  Titre récupérable via le `.mptlt` précédent.
  Une ligne = `div.st_row` : `.st_date`, `.st_hteam` (+ classe `active-team` sur
  l'équipe sujet du bloc), `.st_rescnt .st_res` (score) + `.st_htscr` (mi-temps),
  `.st_ateam`, `.st_ltag` (compétition, ex. `KW2`).
  → Les % V/N/D affichés (`.st_dstc`) sont rendus en JS et **vides dans le HTML** :
  les recalculer à partir des lignes, c'est de toute façon plus sûr.
- **Classement** : `table#standings` (la **première** des deux, 10 `tr`).
  Colonnes : rang, équipe, PTS, J, V, N, D, BP, BC, +/-.
  ⚠️ Rappel du projet `kuwait-football` : le championnat koweïtien départage à la
  confrontation directe, pas à la différence de buts.
- **Buts** : `.os_goals_section1_child` ×8 → [0-3] équipe dom. (marqués, moy.,
  encaissés, moy.), [4-7] équipe ext.
- **Tirs** : `.os_shots_stats_section` ×4 → [0,1] dom. (total de tirs, tirs bloqués),
  [2,3] ext. Chaque bloc donne total + moyenne par match.
- **Attaques** : `.os_attacks_stats` ×8 → [0,1] att. totales dom., [2,3] att. totales
  ext., [4,5] att. dangereuses dom., [6,7] att. dangereuses ext. (total puis moyenne).
- **Autres / Disciplinaire** : `table.os_others_table`, une ligne = `tr` au format
  `moy_dom | total_dom | libellé | total_ext | moy_ext`. Le libellé est dans
  `.os_others_stats_h`, sauf cartons rouges/jaunes dont la cellule est
  `td.os_card.__red` / `__yellow`. **Parser par libellé, pas par index** — les
  index sautent entre les deux sous-tableaux.

## Point ouvert du 05/08 — RÉSOLU le 06/08, ne pas y revenir

Les onglets de pronostics (« Moins/Plus 2.5 », « Les deux équipes marquent »…) ne
s'ouvraient pas au clic. **Il n'y a rien à cliquer** : les dix marchés sont déjà
tous présents dans le HTML servi, dans des conteneurs masqués. Inutile d'aller
chercher les pages ligue dédiées.

| conteneur | marché | ce qu'on obtient |
|---|---|---|
| `#m1x2_table` | 1X2 | 7 / 26 / 67, prono `2` |
| `#uo_table` | Plus/Moins 2.5 | 36 / 64, prono `Plus`, total 3.20 |
| `#ht_table` | Mi-temps 1X2 | 32 / 30 / 38 |
| `#htft_table` | Mi-temps / fin | 25 %, prono `2` |
| `#bts_table` | Les deux marquent | 33 / 67, prono `Oui` |
| `#dbc_table` | Double chance | 93 %, prono `2X` |
| `#ah_table` | Handicap asiatique | 60 %, `Invité -1.5` |
| `#gscr_table` | Score exact | 1 - 3 |
| `#corner_table` | Corners | 58 / 42, `Moins`, 8.88 |
| `#card_table` | Cartons | 48 / 52, `Plus`, 4.64 |

Chaque conteneur porte un `.rcnt` de structure identique à celle de la page
ligue : `.fprc > span` (probabilités), `.predict .forepr` (pronostic),
`div.ex_sc.tabonly`, `div.avg_sc.tabonly`, `.prwth .wnums`.
⚠️ `.ex_sc` existe en double (version mobile dans `.predict`) — toujours
sélectionner la variante `.tabonly`.

## Acquis de parsing (06/08/2026)

- **Les blocs « Les 6 derniers matchs » contiennent toute la saison** (16 et 17
  lignes ici), c'est le JS qui tronque à 6 à l'affichage. Les lignes sont triées
  du plus récent au plus ancien. `parse_match.py` produit donc `record` (tout),
  `record_recent` (6 premières) et `form` (« VVNNVD »).
- **Les blocs mélangent les compétitions.** Al Jazira sortait à 17 matchs contre
  16 au classement : l'écart est un match de Coupe (`.st_ltag` = `KwC` au lieu de
  `KW2`). Filtrer sur `competition` si on veut du championnat pur.
- **Recoupement réussi** : le bilan recalculé d'Al Shamiya (3V 1N 12D, 15:46 en 16
  matchs) tombe exactement sur sa ligne de classement. Le calcul V/N/D depuis les
  lignes est donc fiable.
- Le classement de cette D1 compte **8 équipes**, pas 10. Les deux premières `tr`
  de `table#standings` sont un titre vide puis l'en-tête : les sauter en testant
  que la 1re cellule est bien un nombre.

## Console HTML (06/08/2026)

`console_template.html` + `build_console.py` -> `console.html`, autonome et
hors-ligne (les données sont injectées à la place du jeton
`/*__CONSOLE_DATA__*/`, aucun `fetch()` à l'ouverture). Même principe que
`build_dashboard.py` du projet `kuwait-football`.

    python build_console.py                      # tout ce qui est en cache
    python build_console.py --file cache/x.html  # un fichier
    python build_console.py <url> [<url> ...]    # par URL, Chrome si absent du cache

### Orientation : statistiques, pas pronostics

Décision de Haris le 06/08/2026, **à ne pas re-débattre** : la console compare
les relevés des deux équipes et n'annonce aucun vainqueur. Une première version
était construite autour des dix marchés (score prédit en hero, barres de
probabilité) — elle a été refaite. `build_console.py` retire donc `predictions`
de la charge utile ; `parse_match.py` continue de les extraire et ils restent
disponibles dans son JSON, mais la page ne les affiche pas.

Sections, dans l'ordre : bandeau, contenu Instagram, carte d'identité (tuiles par
équipe), comparatif tête à tête, parcours (graphique buts marqués/encaissés par
match), contexte (domicile / extérieur / face à face). Pas de hero : aucun chiffre
ne mérite d'écraser les autres quand le but est la comparaison.

**Le classement est dans une colonne collante à droite** (296 px, `position:
sticky`), pas dans le flux : c'est la référence qu'on veut garder sous les yeux
en parcourant les stats. Version compacte (rang, écusson, équipe, J, Pts, +/-),
les deux équipes du match surlignées, et le détail V/N/D + buts pour/contre
replié dans un `<details>` puisque la colonne est étroite. La carte a un
`max-height: calc(100vh - 32px)` avec défilement propre : sinon un classement
plus long que l'écran rendrait le bas inaccessible. Sous 940 px de large, la
colonne repasse sous le contenu principal.

**Deux rôles de couleur seulement, à ne pas mélanger** (palette passée au
validateur du skill dataviz, PASS dans les deux modes) :
- **Entités** — domicile `#2a78d6` / extérieur `#eb6834` (clair), `#3987e5` /
  `#d95926` (sombre). Séparation CVD ΔE 24.7 clair, 26.8 sombre. Le domicile est
  bleu *partout* : pastilles, tête à tête, parcours, surlignage du classement.
- **Gris `#898781`** — jamais une équipe. Porte les buts encaissés, que la
  position sous la ligne de base distingue déjà.

Piège de couleur rencontré sur la version pronostics, **à garder en tête si des
marchés reviennent un jour** : « 2X » et « Invité -1.5 » *désignent* une équipe.
Les remplir en bleu les faisait lire comme l'équipe à domicile, bleue partout
ailleurs. Il avait fallu passer ces jauges en gris neutre.

Autres décisions de rendu :
- **Périmètres différents dans la même carte** : le classement ne compte que le
  championnat, les relevés de Forebet agrègent toutes les compétitions. Al Jazira
  affiche « 9V sur 16 » (championnat) à côté de « 20 buts contre » (17 matchs,
  coupe comprise). La carte d'identité détecte l'écart et l'écrit noir sur blanc,
  sinon ça passe pour une contradiction.
- Le bilan d'un bloc est celui d'**une** équipe (`active-team` chez la source).
  Le nom est écrit devant (« vu par Al Jazira : 2 matchs · 2V 0N 0D ») — sans ça
  le face à face se lit spontanément comme le bilan de l'équipe qui reçoit, soit
  l'inverse de la vérité ici.
- **Échelle commune aux deux graphiques de parcours** : mis à l'échelle
  séparément, ils se compareraient à tort.
- Les colonnes de parcours sont plafonnées à 24 px, donc le bloc prend la largeur
  de ses données ; la ligne de base et l'axe s'alignent dessus au lieu de
  traverser une zone vide qui se lirait comme des matchs manquants.
- Les rubriques vides des deux côtés (six mètres, touches, penaltys, arrêts,
  tacles) sont sorties du comparatif et listées en note — une barre à zéro se
  lirait comme une mesure réelle.
- Chaque ligne du tête à tête est mise à l'échelle indépendamment ; les valeurs
  sont écrites de part et d'autre, donc rien n'est accessible par la seule
  couleur ni par le seul survol.
- Forme : lettre V/N/D **et** couleur, jamais la couleur seule.

## Rencontres et filtres (06/08/2026)

`fetch_fixtures.py` lit la page ligue et en tire les rencontres (identité, coup
d'envoi, score si joué, URL de la fiche).

    python fetch_fixtures.py            # depuis le cache
    python fetch_fixtures.py --force    # rafraîchit la page ligue

Sélecteurs : une ligne = `div.rcnt` **dans `#body-main`** — la page glisse deux ou
trois rencontres d'autres championnats dans `#body-cont`, à écarter. `.l_scr`
vide = match à venir, rempli = résultat.

`build_console.py --fixtures` enchaîne les deux : liste les rencontres, récupère
la fiche de chacune, construit la console.

    python build_console.py --fixtures                # les matchs à venir
    python build_console.py --fixtures --scope all    # + les résultats récents

La console a une barre de filtres (équipe, période : à venir / aujourd'hui /
joués / toutes) et une liste de rencontres groupée par date ; on clique une
rencontre pour afficher les stats des deux équipes. Une rencontre listée sans
fiche récupérée reste visible, marquée « fiche non récupérée » — on la montre
sans prétendre pouvoir l'ouvrir.

**Deux pièges rencontrés, tous les deux corrigés :**

- **La page ligue vieillit en cache et ment sur les dates.** Le 06/08 elle
  annonçait les 4 matchs le 06/08 ; deux fiches récupérées le jour même
  disaient 07/08. Après `fetch_fixtures.py --force`, la page ligue fraîche
  confirmait bien 2 matchs le 06 et 2 le 07. `reconcile()` dans
  `build_console.py` fait donc **primer la date de la fiche** sur celle de la
  page ligue, et garde l'ancienne dans `kickoff_ligue`.
- **Le slug d'URL n'est pas `[a-z0-9-]`.** Forebet laisse passer parenthèses et
  accents : `sporty-sahel-(kuw)-2487392`, `ferencváros-w-paok-w-2487422`. La
  regex trop stricte de `parse_match.py` faisait sortir `match_id` à `None` sur
  ces matchs, et la console les affichait « fiche non récupérée » alors qu'elles
  étaient bien là. `MATCH_ID_RE` utilise maintenant `.+?`.

Vérifié : les 8 fiches rendent sans `undefined`/`NaN`, les deux équipes sont
surlignées au classement dans chaque cas, aucune erreur console.

## Générateur de prompt Instagram (06/08/2026)

**But réel du projet, énoncé par Haris ce jour-là** : produire du contenu Instagram
à partir des stats. Un carrousel v1 existe déjà, fait à la main :
`Downloads\Match Carousel v2-selection*.png` (4 slides, Al Shamiya - Al Jazira).

La console a donc une carte « Contenu Instagram » avec un bouton qui compose un
brief prêt à coller dans Claude, rempli des chiffres de la fiche affichée
(~5 000 caractères), plus un bouton Copier.

Structure du carrousel reprise des PNG de référence, format 1080 x 1350 (export
2x = 2160 x 2700) :
- 01 couverture, fond coupé en diagonale bleu/sable, noms, journée, pts et rangs
- 02 les visiteurs, fond sable, pts + rang + pastilles V/N/D + marqués/encaissés/diff
- 03 les hôtes, fond bleu, même composition, orange `#f2703f` sur les records subis
- 04 « les chiffres qui comptent », fond nuit, lignes chiffre + étiquette

Points à connaître :
- **La journée est déduite** : `max(matchs joués) + 1`, et uniquement si toutes
  les équipes ont joué le même nombre de matchs. Sinon le champ est omis plutôt
  que faux. Sur le match de test ça retrouve bien « journée 17 ».
- **Les superlatifs sont calculés depuis le classement**, pas saisis à la main :
  `rankMap()` classe sur `goals_for` / `goals_against` et produit « meilleure
  attaque de la division », « pire défense de la division », « 3e attaque »…
  À noter : le carrousel fait à la main annonçait Al Jazira « 2ND BEST » à
  l'attaque, alors qu'avec 32 buts contre 35 et 33 elle est **3e**. Le
  générateur corrige ce genre d'erreur.
- Le brief **interdit explicitement** d'inventer un chiffre et de produire un
  pronostic — cohérent avec l'orientation stats du projet. Les lignes de la
  slide 04 sont calculées (écart de points, bilan domicile/extérieur, tirs par
  match, buts encaissés par match, % de victoires sur 6, face à face).
- Le bouton Copier passe par `navigator.clipboard`, avec `execCommand("copy")` en
  secours : l'API n'est pas toujours disponible en `file://`.

## Écussons et couleurs des clubs (06/08/2026)

`crests.py` -> `data/teams.json` : un écusson en `data:` URI + les couleurs
dominantes par club. La console reste donc un fichier unique, hors ligne.

    python crests.py            # complète les clubs manquants
    python crests.py --force    # tout refaire

**Sources écartées, ne pas y revenir :**
- **TheSportsDB ne connaît pas ces clubs.** `searchteams.php?t=Al Jazira` répond
  en **60 secondes** et renvoie l'Al Jazira des Émirats. Pire,
  `lookup_all_teams.php?id=5213` (« Kuwait Division 1 ») renvoie des clubs
  **anglais** de League One — la table est mal mappée chez eux.
- **Téléchargement direct des images Forebet : 403.** Cloudflare protège aussi
  `/images/icons/*.png`, et un `fetch()` exécuté *dans* la page se prend le même
  403 (testé, 3 tentatives).

**La méthode qui marche : canvas.** Le navigateur, lui, affiche bien ces images
en rendant la page. `ForebetBrowser.grab_images()` visite la page match et
redessine chaque `<img>` déjà chargée dans un canvas, puis `toDataURL()`. Aucune
requête supplémentaire, donc rien à bloquer ; même origine, donc pas de canvas
« taint ». Une page match porte les écussons de ses deux clubs : les 8 pages en
cache couvrent toute la division.

Repères de parsing : les logos sont dans `a.team-logo img`, avec le nom du club
dans `alt` (« Al Shamiya - Logo »). ⚠️ `/images/fc/*.png` sont des **drapeaux de
pays**, pas des écussons.

**Couleurs extraites de l'écusson**, pas saisies : `dominant_colours()` regroupe
les pixels et classe sur `fréquence x chroma`. Sans la pondération par le chroma,
le blanc du fond et le noir des contours sortent toujours en tête et on perd la
couleur du club. Résultat :

| club | couleurs |
|---|---|
| Al Shamiya | `#0c3760` `#f4f6f9` |
| Al Jazira | `#e8e2d1` `#585246` |
| Burgan SC | `#252a5a` `#f0dfc1` |
| Khaitan SC | `#f01a24` `#fdfcfc` |
| Sahel (KUW) | `#232276` `#fcca0a` |
| Sporty | `#683eb4` |
| Sulaibikhat | `#de1f26` `#fcfbfa` |
| Yarmouk (KUW) | `#fdfdfe` `#8e8fc3` |

À noter : le carrousel fait à la main utilisait déjà marine + crème, c'est-à-dire
exactement les couleurs réelles d'Al Shamiya et d'Al Jazira.

**Deux affiches ont la même teinte des deux côtés** : Khaitan `#f01a24` contre
Sulaibikhat `#de1f26` (deux rouges), Sahel `#232276` contre Burgan `#252a5a`
(deux marines). `pair_note()` **n'utilise pas la couleur secondaire** dans ce cas
— celle de Sulaibikhat est un blanc cassé, et écrire « Sulaibikhat = blanc »
serait faux. Il décale la **clarté** de la couleur extérieure par pas successifs
jusqu'à franchir ΔE 15 en OKLab, la teinte du club étant conservée :
Sulaibikhat -> `#a40000`, Burgan -> `#4d568a`. Les 8 affiches franchissent le
seuil. Le prompt annonce la vraie couleur et explique la substitution.

`ink_on()` indique la couleur de texte à poser sur chaque fond : indispensable,
Yarmouk est quasi blanc (`#fdfdfe`) et Al Shamiya très sombre.

**Où les couleurs des clubs servent — et où non.** Elles pilotent le prompt
Instagram, les écussons et une pastille à côté du nom. Les **graphiques de la
console gardent la paire validée bleu/orange** : deux clubs peuvent partager une
teinte, et une couleur de club peut être blanche ou quasi noire — inutilisable
comme marque de données. L'identité passe par l'écusson, la lisibilité par la
palette validée.

Détail d'affichage : beaucoup d'écussons sont sur fond transparent avec des
traits sombres. En thème sombre ils disparaîtraient : la classe `.crest` leur
pose un fond blanc à 92 % arrondi, uniquement dans ce thème.

## Direct et statistiques par match (sondé le 06/08/2026)

### Il EXISTE des statistiques par match pour le Koweït — conclusion à corriger

Le projet `kuwait-football` avait conclu « aucune statistique de match n'existe
pour le Koweït ». C'était vrai **de TheSportsDB et d'API-Football**, pas de
Forebet. Forebet a son propre fournisseur (champs de forme Sportmonks) et il
couvre la Division 1 koweïtienne.

    https://www.forebet.com/scripts/get_evs_n.php?gdt=1&mid=<match_id>&gmc=1

Vérifié sur Khaitan 0-1 Sulaibikhat (`2486627`) et Al Jazira 3-0 Sporty
(`2486626`). Clés renvoyées : `match`, `formations`, `scores`, `events`, `stats`,
`lineup`, `bench`, `sidelined`.

Ce qui est réellement rempli pour le Koweït :
- **possession** (`possessiontime` : 59 / 41)
- **tirs** (`shots` : `total`, `ongoal`, `offgoal` — 8 dont 1 cadré)
- **corners**, **cartons** jaunes/rouges, **remplacements**
- `attacks` / `dangerous_attacks`, `ball_safe`, `goal_attempts`
- **chronologie** (`events` : buts avec la minute — 5 événements sur Al Jazira)
- **stade et capacité** (« Thamir Stadium », 15 000), **couleurs officielles**
  (`host_color` `#EA1515` pour Khaitan)

Restent vides sur cette division : `passes`, `fouls`, `tackles`, `saves`,
`offsides`, `lineup`, `bench`, `formations`, `referee`, noms des buteurs.
⚠️ Qualité inégale : sur Al Jazira - Sporty, `dangerous_attacks` (94) dépasse
`attacks` (79). À recouper avant de publier un chiffre.

Sans `gmc=1`, le même endpoint ne renvoie que la chronologie (et une liste vide
si le match n'est pas couvert).

### Le direct passe par du Server-Sent Events

`all.js` ouvre `new EventSource("https://www.forebet.com/glvs/…")`. Le flux pousse
un JSON par match, indexé par `match_id`, avec `host_sc`, `guest_sc`, `minute`,
`ad_tm` (temps additionnel), `running`, plus les cotes en direct (`odds`,
`odds_1`, `odds_X`, `odds_2`). Donc : **score et minute en temps réel, poussés,
sans polling**. Aucune statistique dans ce flux.

Autres points d'entrée repérés dans `all.js` : `/gsv/` (cotes),
`/scripts/getftr.php?int=N&ln=` (listes de matchs). Deux URL `http://localhost/`
traînent dans le code : ce sont des restes de dev, pas des endpoints publics.

### TRANCHÉ le 10/08/2026 : oui, les stats se remplissent pendant le match

La question est réglée, ne pas la rouvrir. Relevés pris sur Khaitan SC -
Al Jazira (`2487397`) pendant la rencontre :

| | 19:42 | 19:46 | 20:07 |
|---|---|---|---|
| possession | 65 / 35 | 64 / 36 | 58 / 42 |
| tirs | 1 / 0 | 1 / 0 | 3 / 4 |
| attaques | 17 / 13 | 22 / 16 | — |
| remplacements | — | 0 / 1 | 0 / 1 |

Trois enseignements, tous constatés et non déduits :

- **Les chiffres bougent d'un relevé à l'autre**, à la granularité de quelques
  minutes. `--force` est indispensable : servi depuis le cache, un relevé en
  direct n'a aucun intérêt.
- ⚠️ **Les rubriques apparaissent au fil du match** — « remplacements » n'existe
  pas au coup d'envoi. Tout code qui consomme ces stats doit tolérer des clés
  absentes, jamais supposer un jeu de champs fixe.
- ⚠️ **Ni minute, ni statut, ni faits de jeu en direct.** L'en-tête ne porte que
  `date`, `host`/`guest` (+ id, couleur, entraîneur), `venue`,
  `venue_capacity`, `referee` et les scores — **pas de `minute` ni de
  `status`** — et `events` reste **vide** tant que le match n'est pas fini. On
  ne peut donc pas afficher d'horloge de match : c'est l'heure du *relevé* qu'on
  date. Pour la minute, il faudrait le flux SSE `/glvs/` décrit plus haut.

### ⚠️ Le score des premières minutes peut changer de camp

Sur Sahel - Al Shamiya (`2487395`), le **but unique** a été attribué à
Al Shamiya à 19:41 (`ht_score` « 0-1 », `goals` 0/1) puis à Sahel à 19:52
(`ht_score` « 1-0 », `goals` 1/0). Contrôlé dans la foulée : `host_id` (6084,
Sahel) et `guest_id` (28045) sont **présents et corrects**, et les lignes de
`stats` arrivent dans l'ordre `[hôte, invité]`. **Ce n'est donc pas le repli
positionnel de `normalise()`** — c'est la source qui s'est reprise. Le cache
ayant été écrasé par le `--force`, l'appel de 19:41 n'est plus rejugeable.

À rapprocher du désaccord Forebet / Sofascore sur qui reçoit : les deux
symptômes portent sur la même chose, l'attribution des camps.

Conséquence retenue plutôt qu'un correctif : le serveur **compare chaque relevé
au précédent et marque `unstable` toute rencontre dont le compte de buts
recule** — un but ne se démarque pas. La console affiche alors le score avec
une réserve explicite au lieu de le présenter comme acquis.

Noter au passage que **`ht_score` porte le score courant pendant la première
période**, pas le score à la mi-temps : c'est la seule source de score du flux
`gmc=1`, il ne faut pas la lire comme un « mi-temps » définitif.

## Statistiques de match : branchées le 10/08/2026

`fetch_stats.py` interroge `get_evs_n.php?...&gmc=1`, normalise la réponse et
la range dans `match["match_stats"]`. `build_console.py` l'accroche à chaque
fiche (option `--no-stats` pour s'en passer), la console l'affiche dans une carte
**« Statistiques du match »** placée avant la carte d'identité, et le brief
Instagram reçoit un bloc séparé.

    python fetch_stats.py 2486626 2486627 --summary

Quatre décisions de fond, toutes dictées par la qualité de la source :

- **La carte est à part, et en premier.** Tout le reste de la console agrège une
  saison. Mélangé au comparatif, « 33 tirs » se lirait comme un total de saison.
- **Un zéro n'est pas un zéro.** `passes`, `fouls`, `tackles`, `saves`,
  `offsides`, `ball_safe`, `goal_attempts` arrivent à 0 parce que le fournisseur
  ne les couvre pas. `prune()` retire tout champ nul **des deux côtés**, et la
  console nomme ce qu'elle tait au lieu de tracer une barre à zéro.
- **Les attaques ne sont pas publiées quand elles sont incohérentes** :
  `dangerous_attacks` (94) > `attacks` (79) sur Al Jazira - Sporty. Le couple
  est conservé avec un drapeau `suspect`, et l'affichage l'écarte en le disant.
- **L'appariement passe par `team_id`**, jamais par l'ordre du tableau `stats`,
  qui n'est pas garanti (`match.host_id` / `guest_id` donnent le camp).

### Ce que la réponse contient réellement (revérifié le 10/08)

Renseignés : `possessiontime`, `shots` (`total` / `ongoal` / `offgoal`),
`corners`, `yellowcards`, `redcards`, `substitutions`, `goals`, `venue` (+
capacité), `ht_score` / `ft_score`. Systématiquement vides : passes, fautes,
tacles, arrêts, hors-jeu, `lineup`, `bench`, `formations`, `referee`.

⚠️ **`events` est intermittent.** Il portait 5 et 7 faits de jeu sur les matchs
du 02/08, et il est **vide sur les quatre matchs des 06 et 07/08**, y compris un
0-5. Ce n'est donc pas une question de couverture de la division : la
chronologie va et vient. La console n'affiche le bloc que s'il est là, et le
brief Instagram ne mentionne les buts que dans ce cas.

ℹ️ **`host_color` / `guest_color` se remplissent maintenant** (`#0046A8`,
`#C40010`, `#FFDF1B`… sur les matchs des 06-07/08), alors qu'ils étaient vides
sur ceux du 02/08. C'est une deuxième source de couleurs de club, gardée dans
`match_stats.colors`. **Elle ne pilote rien** : la palette reste celle extraite
des écussons par `crests.py` — décision inchangée.

### Le piège Cloudflare sur les endpoints JSON

Un `fetch()` sur `get_evs_n.php` renvoie **403** tant que la page hôte est
encore bloquée sur « Un instant… » : la requête part sans le cookie de
clearance. Ce n'est pas un endpoint interdit. `CdpBrowser._land_on_forebet()`
attend donc la résolution du challenge, **puis** `wait_for_load_state("load")` —
sans quoi le rechargement final du challenge détruit le contexte JS en pleine
évaluation (« Execution context was destroyed »). `get_json()` retente trois
fois par-dessus.

**Un corps vide n'est pas une panne** : c'est ainsi que Forebet répond pour une
rencontre à venir ou non couverte. Il est mis en cache tel quel et remonte en
`None`, sans erreur de parsing.

## Export JSON (10/08/2026)

`build_json.py` écrit `output/index.json`, `output/teams.json` et
`output/matches/<match_id>.json`. Le schéma n'est pas celui du plan d'origine —
ce document **n'existe plus sur le disque** ; il a été redéfini ici, versionné
par le champ `schema`.

    python build_json.py --fixtures --scope all

La collecte est **partagée avec la console** : `build_console.assemble()` et
`add_source_arguments()` servent les deux, pour que les drapeaux ne divergent
pas. Deux écarts assumés par rapport à la charge utile de la console :

- les **écussons ne sont pas embarqués** par match (400 Ko chacun) mais une
  seule fois dans `teams.json`, référencés par le nom du club ;
- chaque camp est **recroisé à l'avance** (`standing`, `season`, `form`,
  `record_at_venue` au même endroit) : la console fait ce recoupement à
  l'affichage, un consommateur externe n'a pas à le refaire.

Une rencontre venue du seul calendrier Flashscore n'a pas de fiche : son entrée
d'index porte `document: null` plutôt qu'un chemin vers un fichier absent.
`matches/` est vidé à chaque build (`--keep-stale` pour ne pas le faire), sinon
une fiche d'un ancien build survivrait sans être indexée.

## Chaîne de diffusion : pas de source automatique (sondé le 06/08/2026)

Question posée par Haris : afficher sur quelle chaîne chaque match est diffusé.
**Aucune source automatique trouvée pour cette division.** Ne pas re-tester ces
deux-là :

- **Forebet n'a rien.** Zéro occurrence de `broadcast`, `channel`, `tv station`,
  `stream`, `diffusion` ou `chaîne` — ni dans le HTML de la fiche match, ni dans
  `all.js` (120 Ko). Les 27 « tv » du HTML sont des faux positifs
  (`btvi`, `DefaultValue`, `mm-listview`).
- **Live Soccer TV ne couvre que l'élite.** ⚠️ Piège de nommage : leur URL
  `/competitions/kuwait/division-1/` est en réalité la **Kuwait Premier League**
  (Al Arabi, Qadsia, Kazma, Al Salmiyah…), c'est-à-dire la 1re division. Une
  recherche sur Sulaibikhat ou sur notre Al Jazira ne renvoie rien : les clubs de
  la 2e division sont absents du site. La chaîne citée sur les matchs d'élite est
  « 51 Kuwait » (KTV Sport), et pas sur tous.

Piste non testée : **Sportmonks** a un endpoint `tvstations`, et les champs de
`get_evs_n.php` ressemblent à du Sportmonks — donc Forebet passe peut-être par
eux sans exposer ce bloc. Couverture TV d'une 2e division koweïtienne très
douteuse, et c'est payant (essai 14 jours). À sonder seulement si le besoin
devient réel.

Solution retenue : **`data/broadcasts.json` saisi à la main** (même principe que
`manual_results.json` du projet `kuwait-football`), lu par `build_console.py`.
`channels` liste les chaînes habituelles données par Haris — Kuwait TV 2,
Kuwait TV Sport, Kuwait TV Sport 2 — et `matches` associe un identifiant de match
à une chaîne. Tant qu'une case est vide, la console affiche « diffusion non
renseignée — habituellement … » et **le prompt Instagram n'imprime rien** : on ne
publie pas une chaîne incertaine sur un post. Dès qu'elle est remplie, elle
apparaît dans le bandeau, en pastille dans la liste et sur la slide 1.

### Grilles des chaînes koweïtiennes : rien d'exploitable (sondé le 06/08/2026)

Recherche d'un EPG pour savoir quel match passe sur quelle chaîne. **Aucune
source ne convient**, et ce n'est pas un problème d'autorisation — kooora et
51.com.kw autorisent tout dans leur `robots.txt`, la donnée n'existe simplement
pas :

- **Live Soccer TV, page KTV Sport** : il y a bien une grille, mais elle ne
  contient que des amicaux européens (Bayern - Aston Villa, Newcastle - Everton,
  Dortmund - Roma…). Zéro football koweïtien.
- **kooora.com** : liste les matchs du jour de la 2e division islandaise et de
  la 3e norvégienne, mais **aucune compétition koweïtienne**.
- **51.com.kw** (plateforme officielle de l'État) : catalogue de replay, pas de
  grille horaire — aucun horaire sur la page.
- **icanlive.tv** : annuaire de flux, aucun programme.

Là où l'information vit réellement : le compte X de la chaîne
(`@kuwaitsporttv`), qui publie la grille du jour — en image, donc non
exploitable automatiquement. La saisie manuelle reste la seule voie.

## Effectifs : sources évaluées le 06/08/2026

Objectif : combler le trou laissé par Forebet, dont `lineup`, `bench` et les noms
de buteurs sont vides sur cette division.

| source | verdict |
|---|---|
| **soccer365.net** | **A les données**, mais `robots.txt` interdit ClaudeBot |
| Transfermarkt | injoignable — 504 sur `.com`, `.us` et `.de` ⚠️ **révisé le 10/08, voir plus bas** |
| playmakerstats.com | connaît clubs et « 2ª Divisão Kuwait », mais **0 joueur** |
| Wikipedia | pas de section effectif à jour sur ces clubs |
| Forebet | `lineup`/`bench` vides sur les matchs terminés testés |
| **Flashscore** | autorisé, mais **« FINAL RESULT ONLY »** sur cette division |
| **Sofascore** | ⚠️ **la meilleure source — 22 à 33 joueurs par club, voir plus bas** |

**soccer365 est la seule source complète trouvée** : effectif groupé par poste,
âges, entraîneur, et les 8 clubs présents. Identifiants relevés — Khaitan 9142,
Al Sahel 11276, Al Sulaibikhat 11280, Yarmouk 11282, Burgan 11284, Al-Jazira
31343, Al-Shamiya 32916, Sporty 32917.

⚠️ **Mais son `robots.txt` liste `User-agent: ClaudeBot -> Disallow: /`**, avec
`Content-Signal: ai-train=no`. Le site refuse nommément la collecte automatisée
par Claude. **Ne pas lui écrire de scraper.** Si Haris relève les effectifs
lui-même, les déposer dans `data/squads.json` : c'est sa collecte, pas la nôtre.

Piste encore ouverte : les compositions Forebet paraissent en général ~1 h avant
le coup d'envoi. À retester sur un match koweïtien à l'approche de 19 h 45 —
le sondage du 06/08 s'est arrêté sur un **403** (trop de requêtes dans la
journée), il faut laisser retomber avant de réessayer.

### Transfermarkt : joignable, autorisé, mais partiel (re-sondé le 10/08/2026)

**Le 504 du 06/08 était passager.** `www.transfermarkt.com` et `.fr` répondent
200 en 0,45 s. (`.de` renvoie 403, ne pas s'en servir.) La conclusion
« injoignable » ne tenait plus : elle est corrigée dans le tableau ci-dessus.

**`robots.txt` autorise tout le monde** : `User-agent: * / Allow: /`. Le seul
interdit est `wget`, et il n'y a **aucune règle visant ClaudeBot** — c'est la
différence de fond avec soccer365, qui nous nomme et nous refuse.

**Les 8 clubs y sont**, avec des effectifs réels (nom, poste, âge, fin de
contrat, valeur marchande) — mais **très incomplets** :

| club | id Transfermarkt | joueurs listés |
|---|---|---|
| Al-Yarmouk SC (Kuwait) | 29285 | 13 |
| Khaitan SC | 38189 | 13 |
| Al-Sahel SC | 32611 | 13 |
| Burgan SC | 56225 | 9 |
| Al-Jazeera FC | 129700 | 8 |
| Al-Sulaibikhat SC | 50944 | 6 |
| Al-Shamiya FC | 135029 | 2 |
| Al-Shamiya SC | 135039 | 0 |
| Sporty FC (Kuwait) | 144497 | 0 |

Soit **~64 joueurs pour 8 clubs**, là où un effectif réel en compte 25 environ.
Ce qui est listé penche nettement vers les étrangers et les joueurs valorisés.
**Transfermarkt ne remplace donc pas soccer365** ; il pré-remplit une partie de
`data/squads.json`, à compléter à la main.

⚠️ **Al-Shamiya existe en double** (`FC` 135029 et `SC` 135039). Lequel est notre
club n'est pas tranché — à vérifier avant d'en dépendre.

Trois pièges relevés :

- ⚠️ **Ne pas passer `saison_id`.** `/kader/verein/29285/saison_id/2025` renvoie
  une page valide **sans aucun joueur** — pas une erreur, une table vide. Sans le
  paramètre, la même URL en donne 13. Le titre indique « Detailed squad 26/27 » :
  la page par défaut est la saison en cours côté Transfermarkt, et l'effectif
  25/26 n'est pas conservé. Les joueurs listés ne sont donc pas nécessairement
  ceux qui disputent les rencontres qu'on affiche — à garder en tête avant de
  publier un nom.
- ⚠️ **Ne pas compter les `<tr>` naïvement.** Chaque ligne de joueur contient une
  `table.inline-table` (photo, nom, poste) avec ses propres `<tr>` : une regex
  sur `<tr class="odd|even">` ramène 1 joueur au lieu de 13. Passer par
  `tbody.find_all("tr", recursive=False)`.
- **Le site limite le débit.** Une poignée de `curl` rapprochés finit en
  `ERR_TIMED_OUT`. Le throttling de `browser.py` (2-5 s) passe sans problème.

### Sofascore : accessible depuis un vrai navigateur (re-sondé le 10/08/2026)

⚠️ **La conclusion « Sofascore est inutilisable, 403 » était liée à la méthode,
pas au site.** Elle valait pour `urllib` et `curl`. Depuis, `browser.py` sait
piloter un vrai Chrome : un `fetch()` exécuté **dans** une page sofascore.com
part en même origine, avec ses cookies — exactement l'astuce qui débloque
`get_evs_n.php` chez Forebet. **L'API répond 200.**

`robots.txt` (lisible seulement depuis le navigateur, `curl` reçoit un 403) :
seul **Bytespider** est banni. Pour `*`, sont interdits les **classements**
(`/standings/` et ses traductions) et les URL de **saisons archivées**
(`/*/2017-` … `/*/2025-`). Aucune règle visant Claude, et `/api/` n'est pas
listé. Les classements, on les a déjà par Forebet.

**Points d'entrée vérifiés** (préfixe `https://www.sofascore.com`) :

    /api/v1/search/all?q=<nom>&page=0     -> id d'équipe, pays, couleurs
    /api/v1/team/<id>/players             -> effectif complet
    /api/v1/team/<id>/events/last/0       -> 30 derniers matchs
    /api/v1/event/<id>                    -> date, tour, saison, stade
    /api/v1/event/<id>/statistics         -> stats du match
    /api/v1/event/<id>/lineups            -> **404 sur cette division**

Tournoi : « Zain First Division », `uniqueTournament` **20044**, saison 25/26.

**C'est LA source pour les effectifs** — de loin la meilleure trouvée, et
autorisée, contrairement à soccer365 :

| club | id Sofascore | joueurs | dont numérotés |
|---|---|---|---|
| Yarmouk SC | 55163 | 33 | 26 |
| Al Sulaibikhat FC | 55165 | 31 | 27 |
| Burgan SC | 192706 | 31 | 9 |
| Khaitan SC | 55157 | 25 | 16 |
| Al-Shamiya FC | 1084291 | 22 | 21 |

Avec poste, numéro de maillot et nationalité. À comparer aux 13 de Transfermarkt
pour Yarmouk. **Restent à identifier : Al Sahel** (l'id 251405 trouvé par
recherche renvoie 0 joueur, ce n'est pas le bon club) **et Sporty**.

**Les statistiques de match sont complémentaires de Forebet, pas supérieures.**
Sur Khaitan - Yarmouk : possession, corners, coups francs, cartons, hors-jeu,
touches, six mètres — **mais aucun tir**, là où Forebet donne total / cadrés /
non cadrés. À l'inverse Forebet n'a ni hors-jeu ni touches. Même piège du zéro
qui veut dire « non couvert » (coups francs 0, six mètres 0). **Forebet reste la
source des stats ; Sofascore apporte les effectifs.**

#### Inventaire complet des points d'entrée (sondés un par un le 10/08/2026)

Tournoi `uniqueTournament` **20044**, saisons **25/26 = 75693**, 24/25 = 60750,
23/24 = 51541, 22/23 = 49166 — quatre saisons d'historique. 21 journées,
journée en cours 18.

| point d'entrée | ce qu'on en tire |
|---|---|
| `/api/v1/search/all?q=` | id d'équipe, pays, **couleurs officielles** |
| `/api/v1/team/<id>` | **stade déclaré, ville, entraîneur**, forme, position |
| `/api/v1/team/<id>/players` | **effectif complet** : poste, n° de maillot, nationalité |
| `/api/v1/team/<id>/events/last/0` | 30 derniers matchs, avec tournoi et score |
| `/api/v1/team/<id>/performance` | 10 derniers résultats + indice de forme |
| `/api/v1/team/<id>/unique-tournament/20044/season/75693/statistics/overall` | buts pour/contre, penaltys, clean sheets, rouges, matchs |
| `/api/v1/unique-tournament/20044/seasons` | les saisons et leurs id |
| `/api/v1/unique-tournament/20044/season/<s>/rounds` | journées, journée en cours |
| `/api/v1/unique-tournament/20044/season/<s>/top-players/overall` | **classement des buteurs — 50 joueurs** |
| `/api/v1/unique-tournament/20044/season/<s>/top-teams/overall` | buts pour/contre, rouges, clean sheets des 8 clubs |
| `/api/v1/unique-tournament/20044/season/<s>/team-events/total` | tous les matchs de la saison |
| `/api/v1/event/<id>` | date, tour, saison, **stade et capacité** |
| `/api/v1/event/<id>/statistics` | possession, corners, coups francs, cartons, hors-jeu, touches, six mètres |
| `/api/v1/event/<id>/incidents` | faits de jeu + couleurs des maillots |
| `/api/v1/event/<id>/h2h` | bilan des confrontations (V/N/D) |
| `/api/v1/player/<id>` | taille, pied fort, date de naissance, fin de contrat, nationalité |
| `/api/v1/player/<id>/unique-tournament/20044/season/<s>/statistics/overall` | **buts et penaltys seulement** |

**Répondent 404 sur cette division** — ne pas re-sonder : `/lineups`,
`/best-players` (notes de joueurs), `/graph` (momentum), `/shotmap`, `/odds`.

⛔ **Les classements sont hors limites** : le `robots.txt` interdit `/standings/`
et `/*/standings/` à tous les robots, ce qui couvre aussi la route d'API. Sans
importance ici, Forebet nous les donne déjà.

**Les statistiques individuelles se réduisent aux buts.** Sur le meilleur buteur
du championnat, les seuls champs non nuls de la saison sont `goals` et
`penaltyGoals` : ni minutes, ni passes décisives, ni notes. Le radar chart par
joueur reste donc impossible, comme conclu dans `kuwait-football` — mais **le
classement des buteurs, lui, existe** (50 joueurs, de 12 buts à 1), et aucune
autre source testée ne l'avait.

#### ⚠️ Qui reçoit : tranché le 11/08/2026 — Flashscore fait autorité

Les sources ne désignent pas le même hôte. Elles s'accordent en revanche sur le
**résultat** et sur les **chiffres par équipe** (Yarmouk 66 % / 9 corners /
1 jaune des deux côtés) : le désaccord porte uniquement sur l'étiquette. Elles
divergent aussi sur le **stade** du même match (« Jaber Al-Mubarak Stadium »
contre « Al Shabab Mubarak Alaiar Stadium »).

**Le relevé, refait proprement le 11/08 :**

| confrontation | accord | inversé |
|---|---|---|
| Flashscore vs Sofascore, saison entière (70 rencontres) | 9 | **61** |
| Forebet vs Flashscore, sur les 10 qu'il étiquette lui-même | **8** | 2 |
| Forebet vs Sofascore, sur ces mêmes 10 | 0 | **10** |

Flashscore n'est donc **jamais minoritaire**, et deux sources indépendantes
s'opposent à Sofascore. D'où la décision : **son hôte fait foi**, et
`hosts.py` remet les rencontres divergentes dans son sens. Concrètement, ça
corrige deux matchs du 02/08 (Al Shamiya - Yarmouk et Al Jazira - Sporty, que
Forebet donnait à l'envers) et laisse tout le reste en place.

Deux pièges méthodologiques, tous deux tombés dedans avant d'en sortir :

- ⚠️ **Ne pas arbitrer sur les rencontres à venir.** Elles viennent déjà de
  Flashscore via `merge_calendar` : les confronter à Forebet, c'est confronter
  Flashscore à elle-même. Seules les 10 rencontres que Forebet étiquette de son
  côté valent quelque chose.
- ⚠️ **Apparier sur la date autant que sur la paire d'équipes.** Un aller-retour
  fournit les deux ordres ; chercher la seule paire trouve toujours une
  correspondance et conclut à tort à l'accord. C'est ce qui avait d'abord fait
  lire « 66 accords sur 70 » là où il y en a 9.

La version précédente de cette section — « Forebet et Sofascore inversent
systématiquement, non tranché » — **était fausse sur les deux points** : le
désaccord ne portait que sur 4 rencontres choisies, et Forebet a raison 8 fois
sur 10.

⚠️ **Ce que l'arbitrage ne rattrape pas** : les bilans « à domicile » et « à
l'extérieur » de la saison, que Forebet calcule lui-même à partir de sa propre
idée de qui reçoit. Permuter une étiquette ne les recalcule pas.

⚠️ **La réserve qui reste** : si Forebet et Flashscore partagent un flux en
amont, leur accord ne vaut pas double, et Sofascore pourrait avoir raison
contre les deux. Rien dans les données ne permet de le dire — il faudrait la
fédération koweïtienne. `--no-hosts` rend l'étiquette à Forebet si la décision
doit être revue.

À noter, et ça relativise l'enjeu : **les clubs partagent les terrains.**
Burgan - Sulaibikhat se joue au « Khaitan Stadium », où Khaitan ne joue pas ;
trois rencontres différentes ont lieu au même « Al Shabab Mubarak Alaiar
Stadium ». Le « domicile » de cette division est largement nominal.

**Le stade déclaré par Sofascore ne tranche pas non plus** : il donne « Mishref
Stadium » pour Yarmouk et « Khaitan Stadium » pour Khaitan, alors que leur
rencontre du 07/08 s'est jouée au **« Jaber Al-Mubarak Stadium »** — le terrain
d'aucun des deux. Les équipes ne jouent tout simplement pas chez elles. Il
faudra une source officielle (fédération koweïtienne) ou rien.

### Flashscore (évalué le 06/08/2026)

**Accès autorisé** : son `robots.txt` bloque une vingtaine de robots (CCBot,
Meta, Diffbot, cohere-ai, YouBot…) mais **ni ClaudeBot ni aucun agent
Anthropic**. Sous `User-agent: *`, seuls `/standings/`, `/draw/` et `/newsfeed/`
sont interdits — le classement, on l'a déjà par Forebet.

**Mais la couverture s'arrête au score.** La fiche match affiche noir sur blanc
« **FRO — FINAL RESULT ONLY** », et les onglets se limitent à Summary, H2H,
Standings et cotes : pas de compositions, pas de statistiques, pas de
chronologie. La page équipe n'a pas d'onglet effectif ; l'URL `/squad/` retombe
sur le résumé. Seul l'onglet Transferts contient des noms de joueurs (arrivées
et départs datés), ce qui ne reconstitue pas un effectif.

Identifiants d'équipe relevés (format `/team/<slug>/<id>/`) : Yarmouk `pfvGnj7E`,
Al Sulaibikhat `KhA7k6SK`, Al Sahel `MepdeKsB`, Al-Jazira `zaSgiucB`, Khaitan
`4KZ0fvcH`, Burgan `j5EVs5UB`, Al Shamiya `vFTknll1`, Sporty `U3drhvxK`.

**Le seul apport réel de Flashscore : un calendrier plus lointain.** Là où la
page ligue Forebet ne montre que la journée en cours et la précédente,
Flashscore annonce les rencontres suivantes (Al-Jazira : 09/08, 13/08, 16/08,
20/08). C'est la réponse à la limite notée plus haut sur l'horizon « 7 jours ».
Il confirme aussi la journée 17, ce qui valide la déduction `max(joués) + 1`.

Bilan : **Forebet reste strictement supérieur pour les statistiques** (il a
possession et tirs via `get_evs_n.php`, Flashscore n'a rien). Flashscore ne sert
qu'au calendrier — c'est exactement l'usage qui en est fait.

#### La page `results/`, branchée le 11/08/2026

Second usage depuis l'arbitrage de l'hôte : `load_results()` lit
`/football/kuwait/division-1/results/`, **70 rencontres depuis le 14/09/2025**.
C'est la seule source qui porte, sur les matchs passés, une étiquette
domicile/extérieur indépendante de Forebet. Elle est autorisée : `robots.txt`
n'interdit que `/standings/`, `/draw/` et `/newsfeed/`.

Deux pièges de parsing, réglés :

- **Deux formats de date cohabitent sur la même page** : « 06.08. 19:45 » pour
  les rencontres récentes, « 31.12.2025 » — datée mais sans heure — pour les
  plus anciennes. Ne lire que la première laissait **36 résultats sur 70 sans
  date**, donc hors d'atteinte de l'arbitrage.
- **`resolve_year()` raisonnait à l'envers sur cette page.** Son heuristique
  (« une date loin dans le passé appartient à l'année suivante ») vaut pour un
  calendrier, pas pour des résultats : une rencontre de janvier lue en août s'y
  retrouvait datée de 2027. D'où le paramètre `past=True`.

### Calendrier lointain, branché le 06/08/2026

`fetch_flashscore.py` -> 20 rencontres, du 06/08 au 20/08 (5 journées), là où la
page ligue Forebet n'en montrait que 2 jours.

    python fetch_flashscore.py                     # seul
    python build_console.py --fixtures --scope all # fusion automatique
    python build_console.py --fixtures --no-calendar

Sélecteurs : `div.event__match` (l'attribut `id` porte l'identifiant Flashscore),
`.event__homeParticipant` / `.event__awayParticipant`.
⚠️ **Ne pas s'appuyer sur les classes de style** : elles sont hachées et changent
à chaque déploiement (`wcl-participant_bctDY`). Pour l'horaire, passer par
`[data-testid="wcl-stageTime"]`, stable.
⚠️ **Flashscore n'affiche pas l'année** (« 06.08. 19:45 ») : `resolve_year()`
prend l'année courante et bascule sur la suivante si la date obtenue est à plus
de 120 jours dans le passé — sinon le passage décembre/janvier casserait tout.

**Rapprochement des noms.** Les deux sources n'écrivent pas les clubs pareil :
« Yarmouk (KUW) » / « Yarmouk », « Sulaibikhat » / « Al Sulaibikhat »,
« Khaitan SC » / « Khaitan », « Al Jazira » / « Al-Jazira ». `normalise()` retire
parenthèses, `al`, `fc`, `sc` et la ponctuation. Sans ça, le sélecteur d'équipes
afficherait seize entrées au lieu de huit et rien ne se dédoublonnerait.

**Dédoublonnage sur la paire d'équipes**, pas sur la date : les deux sources
peuvent diverger d'un jour (déjà constaté), et une même affiche ne se rejoue pas
dans la fenêtre couverte. Résultat vérifié : 20 rencontres Flashscore, 4 déjà
connues de Forebet écartées, **16 ajoutées**, 24 au total sur 7 dates, aucun
doublon.

Les rencontres venues de Flashscore portent `source: "flashscore"`, n'ont pas de
`match_id` et s'affichent « au calendrier » — et non « fiche non récupérée », qui
laisserait croire à un échec de collecte. Forebet reste la source de référence :
c'est lui qui apporte l'identifiant et la fiche détaillée, et ce sont ses noms de
clubs qui sont affichés. Si Flashscore tombe, le build continue sans lui.

## Bouton « Rafraîchir » (10/08/2026)

### Forebet n'autorise pas le navigateur — mesuré, pas supposé

Depuis l'origine `https://haris692.github.io`, un `fetch()` sur la page ligue
**et** sur `get_evs_n.php` échoue en `TypeError: Failed to fetch` : **aucun
en-tête CORS**. C'est la différence avec `kuwait-football`, où TheSportsDB
renvoie `Access-Control-Allow-Origin: *` et permet un vrai bouton côté client.
**Ne pas re-tester, et ne pas promettre un rafraîchissement en ligne.**

### Le bouton fait donc deux choses, et le dit

1. **Servie par `serve.py`** (nouveau) : `POST /api/refresh` déclenche la
   collecte Python complète (`assemble()` avec `force=True`), réécrit la page
   et son fichier de données, et renvoie la charge utile. La console se
   redessine sans rechargement. ~1 min.
2. **Publiée ou en `file://`** : repli sur le fichier de données déposé à côté
   de la page. Le bouton rapporte ce qui a été *publié* depuis la génération de
   la page, et annonce explicitement quand il n'y a rien de plus récent.

⚠️ **Ne pas détecter `serve.py` par le code HTTP.** Un `http.server` nu répond
**501** à un POST, GitHub Pages **405**, un autre hébergeur autre chose. La
première version traitait tout ce qui n'était pas 404 comme une collecte ratée
et affichait « la collecte a échoué : HTTP 501 » au lieu de se rabattre. Le
test qui marche : **le `Content-Type` est-il du JSON ?** `serve.py` en renvoie
sur toutes ses réponses, succès comme erreur.

### Deux détails qui comptent

- **Le fichier de données porte le nom de sa page** : `index.html` →
  `index.data.json`. Avec un `data.json` unique, chaque build local sur
  `console.html` écrasait la donnée publiée et salissait le dépôt. Le bouton
  reconstruit ce nom depuis `location.pathname`.
- **Les écussons n'y sont pas** : 387 Ko de `data:` URI sur 556, pour des images
  que la page a déjà. `applyData()` garde donc celles de la page quand la charge
  utile reçue n'en apporte pas. Résultat : 165 Ko au lieu de 556. La réponse de
  `serve.py`, elle, est complète.

La charge utile reste **embarquée dans la page** en plus d'être servie à part :
la console doit continuer de s'ouvrir seule, en `file://` et hors ligne. C'est
la raison d'être du fichier unique, on ne la sacrifie pas au bouton.

## Console bilingue (10/08/2026)

L'interface bascule **français / anglais**, détectée d'après le navigateur et
forçable par un bouton (retenu en `localStorage`).

**La langue du brief Instagram est un réglage séparé**, avec son propre bouton
dans la barre du haut. Raison : le carrousel est du contenu éditorial destiné au
compte de Haris ; sa langue est un choix de publication, pas une conséquence du
navigateur d'un visiteur de passage. Par défaut : interface selon le navigateur,
brief en français.

**Détection : la PREMIÈRE langue déclarée décide.** Une première version
regardait si « fr » figurait *quelque part* dans `navigator.languages` — un
visiteur en `en-GB, fr` recevait alors du français alors qu'il demande
l'anglais. Vérifié : `en-US` → en, `de-DE` → en, `ar-KW` → en, `fr-CA` → fr,
`en-GB, fr` → **en**.

**Le dictionnaire `EN` est indexé par la chaîne française elle-même**, pas par
une clé abstraite : le code reste lisible (`t("Comparatif")`) et une entrée
oubliée retombe sur le français plutôt que d'afficher une clé nue. Les phrases à
trous vivent dans `PH`, écrites en entier dans les deux langues.

Trois pièges rencontrés, tous à retenir :

- ⚠️ **`t` était déjà pris quatre fois** comme nom de variable locale (`const t =
  el("table")` dans `matchTable` et `renderStandings`, `tile()`, le paramètre de
  `group` et de `forEach`). Chacun masquait la fonction de traduction dans son
  bloc. Tous renommés — c'est le genre de collision que `node --check` ne voit
  pas et qui explose à l'exécution.
- ⚠️ **Les libellés de rubriques sont de la donnée, pas de l'interface.** Les
  clés de `stats.others` (`Corners`, `Hors-jeu`, `Six mètres`, `Arrêts du
  gardien`, `Penaltys`, `Tacles`, `Touches`, `Fautes`, `Cartons jaunes`,
  `Cartons rouges`, `Aucun but encaissé`) arrivent en français depuis Forebet.
  On traduit à l'affichage ; traduire la clé casserait les recherches. Les onze
  ont été relevées dans les données, pas devinées.
- **Les libellés d'événements** (`but`, `carton jaune`) sont composés en
  français par `fetch_stats.py`. La console repart de `type`, qui est neutre.

Les lettres de forme deviennent **W/D/L** en anglais, mais la **classe CSS reste
V/N/D** : c'est elle qui porte les couleurs.

## Effectifs livrés (10/08/2026) — 230 joueurs, 8 clubs

`fetch_squads.py` collecte les effectifs chez Sofascore et écrit
`data/squads.json`. `build_console.py` les accroche à chaque fiche, et la
console affiche une carte **« Effectifs »** en deux colonnes, groupée par poste,
avec numéro de maillot, code pays et **buts marqués**.

    python fetch_squads.py --summary

| club | id Sofascore | joueurs | entraîneur |
|---|---|---|---|
| Yarmouk SC | 55163 | 33 | João Mota |
| Al Jazeera FC Kuwait | (via le tournoi) | 32 | — |
| Al Sulaibikhat FC | 55165 | 31 | António Miranda |
| Burgan SC | 192706 | 31 | — |
| Al Sahel SC | (via le tournoi) | 30 | Yousef Mudhaf |
| Sporty FC | 1093203 | 26 | Ibrahim Shehab |
| Khaitan SC | 55157 | 25 | Cenk Ozcan |
| Al-Shamiya FC | 1084291 | 22 | Falah Anwar Al Sahli |

**Les clubs sont découverts par le tournoi, pas par recherche de nom.** La
recherche ramène des homonymes (« Al-Yarmouk » existe aussi en Libye et en
Jordanie) et **ne trouvait pas Sporty ni Al Sahel** — les deux ids relevés à la
main le 10/08 étaient d'ailleurs faux. `top-teams/overall` rend exactement les
8 équipes rattachées à la compétition ; c'est cette liste qui fait foi.

**Rapprochement des noms** : `normalise()` de `fetch_flashscore` règle sept cas
sur huit. Le huitième est une divergence de translittération, pas de préfixe —
« Al Jazeera FC Kuwait » contre « Al Jazira » — d'où un unique alias
`jazeerakuwait -> jazira`. **8/8 rapprochés**, vérifié.

**Les buts sont joints à chaque joueur** depuis le classement des buteurs : sans
eux la carte ne serait qu'un annuaire. C'est la seule statistique individuelle
que la source renseigne — ni minutes, ni passes décisives, ni notes.

⚠️ **Ce ne sont pas des compositions.** Aucune source ne publie de feuille de
match sur cette division. La carte le dit explicitement, pour qu'on ne lise pas
« 33 joueurs » comme un onze de départ.

ℹ️ **Un doublon dans la source** : « Metab Fahad Al Salamah » apparaît deux fois
chez Sporty, sous **deux identifiants distincts** (1647399 avec le n° 7, et
1629417 sans numéro). Volontairement **non fusionné** : à deux ids différents on
ne peut pas distinguer un doublon d'un homonyme, et fusionner supprimerait un
vrai joueur dans le second cas. Un joueur sur 230.

ℹ️ **Le stade déclaré par club est conservé (`declared_venue`) mais n'est pas
affiché** : ce n'est pas là que le club joue, les terrains étant partagés.

## Mode direct (10/08/2026)

La console suit les rencontres pendant qu'elles se jouent : score, possession et
tirs se mettent à jour tout seuls, sans rechargement.

**L'architecture est le point important.** La règle « rafraîchissement déclenché
à la main, jamais périodique » (héritée de `kuwait-football`) visait à ne pas
marteler la source. Le direct la respecte en déplaçant la périodicité **du côté
serveur** :

- `serve.py` tient un **unique fil de fond** (`LiveCollector`) qui relève les
  seuls matchs en cours, **une fois par minute**, avec un seul Chrome gardé
  ouvert d'un cycle à l'autre ;
- la page interroge `GET /api/live` toutes les **15 s**, mais ne fait que **lire
  le dernier instantané** — elle ne déclenche aucune collecte ;
- donc **dix onglets ouverts coûtent à Forebet exactement ce que coûte un
  seul**, ce qu'un polling côté page n'aurait pas permis.

Trois garde-fous, chacun pour une raison précise :

- **Le collecteur démarre à la première demande et s'arrête après 180 s sans
  demande.** Fermer l'onglet suffit donc à ne plus solliciter la source — sinon
  un `serve.py` oublié la sonderait toute la nuit.
- **C'est le serveur qui décide quoi relever**, à partir des `fixtures` de son
  `data.json` ; la page n'envoie aucun identifiant. Sans ça, un onglet pourrait
  lui faire interroger n'importe quel `match_id`.
- **`/api/refresh` a la priorité** : les deux pilotent le même Chrome sur le
  port CDP 9333. Le direct tente `Handler.lock` sans bloquer et **saute son
  tour** si une collecte complète est en cours.

Fenêtre « en cours » : de 5 min avant le coup d'envoi à 150 min après. Large,
parce que **rien dans la source ne dit qu'un match est fini** — c'est `ft_score`
qui, en se remplissant, sort la rencontre du suivi.

**Côté page** : un bouton « ● Direct » qui **n'apparaît que pendant qu'une
rencontre se joue** (inutile un mardi matin), allumé par défaut, le refus étant
retenu en `localStorage`. Score en rouge et pastille « en direct » qui bat dans
la liste ; badge sur la carte « Statistiques du match », qui dit aussi qu'un
relevé en direct est encore incomplet. `renderAll()` rappelle `syncLive()` : une
rencontre qui entre dans sa fenêtre allume le direct **sans rechargement**.

⚠️ **`played` n'est jamais modifié par le direct**, seulement `score` et `live` :
un match en cours n'est pas un match joué, et les filtres doivent continuer de
le classer parmi les rencontres à venir.

⚠️ **Rien de tout ça ne marche sur GitHub Pages** — `/api/live` n'y existe pas.
La page le détecte (réponse non-JSON, comme pour « Rafraîchir »), coupe le suivi
et le dit. Le direct est une fonctionnalité de `python serve.py`, point.

Vérifié en conditions réelles pendant Sahel - Al Shamiya et Khaitan - Al Jazira
le 10/08 : deux cycles à 62 s d'intervalle, possession 70 → 71 %, tirs 5 → 6,
aucune erreur console, bascule arrêt/reprise et persistance du refus contrôlées.

### Le direct passe aussi dans le site (12/08/2026)

Jusqu'ici le direct était une fonctionnalité de la **console**. Il est maintenant
consommé par le **site** lui aussi : servi par `serve.py`, l'accueil et la fiche
de match voient leur score et leurs statistiques bouger seuls pendant la
rencontre. Rien de nouveau côté serveur — c'est le même `GET /api/live`, le même
fil de fond, le même coût pour Forebet.

`src/js/core/live.js` est le seul ajout. Trois décisions y sont inscrites :

- **L'absence de direct n'est pas une erreur.** Sur GitHub Pages `api/live`
  répond 404 ; on arrête définitivement le suivi et **il ne doit rien en
  paraître** — pas de bandeau, pas de message d'échec. Un `Failed to fetch`, lui,
  est toléré trois fois : le serveur peut redémarrer sous la page.
- **Le chemin est relatif** (`api/live`, pas `/api/live`) : le site publié vit
  sous `/football-stats-scraper/`, et en local les deux formes coïncident — la
  faute ne serait apparue qu'au déploiement.
- **On ne s'abonne pas s'il n'y a rien à suivre**, et un onglet caché suspend la
  demande : c'est elle qui tient le collecteur éveillé (`LIVE_IDLE_STOP`, 180 s).

⚠️ **Seuls deux emplacements sont redessinés** — la une de l'accueil, le tableau
d'affichage et la carte de statistiques du match. Reconstruire la page entière
toutes les quinze secondes ferait sauter l'onglet choisi, la position de lecture,
la sélection de texte et le défilement des rails horizontaux, pour un chiffre qui
bouge une fois par heure. Et on ne prévient les abonnés **que si le relevé a
changé**.

⚠️ Le marqueur rouge recouvre désormais **deux situations**, et l'infobulle est
ce qui les sépare : sans serveur il dit « ça se joue », déduit de l'horloge ; avec
serveur, `liveMark(true)` dit que le score est relevé chaque minute. Ne jamais
laisser l'un porter la phrase de l'autre. La note de méthode de la carte, en
direct, dit aussi ce que le direct **ne sait pas** : ni la minute de jeu, ni le
statut — la source ne les publie pas.

`serve.py` sert les deux façades depuis le même dossier ; `--site` ne choisit que
la page ouverte au démarrage.

### Une collecte `--club` n'écrase plus les sept autres (12/08/2026)

⚠️ `fetch_players.py` repartait d'un dictionnaire vide. Une passe `--club` — ou
une passe complète interrompue par `Flaky` — réécrivait donc `data/players.json`
avec **le seul club collecté**. C'est arrivé le 11/08, Khaitan effacé par
Al Jazira. On repart maintenant des fiches déjà écrites. Le revers du cumul est
traité dans la foulée : l'effectif du jour fait foi **pour le club collecté
seulement**, et un joueur qui n'y figure plus est retiré.

## Sofascore élargi (11/08/2026)

Sondage endpoint par endpoint, pour savoir ce que cette source a vraiment sur
cette division. **Le partage avec Forebet ne change pas** — les chiffres du
match restent chez Forebet — mais Sofascore comble trois trous réels.

| endpoint | verdict |
|---|---|
| `event/{id}/incidents` | ✅ **buteurs nommés et minutés**, cartons minutés |
| `.../events/round/{n}` + `/rounds` | ✅ saison complète, **numéro de journée**, journée courante |
| `event/{id}/managers` | ✅ les deux entraîneurs du soir |
| `team/{id}/.../statistics/overall` | ✅ clean sheets, **buts sur penalty**, rouges |
| `event/{id}/statistics` | ❌ **une seule ligne : « Red cards »** |
| `lineups`, `best-players`, `graph`, `odds` | ❌ 404 |

⚠️ **Ne pas relire « Sofascore n'a aucun tir » comme « Sofascore n'a rien ».**
L'endpoint `statistics` existe et répond 200 : il est simplement presque vide.
C'est ce qui rend Forebet irremplaçable pour possession et tirs.

**Ce que ça change dans la console** : la carte « Statistiques du match »
affiche désormais une chronologie **nommée** — 195 buts datés sur la saison,
**187 avec un buteur** (96 %). L'ancienne chronologie Forebet reste en repli
pour une rencontre trop récente pour Sofascore. Le brief Instagram cite les
buteurs au lieu de « 87' Al Jazira », et la journée affichée est relevée au
lieu d'être déduite du nombre de matchs joués.

**Les buts sur penalty valent le détour** : Forebet affiche « 0 / 0 » pour tous
les clubs, Sofascore compte 3 penaltys pour Sahel et 3 pour Sulaibikhat. D'où
un groupe « Bilan de saison · Sofascore » **à part** dans le comparatif : les
deux sources ne comptent pas le même nombre de matchs, les fondre ferait
passer un décalage de fraîcheur pour une contradiction.

⚠️ **Tout ce qui sort de Sofascore arrive dans SON orientation.** Il inverse
Flashscore sur 61 rencontres sur 70. `attach_events()` compare son hôte au
nôtre et retourne le `side` — **et aussi le score courant** porté par chaque
événement, sans quoi la chronologie annoncerait « 1-0 » au moment où notre hôte
vient d'encaisser. Cette fonction doit tourner **après** `arbitrate()`, jamais
avant.

ℹ️ **Coût maîtrisé** : ~150 requêtes à la première collecte, puis presque rien.
Une rencontre terminée ne bouge plus, son relevé est donc mis en cache 30 jours
et `--force` ne s'y applique pas — même compromis que `attach_stats()`.

## Rafraîchissement quotidien (11/08/2026)

`daily.py` enchaîne effectifs → rencontres → console, puis commite et pousse
**ce qui a changé, et rien si rien n'a changé**. `schedule_daily.ps1` l'inscrit
au planificateur Windows à 8 h.

**Pourquoi une tâche locale et pas un agent dans le cloud** : la collecte a
besoin du Chrome de cette machine et de la clearance Cloudflare gardée dans
`.chrome-profile/`. Depuis ailleurs, Forebet renvoie un challenge insoluble. La
tâche tourne donc en session ouverte (`-LogonType Interactive`), avec
`StartWhenAvailable` pour rattraper une machine éteinte à 8 h.

⚠️ **Ça revient sur la règle « déclenchement manuel strict, jamais
périodique »** héritée de `kuwait-football`. Assumé : cette règle visait à ne
pas marteler la source, et une passe quotidienne qui laisse le cache servir
tout ce qui est figé en est très loin. Le mode direct l'avait déjà déplacée une
première fois, pour la même raison.

Deux garde-fous, chacun pour une raison précise :

- **La première étape en échec arrête tout.** Régénérer la page à partir d'une
  collecte incomplète publierait une régression que personne ne verrait passer.
- **La publication énumère ses fichiers** au lieu d'un `git add -A` : un
  `cache/` ou un `.chrome-profile/` qui échapperait au `.gitignore` n'a rien à
  faire dans un commit automatique que personne ne relit.

Journal dans `daily.log`. À la main : `Start-ScheduledTask -TaskName
FootballStatsScraper-Daily`, ou `python daily.py --dry-run` pour voir ce qu'il
ferait.

### ⚠️ Le cache de la page ligue n'avait pas d'âge (12/08/2026)

**Le bug qui gelait les résultats**, et il aurait survécu à la correction
ci-dessous. `fetch_fixtures.load_league_html()` rendait le fichier de cache dès
qu'il **existait** — sans jamais regarder sa date, contrairement à
`browser.get()` qui applique `max_age_hours`. Une fois la page écrite, plus
rien ne la rafraîchissait sauf `--force`, que `daily.py` ne passe pas.

Ce qui rend la panne difficile à voir : **cette page est la seule à porter
`score` et `played`** pour le calendrier. Les fiches détaillées ont leur
`full_time`, mais rien ne le remonte dans la liste. Le 12/08 le site affichait
donc « à venir » deux rencontres jouées la veille, **alors que leur fiche
connaissait le score** — 3-1 et 3-0, avec possession, tirs et chronologie
nommée. Symptôme trompeur : la donnée avait l'air manquante, elle était juste
invisible depuis la liste.

Corrigé en donnant à cette page son propre âge, plus court que le défaut :
`LEAGUE_MAX_AGE_HOURS = 1.0`. Elle change plusieurs fois par jour et ne coûte
qu'une requête. Le `cache_path` importé ne sert plus.

⚠️ Règle à retenir : **un cache sans date n'est pas un cache, c'est un gel.**
Si un jour un autre chargeur court-circuite `browser.get()`, il refera ce bug.

### ⚠️ Les fiches joueurs sont sorties du quotidien (12/08/2026)

**Le rafraîchissement publie le résultat des matchs de la veille et leur
détail. Rien d'autre.** `fetch_players.py` en a été retiré : 230 requêtes et des
dizaines de minutes pour des dates de naissance qui ne changent jamais d'un jour
à l'autre.

Ce n'est pas une optimisation, c'est une correction. Le garde-fou « la première
étape en échec arrête tout » est juste, mais il transforme la fragilité de
n'importe quelle étape en panne de publication **pour tout le reste**. Cas réel
du 12/08 : les rencontres du 11 étaient collectées à 08:33, les fiches joueurs
ont expiré à 08:44 (`Page.goto: Timeout`), et le site est resté figé — deux
rencontres affichées « à venir » le lendemain de leur coup d'envoi. La veille,
même chose depuis `fetch_squads.py` (`Failed to fetch`, Cloudflare).

La règle qui en sort : **ne mettre dans le quotidien que ce qui change
quotidiennement.** Une étape lente et faillible qui garde une donnée figée n'a
rien à faire devant celle qui porte les scores.

Les fiches se collectent donc à la main, quand un effectif bouge :
`python fetch_players.py --club yarmouk`. Elles restent dans `PUBLISHED` — le
rafraîchissement du lendemain les pousse avec le reste.

## Refonte de l'interface (11/08/2026)

Le problème n'était pas le manque de données, c'était de ne rien y retrouver :
**neuf cartes empilées sur 5 737 px**, toutes du même poids visuel, chacune
précédée de trois lignes d'explication, et **le score nulle part en évidence**.

### Ce qui change

**Trois onglets, par intention** — « Le match », « Les équipes », « La saison ».
Le découpage suit ce qu'on cherche, pas les sources, qui ne regardent que nous.
L'onglet du match tombe de 5 737 à ~1 500 px. Le choix est retenu en
`localStorage` : on compare souvent le même onglet sur plusieurs rencontres.

**Un tableau d'affichage collant en haut** : les deux clubs, leur rang et leurs
points, et le score en grand. Il ne bouge plus quand on descend — on ne doit
jamais avoir à remonter pour se rappeler qui menait. Le score est un bouton :
il ramène à la liste des rencontres, seul chemin pour changer de match une fois
dans les onglets.

⚠️ **Le classement n'est plus dans une colonne collante à droite.** Le bandeau
porte le rang et les points des deux clubs — la seule part dont on ait besoin en
lisant un match — et la table complète vit dans « La saison ». Garer un tableau
de huit lignes en permanence coûtait une colonne pour une information qu'on
consulte deux fois.

**Les notes de méthode se replient** (`<details class="note">`). Cette console
tient à dire ce qu'elle sait et ce qu'elle ignore — c'est ce qui la distingue
d'un tableau de chiffres sans provenance — mais fois neuf cartes, ça faisait
trente lignes de commentaire devant les données. Le stade et la mi-temps, eux,
**restent visibles** : c'est du relevé, pas de la méthode.

### La direction : le tableau d'affichage, à 19 h 25

Toutes les rencontres de cette division se jouent le soir sous les projecteurs.
D'où un fond sombre par défaut, et **pas d'un noir neutre** : une pointe de vert
(`#0c1310`), celle d'une pelouse éclairée de nuit, et une encre légèrement
verdie plutôt que du blanc pur. Un seul accent chaud, `--flood` (`#f2c14e`), la
couleur du projecteur — **réservé à la ligne de score, au rail et au direct**.
Le clair reste à un clic et reste soigné.

Typographie : **Bahnschrift** pour l'affichage, le DIN livré avec Windows, la
lettre des panneaux de signalisation. Elle est sur la machine, sans rien
télécharger — la page doit rester un fichier autonome et hors ligne. Replis vers
`DIN Alternate`, `Oswald`, `Roboto Condensed`.

⚠️ **La paire domicile/extérieur ne bouge pas** : `#3987e5` / `#d95926` en
sombre, validée CVD ΔE 26.8. La refonte change le sol et la typographie, pas les
couleurs porteuses de sens.

### La signature : le rail des minutes

Depuis que Sofascore nous donne des buteurs **nommés et minutés**, on peut poser
le match sur une ligne de temps : domicile au-dessus, extérieur au-dessous,
chaque but à sa minute, **avec le score qu'il installe**. C'est ce qui
transforme une frise de pastilles en récit — on voit l'égalisation arriver. Le
seul endroit de la page où l'on dépense de l'emphase.

Trois détails qui ont demandé une reprise :

- **La fin du rail suit le match** (`max(96, dernière minute)`) : à 96 fixe, un
  but à 90+9 s'écrasait contre le bord.
- **Deux buts trop proches écrivaient leurs minutes l'une sur l'autre.** Sous
  5 minutes d'écart et du même camp, on garde la pastille et on lâche le
  chiffre, qui reste dans l'infobulle.
- **Un but sans buteur nommé affiche le club**, pas « buteur non nommé » : le
  camp est une vraie information, la mention répétée n'en est pas une.

### Détails de mise en œuvre à ne pas re-découvrir

- ⚠️ **`note` était déjà pris** : c'est la fonction qui écrit la ligne d'état du
  bouton « Rafraîchir ». Le helper des notes repliées s'appelle `methodNote`.
  Deux `const note` dans la même portée = erreur de syntaxe, page blanche.
- ⚠️ Deux fonctions déclarent une variable locale `note` (`renderIdentity`,
  `renderCompare`). Elle masque le helper global dans ces portées — d'où le nom
  distinct plutôt qu'un renommage en cascade.
- Le conteneur `#fixtures` a disparu du HTML : `renderFixtures()` **renvoie**
  désormais une carte au lieu d'écrire dans un hôte, et c'est `renderDetail()`
  qui la place dans l'onglet « La saison ».
- `.controls` ne se repliait pas : sept boutons alignés débordaient sous 520 px.

## Homme du match (11/08/2026)

Demandé pour le carrousel de la J18. **Un meilleur joueur ne se calcule pas sur
cette division** : ni note, ni minutes jouées, ni passes, ni arrêts du gardien —
vérifié endpoint par endpoint chez Sofascore comme chez Forebet. La seule
statistique individuelle qui existe, ce sont les buts.

D'où deux provenances, jamais une troisième, et **la console dit toujours
laquelle** :

- **`auto`** — un joueur a marqué au moins deux buts dans la rencontre. Seul cas
  où la donnée tranche seule. Calculé depuis la chronologie Sofascore.
- **`observé`** — saisi dans `data/motm.json` par quelqu'un qui a regardé le
  match. C'est ce qui permet de désigner un gardien ou un milieu.

La mention voyage jusque dans le brief Instagram (`observé, non mesuré` /
`d'après les buts marqués`). Sans elle, un carrousel présenterait un jugement
comme une mesure — ce que toute cette console s'emploie à éviter ailleurs.

⚠️ **`attach_motm()` tourne après `attach_events()`** : le doublé se lit dans la
chronologie, et le camp doit déjà être dans le bon sens.

ℹ️ Laisser un côté absent est un choix valable, et c'est ce qui a été fait pour
Al Shamiya le 10/08 : battue 0-3 avec 5 tirs, il n'y avait personne à désigner.

ℹ️ **On ne sait pas qui garde les buts.** Khaitan aligne deux gardiens dans son
effectif (Ahmad Al Dousari n°40, Ossama Al Enezi) et aucune source ne publie de
composition. Le 10/08, l'entrée dit donc « Le gardien de Khaitan », sans nom.

## Le site public (11/08/2026)

La console était **un outil** : un fichier unique de 750 Ko, autonome, ouvrable
hors ligne. Le projet doit maintenant être **montré à des clubs koweïtiens** —
c'est un site, et un site se visite.

### L'architecture

```
index.html  calendrier.html  classement.html  clubs.html  club.html  match.html
assets/css/   tokens · base · components · pages
assets/js/core/        dom · i18n · data · shell
assets/js/components/  pieces · cards · rail
assets/js/pages/       un module par page
data/site.json (230 Ko)   data/crests.json (377 Ko)
```

⚠️ **Le fichier unique ouvrable en `file://` disparaît.** Un site multi-pages
charge ses données par `fetch`, donc il lui faut un serveur — GitHub Pages ou
`python serve.py`. C'était la propriété fondatrice de `console.html` ; elle est
échangée contre la navigation, sciemment.

ℹ️ **`console.html` reste l'outil interne** et garde ce qui n'a rien à faire sur
un site public : le générateur de brief Instagram. Les deux se construisent
depuis la même collecte (`assemble()`), donc les chiffres ne peuvent pas
diverger.

**Deux fichiers de données, chargés en parallèle** : `site.json` porte tout ce
qui s'affiche, `crests.json` ne porte que des images. Séparés, un score ne
patiente pas derrière 377 Ko d'écussons ; les emplacements sont réservés à la
bonne taille et les images se posent sans décaler la page.

### Ce que le site emprunte aux plateformes vidéo, et pourquoi

Des **rails horizontaux** — derniers résultats, prochaines rencontres, buteurs,
clubs. C'est le seul emprunt, et il ne tient que parce qu'il y a de quoi les
remplir : 84 rencontres, 50 buteurs, 8 clubs. `railOrGrid()` bascule
automatiquement en grille sous quatre cartes, un rail qui ne défile pas étant
une grille déguisée. Les flèches n'apparaissent qu'à la souris et se cachent aux
extrémités : une flèche qui ne mène nulle part est un mensonge.

### Trois bugs de données trouvés en construisant

- ⚠️ **Le classement affiché était périmé.** Chaque page match de Forebet
  embarque la table **à sa date** ; prendre la première fiche venue affichait
  Yarmouk 1er à 35 pts alors que Sahel menait à 40. `freshest_standings()`
  retient la table dont les équipes ont disputé le plus de rencontres. Le rang
  affiché vient désormais de l'annuaire, jamais de la fiche.
- ⚠️ **Le calendrier de saison partait à l'envers.** Sofascore est la seule
  source à couvrir septembre → août, mais il inverse domicile/extérieur sur 61
  rencontres sur 70. Flashscore couvrant elle aussi toute la saison par sa page
  résultats, `season_events()` arbitre chaque rencontre contre elle :
  **84/84 arbitrées**. Sans ça, presque tout le calendrier aurait été faux.
- Les intitulés de groupe des barres comparées étaient avalés par le test des
  lignes vides — ils n'ont, par nature, ni valeur à gauche ni valeur à droite.

### Détails à ne pas re-découvrir

- `daily.py` lance **`build_site.py`**, plus `build_console.py --out index.html`
  qui écraserait maintenant une page statique versionnée.
- `el()` **refuse le HTML sous forme de chaîne** : aucun nom de joueur ou de
  club venu d'une source ne peut être interprété comme du balisage.
- La racine du site est déduite d'`import.meta.url` et non de la page courante :
  c'est ce qui rend le site déployable dans un sous-dossier, cas de GitHub
  Pages.
- Le thème est posé par un script en ligne **avant le premier rendu**, sinon la
  page clignote en sombre avant de basculer en clair.
- Les modules ES sont mis en cache par le navigateur : après un déploiement,
  penser à un rechargement forcé pour vérifier une correction.

## ⚠️ L'écran noir des modules ES (11/08/2026)

Après un déploiement, cliquer sur une rencontre donnait une **page noire**, sans
message. La console disait :

    SyntaxError: The requested module '../core/data.js'
    does not provide an export named 'isLive'

**Ce n'était pas un accident, c'était structurel.** Un navigateur met chaque
module ES en cache **par URL**. GitHub Pages sert avec `max-age=600` : pendant
les dix minutes qui suivent un déploiement, un visiteur récent peut recevoir un
`match.js` neuf et garder un `data.js` périmé. Les deux ne s'accordent plus, le
graphe de modules **ne se lie pas**, et un graphe qui ne se lie pas n'exécute
rien — ni rendu, ni `try/catch`, ni écran d'erreur. Écran noir.

⚠️ **Un `?v=` sur l'entrée ne corrige pas ça** : la requête n'est pas héritée
par les imports. `match.js?v=2` importe toujours `../core/data.js` tout court,
donc la version en cache. Ne pas retenter cette piste.

**La correction, en deux niveaux :**

1. **Les sources déménagent dans `src/`**, et `build_site.py` en publie une
   copie sous `assets/<empreinte>/`. Les imports relatifs se résolvent à
   l'intérieur de la copie : une page charge donc toujours un jeu cohérent, et
   un état mixte devient impossible. L'empreinte vient du contenu — une
   construction qui ne change rien ne casse aucun cache.
2. **Un filet dans le HTML**, en script *classique* et non en module : c'est un
   module qui peut échouer, et il faut que le secours survive à son échec. Il
   guette les erreurs, et si `#main` est encore vide 1,2 s après le chargement,
   il affiche ce qui s'est passé et un bouton qui recharge en contournant le
   cache. Vérifié en cassant volontairement une page.

ℹ️ **La racine du site se coupe désormais sur `/assets/`** au lieu de compter
les niveaux : `../../../` pointait à côté dès que l'empreinte a ajouté un
niveau. C'est le genre de chemin qui casse en silence à la première
réorganisation.

ℹ️ `daily.py` publie donc aussi `assets/` et les six pages : `build_site.py`
les réécrit quand l'empreinte change.

## Fiches joueurs (11/08/2026)

⚠️ **Une conclusion du projet était trop large et doit être corrigée.**
`kuwait-football` puis ce dépôt affirmaient qu'« aucune statistique
individuelle n'existe sur cette division ». C'est vrai des statistiques **de
match** par joueur — et seulement de celles-là.

Sondé endpoint par endpoint le 11/08 :

| endpoint | verdict |
|---|---|
| `player/{id}` | ✅ naissance, taille, **pied fort**, poste détaillé, n° de maillot, **valeur marchande**, nom arabe |
| `player/{id}/transfer-history` | ✅ la carrière entière, club par club, datée |
| `player/{id}/statistics/seasons` | ✅ les compétitions traversées |
| `player/{id}/.../statistics/overall` | ✅ buts, penaltys, cartons — rien d'autre |
| `player/{id}/image` | ✅ la photo (403 en direct, 200 depuis une page du site) |
| `attribute-overviews`, `heatmap`, `ratings`, `last-year-summary` | ❌ 404 ou vide |

**Il n'y aura donc jamais de radar Football Manager ici** : ni note, ni minutes
jouées, ni passes, ni tacles. En fabriquer un à partir des seuls buts serait une
décoration qui ment, et la page le dit explicitement plutôt que de laisser
croire à un oubli.

**Ce que la page a d'unique, c'est nous qui le calculons.** `goal_profiles()`
dérive de nos 195 buts datés et nommés : la répartition par tranche de quinze
minutes, la part de penaltys, les adversaires, le premier et le dernier but.
Aucune source ne publie ça. Exemple réel : Pablo Vinicius (Khaitan) n'a marqué
ses 4 buts **que** dans la dernière demi-heure.

ℹ️ L'appariement chronologie ↔ effectif se fait sur le **nom** : la source ne
met pas d'identifiant de joueur dans ses `incidents`.

### Ce que la collecte a appris sur le collecteur

Trois corrections à `browser.py`, toutes nées de cette passe de 230 joueurs :

- ⚠️ **Un 404 n'était pas mis en cache** : chaque collecte redemandait tous les
  endpoints inexistants. Une sentinelle est désormais écrite, et relue pour
  lever la même erreur sans requête.
- ⚠️ **Un 404 était retenté trois fois**, avec les pauses. Un 404 est définitif :
  on sort immédiatement.
- **`get_bytes()`** : les photos répondent 403 à une requête directe et 200 à un
  `fetch()` exécuté dans une page du site, comme le reste. Les octets
  transitent en base64, un `page.evaluate` ne rendant que du JSON.

Et deux à `fetch_players.py`, pour un lot qui dure des heures :

- **Un `Failed to fetch` passager ne tue plus la collecte** — c'était arrivé
  après 25 joueurs. La classe `Flaky` compte les échecs **consécutifs** et
  n'abandonne qu'au-delà de 15 : sinon on écrirait 230 fiches vides par-dessus
  les bonnes le jour où Cloudflare ferme la porte.
- **L'écriture se fait après chaque club**, pas à la fin.

ℹ️ Les portraits sont des fichiers séparés (`data/photos/<id>.webp`, ~3 Ko
chacun) et non des `data:` URI : 230 dans un JSON feraient plusieurs mégaoctets
à charger pour en afficher un. Les fiches elles-mêmes vivent dans
`data/players.site.json`, chargé **à la demande** — l'accueil n'en a pas besoin.

## Compositions fournies par les clubs (12/08/2026)

**Le premier trou comblé par une source humaine.** Aucun service ne publie de
feuille de match sur cette division — Sofascore répond 404 sur `lineups`, c'est
vérifié et définitif. Mais **les clubs, eux, publient leur onze sur Instagram**.
D'où une voie qui n'existait pas : la donnée entre à la main, avec sa
provenance, et le site la distingue de tout ce qui est collecté.

Le circuit : les visuels sont déposés dans **`data/inbox/<match_id>/`** — un
dossier par rencontre, ignoré par git, ce sont des pièces justificatives et pas
de la donnée. Ils sont lus, appariés à l'effectif Sofascore, puis écrits dans
**`data/lineups.json`**, versionné. `build_site.py` l'attache à la fiche du
match sous la clé `lineups`, et `match.js` en fait une carte **Composition**,
placée avant les effectifs de saison.

Le dossier par rencontre est une idée de Haris, et elle est meilleure qu'une
boîte à plat : une rencontre produit plusieurs visuels (`compo-`, `changements-`,
`buts-`, `fin-`) et deux clubs les publient chacun de leur côté. `LISEZ-MOI.txt`
y est versionné — c'est le mode d'emploi, il doit suivre le dépôt.

### Ce que l'appariement a appris

⚠️ **Le numéro de maillot ne suffit pas** : seuls **152 des 228 joueurs** en ont
un chez Sofascore, et Burgan (9/31) comme Sporty (12/26) sont à peine couverts.
L'appariement se fait donc sur numéro **puis** nom, et chaque joueur porte dans
le JSON **comment** il a été rapproché (`number+name`, `number`, `name`, `none`).

⚠️ **Le club nomme le père, Sofascore la famille.** `Musaed Trad` = `Musaed Al
Enezi` (n°5), `Khaled Eid` = `Khaled Al Rashidi` (n°7). Ce n'est pas une faute
de frappe, c'est une convention de nommage — et elle reviendra à chaque feuille.

⚠️ **`match: "none"` n'est pas une erreur à corriger en devinant.** Mohammed
Ruwaee est sur le banc de Sulaibikhat et n'existe dans aucune des 29 fiches du
club. Il est publié par son nom, sans lien. L'apparier à « Mohammed Safar » ou
« Mohammed Hamdan » sur le seul prénom fabriquerait une information fausse.

ℹ️ **Une erreur du club est conservée telle quelle** : le visuel de Sulaibikhat
annonce « SULAIBIKHAT | BURGAN » alors qu'il s'agit de la rencontre contre
Sporty. La correction est dans `source.note`, la capture n'est pas retouchée.
Recoupement qui a permis de trancher : les quatre joueurs nommés dans la
chronologie du match contre Sporty (Irobiso 26', Damacena 55', Alaaeddine 75' et
83', Saleh Khamees 88') figurent tous sur ce visuel.

ℹ️ **Sofascore se trompe de prénom sur le n°25 de Sulaibikhat** : « Nasser Al
Faylakawi » là où le club écrit « Nawaf ». Arbitré en faveur du club le
12/08/2026. Le site affiche donc ici un nom qui diffère de la source.

### Sporty : ce que révèle une feuille quand la source a vieilli

La deuxième feuille de la même rencontre est bien plus dure que la première, et
c'est elle qui donne la mesure du problème. **Quatre titulaires sur onze
n'existent dans aucune des 26 fiches Sporty de Sofascore** — Ahmed Fahad (n°5),
Sulaiman Al-Ali (40), Omar Almutairi (49), Abdullah Saad (8). Ce n'est pas un
échec d'appariement : c'est un effectif de source périmé, et la feuille du club
est la seule chose qui le prouve.

⚠️ **Un banc en initiale + nom n'est pas appariable.** Sporty publie
« A. Marzouq », « S. Al-Kandari ». Sur douze, aucun n'a été rapproché. Le seul
qui aurait été tentant — « S. Al-Kandari » contre « Musab Al Kandari » — a
l'initiale contre lui. Les douze sont publiés par leur nom, sans lien.

**Deux gains inattendus**, tranchés par Haris le 12/08 :

- ✅ **Le doublon de Sporty est enfin départagé.** « Metab Fahad Al Salamah »
  existait sous deux identifiants (1647399 en n°7, 1629417 sans numéro) et on ne
  savait pas distinguer doublon et homonyme. La feuille lui donne le **brassard**
  en n°7 : la fiche vivante est celle du n°7.
- ✅ **Yousef Tarek Al Madi a changé de numéro** — 98 chez Sofascore, 11 chez le
  club. Le numéro retenu est celui du club.

ℹ️ **Une contradiction assumée** : Sofascore attribue le rouge de la 74e à
Abdullah Al Najdi (n°16), absent du onze *et* du banc publiés. Les deux sources
sont conservées telles quelles. Corriger l'une par l'autre sans élément nouveau
serait un arbitrage au jugé.

### Le terrain (12/08/2026) — ce qu'un dessin a le droit de dire

Le onze n'est plus une liste, c'est un **terrain** (`src/js/components/pitch.js`).
Il montre une chose que personne ne publie et qu'une énumération cache :
**Sulaibikhat a commencé avec cinq défenseurs**, `1-5-2-3`.

⚠️ **Un terrain ressemble à une mesure**, et c'est exactement le risque contre
lequel tout ce composant est écrit. Trois choses n'existent pas dans la donnée
et ne doivent pas être inventées par le dessin :

- **Le rôle du jour.** Le poste vient de la fiche *générale* du joueur chez
  Sofascore. Cinq « défenseurs » peuvent être une défense à trois avec deux
  pistons. La note dit « range par poste », jamais « dispositif ».
- **Le côté.** Rien ne dit qui jouait à gauche. L'ordre horizontal est celui de
  la feuille du club, arbitraire, et la note l'écrit.
- **Le poste des inconnus.** Les quatre Sporty sans fiche ne sont pas placés au
  jugé : ils vont dans une bande en pointillés sous le terrain, « 4 sans poste
  connu ». Sept joueurs placés et quatre à côté a l'air incomplet — ça l'est.

⚠️ **`shapeOf()` rend `null` dès qu'un seul poste manque.** Sporty n'affiche
donc aucune suite de lignes : un « 1-2-2-2 » à sept joueurs serait faux deux
fois, et se lirait quand même comme un dispositif.

ℹ️ **Le raccourcissement des noms a dû être refait.** Garder les deux derniers
mots donnait deux pastilles « Al Enezi » dans le même onze — les noms de famille
se répètent beaucoup ici. La règle retenue : initiale du prénom, puis la partie
qui identifie (à partir du « Al » s'il y en a un, le dernier mot sinon), d'où
« S. Al Enezi » et « M. Al Enezi ».

ℹ️ Trois jetons ajoutés à `tokens.css` (`--pitch-far`, `--pitch-near`,
`--pitch-line`) : la pelouse est un dégradé et les lignes blanches un
`background-image`, aucune n'est un élément du DOM. Elle reste **plus sombre
qu'une carte** — un terrain plus clair volerait la hiérarchie de la page.

### La limite, écrite sur la page

**Ces visuels sont publiés AVANT le coup d'envoi.** Ils donnent le onze et le
banc, **jamais les changements** — donc aucune minute jouée ne peut en être
tirée, et la note de méthode le dit. Si un club publie aussi un visuel de fin de
match, c'est celui-là qui vaut le plus : il débloquerait les minutes, et avec
elles tout ce qui se ramène au temps de jeu.

La carte « Effectifs » change de note quand une composition existe : dire
« aucune source ne publie de feuille de match » sous une feuille affichée se
contredirait.

## ⚠️ Le classement des buteurs était faux (12/08/2026)

**Le site donnait Allan Paulista (11 buts) meilleur buteur de la division. Le
meilleur buteur est Lucas Shallon, 12 buts, Al Sulaibikhat — il n'apparaissait
nulle part.**

### La cause : un classement dérivé

`scorer_board()` ne collectait rien. Il *remettait à plat* les effectifs :
`fetch_squads` accroche à chaque joueur d'un club ses buts de la saison, et le
build parcourait les huit effectifs pour en tirer un classement.

Un classement dérivé d'un effectif ne peut contenir que **les joueurs encore
inscrits**. Celui qui a changé de club en cours de saison n'est plus dans aucun
effectif de la division — donc ni lui ni ses buts n'existaient. Huit joueurs
étaient dans ce cas, **33 buts**, dont le premier et le cinquième de la
division :

| joueur | buts | club |
|---|---|---|
| Lucas Shallon | 12 | Al Sulaibikhat |
| Hazem Haj Hassen | 7 | Yarmouk |
| Michel Potiguar | 5 | Al Sulaibikhat |
| Abdullah Al Shami | 3 | Yarmouk |
| Nando Welter | 3 | Al Jazira |
| Issad Lakdja, Moriba Diarra, Sávio Maciel | 1 chacun | Yarmouk, Yarmouk, Burgan |

⚠️ **C'est le pire genre de faux : crédible.** Rien n'était vide, rien n'était
en erreur, le tableau était plein et bien classé — il lui manquait seulement le
premier. Une donnée absente se voit ; une donnée absente *qui laisse un
classement cohérent derrière elle*, non.

### Le correctif : `fetch_scorers.py`

L'autorité est le classement que publie la compétition elle-même :

    /unique-tournament/20044/season/{sid}/statistics?order=-goals&accumulation=total

Il ne dépend d'aucun effectif : il énumère tous ceux qui ont joué dans la
saison, avec leur club **au moment où ils ont marqué**, et il donne les
penaltys. 79 buteurs, 192 buts, les 8 clubs rapprochés sans orphelin. Trié par
buts décroissants, donc on s'arrête au premier joueur à zéro — une page de 100
suffit largement pour cette division. Ajouté à `daily.py` : une seule requête.

`scorer_board()` ne fait plus que *décorer* ces lignes — poste et nationalité —
avec l'effectif, quand le joueur y est encore.

⚠️ **L'endpoint accepte `fields=assists,appearances,minutesPlayed` et renvoie
ces clés à `null`** sur cette division (vérifié le 12/08). Ne pas se laisser
prendre : il n'y a toujours ni passe décisive, ni match joué, ni minute. Les
deux seuls chiffres réels sont `goals` et `penaltyGoals`. Ne pas re-sonder.

### Ce que la page dit maintenant

⚠️ **Un buteur parti n'a pas de fiche joueur**, et 43 des 79 n'en ont pas du
tout (`fetch_players` n'a été passé que sur une partie des clubs). `id` n'est
donc renseigné **que si la fiche existe** : sans quoi le lien ouvrait une page
vide. Le tableau du classement rend alors un `<span>` au lieu d'un `<a>`, et
`scorerCard` retombait déjà sur le club.

La note de méthode l'écrit en deux temps — d'abord que le classement est celui
de la compétition et non la somme des effectifs, ensuite qu'un nom sans lien est
un joueur sans fiche. Elle ne dit pas « joueur parti » devant chaque nom non
cliquable : ce serait faux pour les 35 autres.

## Reste à faire

Les trois points de la session du 06/08 sont soldés : `build_json.py`,
`requirements.txt` et `README.md` sont écrits, et l'horizon du calendrier est
réglé par Flashscore (20 rencontres sur 5 journées, contre 2 jours chez
Forebet) — inutile de chercher une page `fixtures` chez Forebet.

Ce qui reste ouvert, par ordre d'intérêt :

1. ~~Trancher si les stats se remplissent pendant le match~~ — **tranché le
   10/08 : oui**, voir la section « Direct et statistiques par match ».
2. ~~Effectifs~~ — **fait le 10/08**, voir plus haut. 230 joueurs, 8 clubs.
3. ~~Trancher qui reçoit~~ — **tranché le 11/08 : Flashscore fait autorité**,
   voir la section dédiée. Reste, en beaucoup plus petit, deux choses que
   l'arbitrage ne couvre pas : les bilans domicile/extérieur calculés par
   Forebet, et le fait qu'une rencontre inconnue de Flashscore garde
   l'étiquette Forebet faute d'arbitre.
4. ~~Le classement des buteurs est faux~~ — **corrigé le 12/08** par
   `fetch_scorers.py`, voir la section dédiée. Reste, en plus petit : les 43
   buteurs sans fiche joueur, que seul un passage complet de `fetch_players.py`
   comblerait.
5. **Le flux SSE `/glvs/`** reste débranché. Il apporterait ce que le mode
   direct ne peut pas montrer : la **minute de jeu** et le temps additionnel,
   absents de `gmc=1`. À faire consommer par `serve.py`, comme le collecteur —
   pas par la page, qui n'a pas accès à Forebet.
6. **Diffuseurs** : `data/broadcasts.json` a quatre cases vides.
   Sofascore ne les a pas non plus (`odds` et `tv` : 404, vérifié le 11/08).
7. **`shoot.py` n'est documenté nulle part ici.** L'outil (captures d'écran
   d'une page web, nettoyage des bandeaux, `--login`) a été écrit le 10/08 en
   9 commits et n'a pas de section dans ce fichier. Il est autonome et sans
   rapport avec la collecte, mais l'absence de trace est un trou de suivi.
