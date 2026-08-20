// Page assembly. Loads one JSON bundle, renders everything, makes no other
// network request — the model runs here, in the reader's browser.
import { initialLanguage, rememberLanguage, translator, STRINGS } from "./i18n.js";
import { selfCheck, predictLadder, shippedThresholds } from "./model.js";
import { divergingBars, reliabilityChart, cityStrip, probabilityMeter } from "./charts.js";

let bundle = null;
let lang = initialLanguage();
let t = translator(lang);

const $ = (id) => document.getElementById(id);
const pct = (v) => `${Math.round(v * 100)}%`;

async function main() {
  const response = await fetch("data/bundle.json");
  if (!response.ok) throw new Error(`bundle.json: HTTP ${response.status}`);
  bundle = await response.json();

  $("lang-toggle").addEventListener("click", () => {
    lang = lang === "it" ? "en" : "it";
    rememberLanguage(lang);
    t = translator(lang);
    document.documentElement.lang = lang;
    render();
  });

  document.documentElement.lang = lang;
  render();
}

function render() {
  renderStatic();
  renderLive();
  renderRecord();
  renderBaselines();
  renderCut();
  renderReliability();
  renderStationarity();
  renderPhysics();
  renderLimits();
  renderSelfCheck();
}

function renderStatic() {
  $("lang-toggle").textContent = t("lang.other");
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.innerHTML = t(node.dataset.i18n);
  }
}

