/* Le calendrier : toutes les rencontres, groupées par jour, filtrables.

   Deux sources cohabitent ici, et la page le dit :
   - `fixtures` — la fenêtre arbitrée (Forebet + Flashscore), avec un hôte sur
     lequel deux sources s'accordent et une fiche détaillée quand elle existe ;
   - `season_events` — la saison entière vue par Sofascore, qui remonte à
     septembre, mais **réorientée contre Flashscore côté build** : Sofascore
     inverse domicile et extérieur sur 61 rencontres sur 70. Les rares qui
     échappent à l'arbitrage sortent marquées, et portent alors un « ? ». */

import { el, append } from "../core/dom.js";
import { t } from "../core/i18n.js";
import { boot } from "../core/shell.js";
import { site, fixtures, teams, nameOf } from "../core/data.js";
import { crestOf, badge, methodNote } from "../components/pieces.js";

const state = { team: "", scope: "all" };

/** Les rencontres arbitrées d'abord, puis celles que seule Sofascore connaît.
 *  Les secondes sont marquées : leur hôte n'est pas arbitré. */
function allRows() {
  const known = new Set(fixtures().map(f => (f.kickoff_iso || "").slice(0, 16) +
    [f.home_key, f.away_key].sort().join("|")));

  const rows = fixtures().map(f => ({
    iso: f.kickoff_iso, kickoff: f.kickoff, round: f.round,
    home: f.home_key, away: f.away_key, score: f.score,
    played: f.played, live: f.live, id: f.match_id, arbitrated: true,
  }));

  for (const e of site().season_events || []) {
    const sig = (e.kickoff_iso || "").slice(0, 16) +
      [e.home, e.away].sort().join("|");
    if (known.has(sig)) continue;
    rows.push({
      iso: e.kickoff_iso, kickoff: e.kickoff, round: e.round,
      home: e.home, away: e.away,
      score: e.finished ? `${e.home_score} - ${e.away_score}` : null,
      played: e.finished, id: null, arbitrated: e.arbitrated,
    });
  }
  rows.sort((a, b) => (a.iso || "").localeCompare(b.iso || ""));
  return rows;
}

function visible(rows) {
  return rows.filter(r => {
    if (state.team && r.home !== state.team && r.away !== state.team) return false;
    if (state.scope === "played" && !r.played) return false;
    if (state.scope === "upcoming" && r.played) return false;
    return true;
  });
}

function row(r) {
  const inner = el("div", { class: "row-fx" }, [
    el("span", { class: "row-fx__t",
                 text: (r.kickoff || "").split(" ")[1] || "" }),
    el("span", { class: "row-fx__m" }, [
      crestOf(r.home, "sm"),
      el("span", { class: "truncate", text: nameOf(r.home) }),
      el("span", { class: "muted", text: "—" }),
      crestOf(r.away, "sm"),
      el("span", { class: "truncate", text: nameOf(r.away) }),
      r.round ? badge("J" + r.round) : null,
      r.live ? badge("LIVE", "live") : null,
      // Sans arbitrage, on ne prétend pas savoir qui reçoit.
      !r.arbitrated ? badge("?", "solid") : null,
    ]),
    el("span", { class: "row-fx__s", text: r.score || "" }),
  ]);
  return r.id
    ? el("a", { href: `match.html?id=${r.id}`, style: { display: "block" } }, [inner])
    : inner;
}

function list(rows) {
  const out = [];
  let day = null;
  for (const r of rows) {
    const d = (r.kickoff || "").split(" ")[0];
    if (d !== day) {
      day = d;
      out.push(el("div", { class: "day", id: (r.iso || "").slice(0, 10) }, [
        el("div", { class: "day__h" }, [
          el("span", { text: d || "—" }),
          d === site().today ? badge(t("Aujourd'hui") || "Aujourd'hui", "flood") : null,
        ]),
      ]));
    }
    out[out.length - 1].append(row(r));
  }
  return out;
}

boot(async host => {
  document.title = `${t("Calendrier")} — ${t("Division 1 koweïtienne")}`;
  const rows = allRows();

  const holder = el("div", {});
  const draw = () => {
    holder.replaceChildren();
    const shown = visible(rows);
    append(holder, shown.length ? list(shown) : el("div", { class: "empty" }, [
      el("h3", { text: t("Rien à afficher") }),
    ]));
    // Un lien profond vers un jour doit atterrir sur ce jour.
    if (location.hash) {
      const target = document.getElementById(location.hash.slice(1));
      if (target) target.scrollIntoView({ block: "start" });
    }
  };

  const teamSelect = el("select", {
    class: "btn", "aria-label": t("Équipe"),
    onChange: e => { state.team = e.target.value; draw(); },
  }, [
    el("option", { value: "", text: t("Clubs") }),
    ...teams().map(c => el("option", { value: c.key, text: c.name })),
  ]);

  const scopeSelect = el("select", {
    class: "btn", "aria-label": t("Rencontres"),
    onChange: e => { state.scope = e.target.value; draw(); },
  }, [
    el("option", { value: "all", text: t("Calendrier") }),
    el("option", { value: "played", text: t("Résultats") }),
    el("option", { value: "upcoming", text: t("À venir") }),
  ]);

  append(host, [
    el("section", { class: "page section" }, [
      el("div", { class: "eyebrow", text: t("Division 1 koweïtienne") }),
      el("h1", { text: t("Calendrier"), style: { marginBlock: "var(--s-2) var(--s-4)" } }),
      methodNote(t("La saison entière vient de Sofascore ; la fenêtre récente " +
        "est complétée par Forebet et Flashscore, qui apportent la fiche " +
        "détaillée. Les rencontres marquées « ? » n'ont pas d'hôte arbitré : " +
        "les sources se contredisent sur qui reçoit, et on ne tranche pas " +
        "sans une deuxième qui confirme.")),
      el("div", { class: "filters", style: { marginTop: "var(--s-4)" } },
        [teamSelect, scopeSelect]),
      holder,
    ]),
  ]);
  draw();
});
