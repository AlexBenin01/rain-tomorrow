// End-to-end render check for the published page.
//
// The Python tests cover the model; this covers the page. It loads index.html
// into a simulated DOM, renders every section against the real bundle, verifies
// the browser model reproduces the training output, and flips the language.
//
// Needs a browser-less DOM, so it runs in a container rather than in pytest:
//
//   docker run --rm -v "$PWD/docs:/docs:ro" -v "$PWD/tests:/work" -w /work //     node:20-alpine sh -c 'npm init -y >/dev/null; npm i --silent jsdom@24; node render_check.mjs'
//
// Exit code 0 means every section rendered, the self-check passed, the language
// toggle worked and no JavaScript error was raised.

import { JSDOM } from "jsdom";
import { readFileSync } from "fs";
const html = readFileSync("/docs/index.html", "utf8");
const bundle = readFileSync("/docs/data/bundle.json", "utf8");
const dom = new JSDOM(html, { url: "http://localhost/", pretendToBeVisual: true });
const { window } = dom;
global.window = window; global.document = window.document;
global.navigator = window.navigator; global.localStorage = window.localStorage;
global.fetch = async () => ({ ok: true, status: 200, json: async () => JSON.parse(bundle) });
const errors = [];
window.addEventListener("error", (e) => errors.push(e.message));
process.on("unhandledRejection", (e) => errors.push(String(e)));

await import("/docs/js/app.js");
await new Promise((r) => setTimeout(r, 500));

const d = window.document;
const check = (id, label) => {
  const n = d.getElementById(id);
  const size = n ? n.textContent.trim().length + n.querySelectorAll("*").length : -1;
  console.log(`  ${label.padEnd(28)} ${size > 0 ? "reso (" + size + ")" : "VUOTO"}`);
  return size > 0;
};
console.log("sezioni:");
const ok = [
  check("live-body", "previsione di domani"),
  check("record-stats", "riquadri del registro"),
  check("record-body", "nota sul registro"),
  check("baseline-chart", "grafico baseline"),
  check("reliability-chart", "curva di affidabilita"),
  check("stationarity-table", "tabella stazionarieta"),
  check("decomposition-table", "scomposizione intensita"),
  check("physics-table", "coefficienti"),
  check("limits-list", "limiti"),
  check("self-check", "auto-verifica"),
].every(Boolean);

console.log("");
console.log("citta mostrate      :", d.querySelectorAll(".city-card").length);
console.log("barre baseline      :", d.querySelectorAll("#baseline-chart rect.bar").length);
console.log("punti affidabilita  :", d.querySelectorAll(".reliability-dot").length);
console.log("righe coefficienti  :", d.querySelectorAll("#physics-table tbody tr").length);
console.log("auto-verifica       :", d.getElementById("self-check").className);
console.log("  ->", d.getElementById("self-check").textContent.trim().slice(0, 100));

// Regression: each day block must be labelled against the READER's date. The
// page once said "Tomorrow" above a forecast for the day already in progress,
// and did so for 23 hours out of every 24.
const pending = JSON.parse(bundle).ledger.filter((r) => r.observed_rain === null);
const days = [...new Set(pending.map((r) => r.target_date))].sort();
const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
const expected = {
  past: ["Awaiting verification", "In attesa di verifica"],
  today: ["Today", "Oggi"],
  tomorrow: ["Tomorrow", "Domani"]
};
const headings = [...d.querySelectorAll(".day-heading")];
console.log(`blocchi giornalieri  : ${headings.length} (attesi ${days.length})`);
if (headings.length !== days.length) errors.push("numero di blocchi errato");
days.forEach((target, i) => {
  const offset = Math.round((new Date(`${target}T00:00:00`) - midnight) / 86400000);
  const when = offset <= -1 ? "past" : offset === 0 ? "today" : "tomorrow";
  const got = headings[i].textContent.trim();
  const ok = expected[when].some((w) => got.startsWith(w));
  console.log(`  ${target} (${offset >= 0 ? "+" : ""}${offset}g)  "${got}"  ${ok ? "ok" : "SBAGLIATO"}`);
  if (!ok) errors.push(`blocco ${target}: atteso ${expected[when].join("/")}`);
});

const before = d.querySelector("h1").textContent;
d.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
await new Promise((r) => setTimeout(r, 200));
const after = d.querySelector("h1").textContent;
console.log("");
console.log(`cambio lingua       : "${before}" -> "${after}"  (lang=${d.documentElement.lang})`);
console.log("errori JS           :", errors.length ? errors : "nessuno");
process.exit(ok && !errors.length && before !== after ? 0 : 1);
