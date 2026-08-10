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

### Ce qui reste à vérifier

Les stats de `gmc=1` sont-elles remplies **pendant** le match, ou seulement à la
fin ? Toujours non tranché au 10/08. **Le test décisif est un match koweïtien en
cours** : lancer `python fetch_stats.py <mid> --force --summary` une vingtaine de
minutes après un coup d'envoi et regarder si possession et tirs sont déjà non
nuls. Rien à coder pour ça — l'outil est là, il manque juste le bon créneau.

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

#### ⚠️ Forebet et Sofascore inversent domicile et extérieur — systématiquement

Sur les **4 rencontres communes**, les deux sources désignent l'hôte à
l'opposé l'une de l'autre. Ce n'est pas un accident isolé :

| date | Sofascore | Forebet |
|---|---|---|
| 02/08 18:00 | Yarmouk **3-0** Al-Shamiya | Al-Shamiya **0-3** Yarmouk |
| 02/08 19:45 | Sulaibikhat **1-0** Khaitan | Khaitan **0-1** Sulaibikhat |
| 07/08 19:45 | Khaitan **0-0** Yarmouk | Yarmouk **0-0** Khaitan |
| 07/08 19:45 | Sulaibikhat **0-0** Burgan | Burgan **0-0** Sulaibikhat |

Les deux s'accordent sur le **résultat** et sur les **chiffres par équipe**
(Yarmouk 66 % / 9 corners / 1 jaune des deux côtés) : le désaccord porte
uniquement sur l'étiquette. Ils divergent aussi sur le **stade** du même match
(« Jaber Al-Mubarak Stadium » contre « Al Shabab Mubarak Alaiar Stadium »).

**Non tranché — il faudrait un arbitre extérieur** (fédération koweïtienne). Ne
pas choisir au hasard : la console écrit « reçoit », calcule des bilans « à
domicile » et « à l'extérieur », et le brief Instagram titre « LES HÔTES » et
« LES VISITEURS ». Si Forebet a tort, ces quatre éléments sont faux.

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

## Reste à faire

Les trois points de la session du 06/08 sont soldés : `build_json.py`,
`requirements.txt` et `README.md` sont écrits, et l'horizon du calendrier est
réglé par Flashscore (20 rencontres sur 5 journées, contre 2 jours chez
Forebet) — inutile de chercher une page `fixtures` chez Forebet.

Ce qui reste ouvert, par ordre d'intérêt :

1. **Trancher si les stats se remplissent pendant le match** (voir plus haut) :
   c'est la seule inconnue qui change ce que la console peut afficher en direct.
2. **Le direct par Server-Sent Events** (`/glvs/`) n'est pas branché : score et
   minute poussés en temps réel, sans polling. N'a de sens que dans une page qui
   reste ouverte — la console est un fichier statique, donc à décider.
3. ~~Effectifs~~ — **fait le 10/08**, voir plus haut. 230 joueurs, 8 clubs.
5. ⚠️ **Trancher qui reçoit.** Forebet et Sofascore s'opposent sur les
   4 rencontres communes. Tant que ce n'est pas arbitré, « reçoit », les bilans
   domicile/extérieur et les slides « LES HÔTES / LES VISITEURS » reposent sur
   une donnée contestée.
4. **Diffuseurs** : `data/broadcasts.json` a quatre cases vides.
