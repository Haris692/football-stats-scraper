"""Les joueurs, un par un : identité, valeur, carrière, photo.

⚠️ **Ceci corrige une conclusion trop large du projet.** `kuwait-football` puis
ce dépôt avaient conclu qu'« aucune statistique individuelle n'existe sur cette
division ». C'est vrai des statistiques **de match** par joueur — ni note, ni
minutes, ni passes, ni tacles, ni heatmap : tous ces endpoints répondent 404,
vérifié le 11/08/2026 et à ne pas re-sonder. Mais les endpoints **de profil**,
eux, répondent, et ils sont riches :

| endpoint | ce qu'il donne |
|---|---|
| `player/{id}` | naissance, taille, pied fort, poste détaillé, n° de maillot, **valeur marchande**, nom arabe |
| `player/{id}/transfer-history` | la carrière, club par club, datée |
| `player/{id}/statistics/seasons` | les compétitions où le joueur a des stats |
| `player/{id}/.../statistics/overall` | buts, penaltys, cartons — et rien d'autre |
| `player/{id}/image` | la photo (403 en direct, 200 depuis une page du site) |

Ce que la page joueur montre en plus, **c'est nous qui le calculons** : à partir
des 195 buts datés et nommés de `data/events.json`, on dérive la répartition par
tranche de minutes, la part de penaltys, les adversaires, domicile/extérieur.
Aucune source ne publie ça.

    python fetch_players.py --summary
    python fetch_players.py --club khaitan --force
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from browser import CdpBrowser
from fetch_squads import BASE, HOST_PAGE, TOURNAMENT, season_id, load as load_squads

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "players.json"
PHOTOS = ROOT / "data" / "photos"

# Un profil ne bouge presque jamais : on le garde un mois. C'est ce qui rend la
# collecte quotidienne quasi gratuite une fois la première passe faite.
AGE_PROFILE = 24 * 30
PHOTO_PX = 160


class Flaky:
    """Compteur d'échecs consécutifs, pour distinguer l'aléa de la panne.

    Une collecte de 230 joueurs dure des heures et fait des centaines de
    requêtes : il y aura des `Failed to fetch`. En laisser un seul interrompre
    tout le lot est absurde — on perd deux cents fiches pour un hoquet réseau,
    ce qui est arrivé le 11/08/2026.

    Mais tout avaler serait pire : si Cloudflare nous ferme la porte, on
    écrirait 230 fiches vides par-dessus les bonnes. D'où le seuil : au-delà de
    `limit` échecs **d'affilée**, ce n'est plus un aléa, on s'arrête.
    """

    def __init__(self, limit: int = 15):
        self.limit = limit
        self.streak = 0
        self.total = 0

    def ok(self) -> None:
        self.streak = 0

    def failed(self, url: str, exc: Exception) -> None:
        self.streak += 1
        self.total += 1
        print(f"    ignoré ({exc}) {url.rsplit('/', 2)[-2:]}", file=sys.stderr)
        if self.streak >= self.limit:
            raise RuntimeError(
                f"{self.streak} échecs d'affilée — la source ne répond plus, "
                f"on s'arrête plutôt que d'écrire des fiches vides") from exc


FLAKY = Flaky()


def _maybe(browser: CdpBrowser, url: str, **kwargs):
    """Un GET dont l'absence est une réponse : tous les joueurs n'ont pas tout."""
    try:
        data = browser.get_json(url, **kwargs)
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            FLAKY.ok()      # une absence est une réponse, pas une panne
            return None
        FLAKY.failed(url, exc)
        return None
    FLAKY.ok()
    return data


def age_of(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        born = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    return now.year - born.year - ((now.month, now.day) < (born.month, born.day))


def profile(browser: CdpBrowser, pid: int, force: bool) -> dict | None:
    data = _maybe(browser, f"{BASE}/api/v1/player/{pid}", force=force,
                  referer=HOST_PAGE, max_age_hours=AGE_PROFILE)
    p = (data or {}).get("player")
    if not p:
        return None
    value = p.get("proposedMarketValueRaw") or {}
    return {
        "id": pid,
        "name": p.get("name"),
        "short_name": p.get("shortName"),
        "name_ar": ((p.get("fieldTranslations") or {})
                    .get("nameTranslation", {}).get("ar")),
        "position": p.get("position"),
        # `positionsDetailed` est le poste réellement occupé (« ST », « DM »),
        # bien plus parlant que la ligne (« F », « M »).
        "positions": p.get("positionsDetailed") or [],
        "number": p.get("shirtNumber") or p.get("jerseyNumber"),
        "birth": p.get("dateOfBirth"),
        "age": age_of(p.get("dateOfBirth")),
        "height": p.get("height"),
        "foot": p.get("preferredFoot"),
        "country": (p.get("country") or {}).get("name"),
        "country_code": (p.get("country") or {}).get("alpha2"),
        "market_value": value.get("value"),
        "market_currency": value.get("currency"),
        "retired": p.get("retired"),
    }


def career(browser: CdpBrowser, pid: int, force: bool) -> list[dict]:
    """La carrière, du plus récent au plus ancien."""
    data = _maybe(browser, f"{BASE}/api/v1/player/{pid}/transfer-history",
                  force=force, referer=HOST_PAGE, max_age_hours=AGE_PROFILE)
    out = []
    for row in (data or {}).get("transferHistory") or []:
        when = row.get("transferDateTimestamp")
        out.append({
            "date": datetime.fromtimestamp(when).strftime("%d/%m/%Y") if when else None,
            "iso": datetime.fromtimestamp(when).isoformat()[:10] if when else None,
            "from": (row.get("transferFrom") or {}).get("name"),
            "to": (row.get("transferTo") or {}).get("name"),
            # « Free », « Unknown », un montant… La source n'est pas normalisée ;
            # on la recopie telle quelle plutôt que d'inventer une catégorie.
            "fee": row.get("transferFeeDescription"),
        })
    out.sort(key=lambda r: r["iso"] or "", reverse=True)
    return out


def competitions(browser: CdpBrowser, pid: int, force: bool) -> list[dict]:
    """Où ce joueur a déjà joué, saison par saison.

    C'est ce qui donne sa profondeur à la fiche : un attaquant de cette division
    a souvent un parcours en Inde, en Chine ou au Brésil, et personne ne
    l'écrit nulle part.
    """
    data = _maybe(browser, f"{BASE}/api/v1/player/{pid}/statistics/seasons",
                  force=force, referer=HOST_PAGE, max_age_hours=AGE_PROFILE)
    out = []
    for row in (data or {}).get("uniqueTournamentSeasons") or []:
        comp = row.get("uniqueTournament") or {}
        for season in row.get("seasons") or []:
            out.append({
                "competition": comp.get("name"),
                "country": ((comp.get("category") or {}).get("country") or {}).get("name"),
                "year": season.get("year"),
            })
    return out


def photo(browser: CdpBrowser, pid: int, force: bool) -> bool:
    """La photo, réduite et recompressée. Renvoie True si elle existe.

    ⚠️ 403 à une requête directe, 200 depuis une page du site : elle passe donc
    par `browser.get_bytes()`, comme tout le reste. Réduite à 160 px et servie
    en fichier séparé plutôt qu'en `data:` URI — 230 portraits dans un JSON
    feraient plusieurs mégaoctets à charger pour en afficher un.
    """
    target = PHOTOS / f"{pid}.webp"
    if target.exists() and not force:
        return True
    try:
        raw = browser.get_bytes(f"{BASE}/api/v1/player/{pid}/image", force=force,
                                referer=HOST_PAGE, max_age_hours=AGE_PROFILE)
    except RuntimeError as exc:
        FLAKY.failed(f"image/{pid}", exc)
        return False
    if not raw:
        return False
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail((PHOTO_PX, PHOTO_PX), Image.LANCZOS)
        PHOTOS.mkdir(parents=True, exist_ok=True)
        img.save(target, "WEBP", quality=82, method=6)
        return True
    except Exception as exc:
        print(f"    photo {pid} illisible ({exc})", file=sys.stderr)
        return False


def collect(force: bool = False, only_club: str | None = None,
            with_photos: bool = True) -> dict:
    squads = load_squads().get("teams") or {}
    if only_club:
        squads = {k: v for k, v in squads.items() if k == only_club}
        if not squads:
            raise SystemExit(f"club inconnu : {only_club}")

    out, shot = {}, 0
    with CdpBrowser() as browser:
        sid, year = season_id(browser, force)
        print(f"saison {year} (id {sid})")
        for club_key, club in squads.items():
            players = club.get("players") or []
            print(f"  · {club.get('sofascore_name') or club_key} "
                  f"({len(players)} joueurs)")
            for entry in players:
                pid = entry.get("id")
                if not pid:
                    continue
                card = profile(browser, pid, force)
                if not card:
                    continue
                card["club"] = club_key
                card["goals_season"] = entry.get("goals") or 0
                card["career"] = career(browser, pid, force)
                card["competitions"] = competitions(browser, pid, force)
                if with_photos:
                    card["photo"] = photo(browser, pid, force)
                    shot += bool(card["photo"])
                out[str(pid)] = card
            # On écrit après chaque club : deux heures de collecte ne doivent
            # pas tenir à ce que le script aille jusqu'au bout.
            _save({"generated": datetime.now().isoformat(timespec="seconds"),
                   "source": "sofascore", "players": out})

    valued = [p for p in out.values() if p.get("market_value")]
    print(f"\n{len(out)} joueur(s) · {shot} photo(s) · "
          f"{len(valued)} avec une valeur marchande")
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": "sofascore",
        "players": out,
    }


def _save(store: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                      encoding="utf-8")


def load() -> dict:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"players": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fiches joueurs Sofascore.")
    parser.add_argument("--force", action="store_true", help="ignorer le cache")
    parser.add_argument("--club", help="ne collecter qu'un club (clé)")
    parser.add_argument("--no-photos", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    store = collect(args.force, args.club, not args.no_photos)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(store, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"écrit : {OUTPUT}  ({OUTPUT.stat().st_size // 1024} Ko)")

    if args.summary:
        rows = sorted(store["players"].values(),
                      key=lambda p: -(p.get("market_value") or 0))
        for p in rows[:20]:
            value = (f"{p['market_value']:,} {p['market_currency']}".replace(",", " ")
                     if p.get("market_value") else "—")
            print(f"  {p['name'][:24]:24} {str(p.get('age') or '?'):>3} ans  "
                  f"{(p.get('positions') or [p.get('position') or '?'])[0]:>3}  "
                  f"{value:>16}  {len(p.get('career') or [])} transfert(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