// --------------------------------------------------------------------------
// Tomorrow
// --------------------------------------------------------------------------
// Every forecast still awaiting its outcome, grouped by the day it is about.
// There are normally two: today's, issued last night, and tomorrow's, issued
// this evening. Both stay on the page — today's is the one you can act on,
// tomorrow's is the one that is still a prediction.
function pendingByDay() {
  const groups = new Map();
  for (const record of bundle.ledger) {
    if (record.observed_rain !== null) continue;
    if (!groups.has(record.target_date)) groups.set(record.target_date, []);
    groups.get(record.target_date).push(record);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function renderLive() {
  const box = $("live-body");
  box.innerHTML = "";
  const groups = pendingByDay();

  if (!groups.length) {
    box.innerHTML = `<p class="muted">${t("live.empty")}</p>`;
    $("live-updated").textContent = "";
    return;
  }

  const byKey = Object.fromEntries(bundle.cities.map((c) => [c.key, c]));
  for (const [target, rows] of groups) {
    const block = document.createElement("div");
    block.className = "day-block";
    const when = relativeDay(target);
    block.innerHTML =
      `<h3 class="day-heading ${when}">${t(`live.heading.${when}`)}` +
      `<span class="subtle"> ${formatDate(target)}</span></h3>`;

    const list = document.createElement("div");
    list.className = "city-list";
    for (const city of bundle.cities) {
      const record = rows.find((r) => r.city === city.key);
      if (!record) continue;
      const card = document.createElement("article");
      card.className = "city-card";
      card.innerHTML = `
        <h4>${byKey[record.city].name}</h4>
        <div class="city-prob"><strong>${pct(record.our_prob)}</strong>
          <span class="muted">${t("live.threshold")}</span></div>
        <p class="vs-normal">${versusNormal(record, target)}</p>
        <div class="city-meter"></div>
        <div class="ladder"></div>
        <p class="muted small om-line">${t("live.openmeteo")}
          ${record.om_precip_mm === null ? "—" : `${record.om_precip_mm.toFixed(1)} mm`}</p>`;
      card.querySelector(".city-meter")
        .appendChild(probabilityMeter(record.our_prob, record.climatology));
      card.querySelector(".ladder").innerHTML = ladderRows(city, record);
      list.appendChild(card);
    }
    block.appendChild(list);
    box.appendChild(block);
  }

  const newest = groups.at(-1)[1][0];
  $("live-updated").textContent = `${t("live.issued")} ${formatDateTime(newest.issued_at)}`;

  // A schedule that stops is invisible unless the page says so.
  const ageDays = (Date.now() - Date.parse(newest.issued_at)) / 86400000;
  $("live-stale").hidden = ageDays <= 2;
  $("live-stale").textContent = t("live.stale");
}

// --------------------------------------------------------------------------
// The public record
// --------------------------------------------------------------------------
function renderRecord() {
  const verified = bundle.ledger.filter((r) => r.observed_rain !== null);
  const box = $("record-body");
  box.innerHTML = "";

  if (!verified.length) {
    box.innerHTML = `<p class="note">${t("record.waiting")}</p>`;
    $("record-stats").innerHTML = statTiles([
      [t("record.issued"), String(bundle.ledger.length)],
      [t("record.verified"), "0"]
    ]);
    return;
  }

  const outcomes = verified.map((r) => (r.observed_rain ? 1 : 0));
  const ours = verified.map((r) => r.our_prob);
  const clim = verified.map((r) => r.climatology);
  const correct = verified.filter((r) => r.our_rain === r.observed_rain).length;
  const brier = mean(ours.map((p, i) => (p - outcomes[i]) ** 2));
  const brierClim = mean(clim.map((p, i) => (p - outcomes[i]) ** 2));
  const bss = brierClim > 0 ? 1 - brier / brierClim : null;
  const dryRate = 1 - mean(outcomes);

  $("record-stats").innerHTML = statTiles([
    [t("record.issued"), String(bundle.ledger.length)],
    [t("record.verified"), String(verified.length)],
    [t("record.correct"), String(correct)],
    [t("record.wrong"), String(verified.length - correct)],
    [t("record.brier"), brier.toFixed(3)],
    [t("record.bss"), bss === null ? "—" : signed(bss)]
  ]);

  box.innerHTML =
    `<p class="note">${t("record.accuracyTrap", { pct: pct(dryRate) })}</p>` +
    (verified.length < 30
      ? `<p class="warning">${t("record.thin", { n: verified.length })}</p>`
      : "");
}

// A probability only means something next to the rate it is being compared with.
// "45%" reads as "probably not"; "45%, one and a half times the August normal"
// reads as what it is.
function versusNormal(record, target) {
  const month = new Date(`${target}T12:00:00Z`).toLocaleDateString(
    lang === "it" ? "it-IT" : "en-GB", { month: "long" }
  );
  const clim = pct(record.climatology);
  const ratio = record.our_prob / record.climatology;
  if (ratio > 0.85 && ratio < 1.15) return t("live.atNormal", { month, clim });
  return t("live.vsNormal", { ratio: ratio.toFixed(1).replace(".", lang === "it" ? "," : "."),
                              month, clim });
}

// The intensity ladder. Rows issued before the thresholds existed carry only the
// headline figure, and are left showing just that rather than being hidden.
function ladderRows(city, record) {
  if (!record.our_probs) return "";
  const shipped = shippedThresholds(city);
  const rows = shipped.map((mm) => {
    const p = record.our_probs[String(mm)];
    if (p === undefined) return "";
    return `<div class="rung">
        <span class="rung-label">${t("live.atLeast")} ${mm} mm</span>
        <span class="rung-bar"><i style="width:${Math.max(2, p * 100)}%"></i></span>
        <span class="rung-value">${pct(p)}</span>
      </div>`;
  });
  return `<div class="ladder-head">${t("live.ladder")}</div>${rows.join("")}`;
}

function statTiles(pairs) {
  return pairs
    .map(([label, value]) => `<div class="tile"><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
}

// --------------------------------------------------------------------------
// Baselines
// --------------------------------------------------------------------------
function renderBaselines() {
  const city = bundle.cities[0];
  const primary = city.thresholds[String(shippedThresholds(city)[0])];
  const items = primary.test_comparison.map((row) => ({
    label: t(`baseline.${row.name}`),
    value: row.bss,
    highlight: row.name === "logistic regression"
  }));
  const box = $("baseline-chart");
  box.innerHTML = "";
  box.appendChild(divergingBars(items, { format: signed }));
  $("baseline-where").textContent = city.name;
}

// --------------------------------------------------------------------------
// Reliability
// --------------------------------------------------------------------------
function renderCut() {
  const city = bundle.cities[0];
  const primary = city.thresholds[String(shippedThresholds(city)[0])];
  const sweep = primary.threshold_sweep || [];
  $("cut-table").innerHTML =
    `<thead><tr><th>${t("cut.threshold")}</th><th>${t("cut.pod")}</th>` +
    `<th>${t("cut.far")}</th><th>${t("cut.csi")}</th></tr></thead><tbody>` +
    sweep.map((row) => {
      const best = row.CSI === Math.max(...sweep.map((x) => x.CSI));
      return `<tr class="${best ? "best" : ""}${row.threshold === 0.5 ? " default" : ""}">
        <th scope="row">${pct(row.threshold)}</th>
        <td>${pct(row.POD)}</td><td>${pct(row.FAR)}</td><td>${row.CSI.toFixed(3)}</td></tr>`;
    }).join("") + "</tbody>";
}

function renderReliability() {
  const city = bundle.cities[0];
  const primary = city.thresholds[String(shippedThresholds(city)[0])];
  const box = $("reliability-chart");
  box.innerHTML = "";
  box.appendChild(
    reliabilityChart(primary.reliability, {
      predicted: t("reliability.predicted"),
      observed: t("reliability.observed"),
      samples: t("reliability.samples"),
      perfect: t("reliability.perfect")
    })
  );
}

// --------------------------------------------------------------------------
// Stationarity
// --------------------------------------------------------------------------
function renderStationarity() {
  if (!bundle.stationarity.length) return;
  const rows = bundle.stationarity
    .map((s) => {
      const change = s.wet_fraction_late - s.wet_fraction_full;
      return `<tr>
        <th scope="row">${s.name}</th>
        <td>${pct(s.wet_fraction_full)}</td>
        <td>${pct(s.wet_fraction_late)}</td>
        <td class="${change < -0.03 ? "drop" : ""}">${signedPct(change)}</td>
      </tr>`;
    })
    .join("");
  $("stationarity-table").innerHTML = `
    <thead><tr><th></th><th>${t("stationarity.full")}</th>
      <th>${t("stationarity.recent")}</th><th>${t("stationarity.change")}</th></tr></thead>
    <tbody>${rows}</tbody>`;

  const thresholds = bundle.stationarity[0].decomposition.map((d) => d.threshold_mm);
  const head = bundle.stationarity.map((s) => `<th>${s.name.split(" ")[0]}</th>`).join("");
  const body = thresholds
    .map((threshold, i) => {
      const cells = bundle.stationarity
        .map((s) => {
          const change = s.decomposition[i].relative_change;
          const cls = change === null ? "" : change < -0.05 ? "drop" : change > 0.02 ? "rise" : "";
          return `<td class="${cls}">${change === null ? "—" : signedPct(change)}</td>`;
        })
        .join("");
      return `<tr><th scope="row">${t("stationarity.threshold")} ${threshold} mm</th>${cells}</tr>`;
    })
    .join("");
  $("decomposition-table").innerHTML =
    `<thead><tr><th></th>${head}</tr></thead><tbody>${body}</tbody>`;
}

// --------------------------------------------------------------------------
// Coefficients
// --------------------------------------------------------------------------
function renderPhysics() {
  const first = bundle.cities[0];
  const features = first.feature_names;
  const coefOf = (c) => c.thresholds[String(shippedThresholds(c)[0])].coefficients;
  const max = Math.max(...bundle.cities.flatMap((c) => coefOf(c).map(Math.abs)));
  const order = features
    .map((name, i) => ({ name, weight: Math.abs(coefOf(first)[i]), i }))
    .sort((a, b) => b.weight - a.weight);

  const head = bundle.cities.map((c) => `<th>${c.name.split(" ")[0]}</th>`).join("");
  const table = $("physics-table");
  table.innerHTML = `<thead><tr><th>${t("physics.feature")}</th>${head}<th></th></tr></thead>`;
  const tbody = document.createElement("tbody");

  for (const { name, i } of order) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<th scope="row"><code>${name}</code></th>` +
      bundle.cities
        .map((c) => `<td class="${coefOf(c)[i] < 0 ? "neg" : "pos"}">` +
          `${signed(coefOf(c)[i], 2)}</td>`)
        .join("") +
      `<td class="strip-cell"></td>`;
    tr.querySelector(".strip-cell")
      .appendChild(cityStrip(bundle.cities.map((c) => coefOf(c)[i]), max));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

// --------------------------------------------------------------------------
// Limits and self-check
// --------------------------------------------------------------------------
function renderLimits() {
  $("limits-list").innerHTML = STRINGS[lang]["limits.list"]
    .map((item) => `<li>${item}</li>`)
    .join("");
}

function renderSelfCheck() {
  const box = $("self-check");
  box.textContent = t("check.running");
  const result = selfCheck(bundle.cities);
  box.className = result.ok ? "self-check ok" : "self-check fail";
  box.textContent = result.ok
    ? t("check.ok", { n: result.coefficients, v: result.cases, m: result.models })
    : t("check.fail", { err: result.error });
}

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------
function mean(values) {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function signed(value, digits = 3) {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}`;
}

function signedPct(value) {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value * 100).toFixed(1)}`;
}

// "today" / "tomorrow" / "past", relative to the reader's own date.
function relativeDay(iso) {
  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  const days = Math.round((new Date(`${iso}T00:00:00`) - midnight) / 86400000);
  if (days <= -1) return "past";
  return days === 0 ? "today" : "tomorrow";
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleString(lang === "it" ? "it-IT" : "en-GB", {
    day: "numeric", month: "long", hour: "2-digit", minute: "2-digit"
  });
}

function formatDate(iso) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString(lang === "it" ? "it-IT" : "en-GB", {
    weekday: "long", day: "numeric", month: "long"
  });
}

main().catch((error) => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<p class="warning load-error">Could not load the page data: ${error.message}</p>`
  );
});
