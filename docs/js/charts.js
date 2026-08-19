// Charts as inline SVG, with no charting library.
//
// Not asceticism: a page that depends on a CDN can break years later for a
// reason nobody remembers, and this one is meant to still work when someone
// clicks the link from an old post. Everything here is a few dozen lines of
// string building.

const NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

function svg(width, height, extra = {}) {
  return el("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width: "100%",
    role: "img",
    ...extra
  });
}

/**
 * Horizontal bars that can point either way, with a zero line.
 * items: [{ label, value, highlight?, note? }]
 */
export function divergingBars(items, { format = (v) => v.toFixed(3), height = 26 } = {}) {
  const W = 460;
  const labelW = 168;
  const valueW = 52;
  const plotW = W - labelW - valueW;
  const H = items.length * height + 12;

  const max = Math.max(...items.map((i) => Math.abs(i.value)), 0.05);
  const zero = labelW + plotW / 2;
  const scale = (v) => (v / max) * (plotW / 2 - 4);

  const node = svg(W, H, { class: "chart chart-bars" });
  node.appendChild(
    el("line", { x1: zero, y1: 4, x2: zero, y2: H - 8, class: "axis-zero" })
  );

  items.forEach((item, i) => {
    const y = i * height + 6;
    const w = scale(item.value);
    node.appendChild(
      el("text", { x: labelW - 10, y: y + height / 2 - 2, class: "bar-label", "text-anchor": "end" },
        item.label)
    );
    node.appendChild(
      el("rect", {
        x: w < 0 ? zero + w : zero,
        y: y + 3,
        width: Math.abs(w) || 1,
        height: height - 12,
        rx: 2,
        class: `bar ${item.value < 0 ? "negative" : "positive"}${item.highlight ? " highlight" : ""}`
      })
    );
    node.appendChild(
      el("text", {
        x: W - 6, y: y + height / 2 - 2, class: "bar-value", "text-anchor": "end"
      }, format(item.value))
    );
  });
  return node;
}

/**
 * Reliability diagram: forecast probability against observed frequency.
 * points: [{ predicted, observed, n }]
 */
export function reliabilityChart(points, labels) {
  const S = 300;
  const pad = 34;
  const plot = S - pad * 2;
  const x = (v) => pad + v * plot;
  const y = (v) => S - pad - v * plot;

  const node = svg(S, S + 16, { class: "chart chart-reliability" });

  for (let t = 0; t <= 1.0001; t += 0.25) {
    node.appendChild(el("line", { x1: x(t), y1: y(0), x2: x(t), y2: y(1), class: "grid" }));
    node.appendChild(el("line", { x1: x(0), y1: y(t), x2: x(1), y2: y(t), class: "grid" }));
    node.appendChild(
      el("text", { x: x(t), y: S - pad + 14, class: "tick", "text-anchor": "middle" },
        `${Math.round(t * 100)}%`)
    );
    node.appendChild(
      el("text", { x: pad - 6, y: y(t) + 3, class: "tick", "text-anchor": "end" },
        `${Math.round(t * 100)}%`)
    );
  }

  node.appendChild(
    el("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), class: "diagonal" })
  );

  const path = points
    .map((p, i) => `${i ? "L" : "M"}${x(p.predicted).toFixed(1)},${y(p.observed).toFixed(1)}`)
    .join(" ");
  node.appendChild(el("path", { d: path, class: "reliability-line" }));

  points.forEach((p) => {
    const dot = el("circle", {
      cx: x(p.predicted), cy: y(p.observed),
      // area proportional to the sample count, floored so a thin bin stays visible
      r: Math.max(3.5, Math.min(9, Math.sqrt(p.n) * 0.7)),
      class: "reliability-dot"
    });
    dot.appendChild(el("title", {}, `${labels.predicted} ${Math.round(p.predicted * 100)}% · ` +
      `${labels.observed} ${Math.round(p.observed * 100)}% · ${p.n} ${labels.samples}`));
    node.appendChild(dot);
  });

  node.appendChild(
    el("text", { x: S / 2, y: S + 12, class: "axis-title", "text-anchor": "middle" },
      labels.predicted)
  );
  // the diagonal means nothing without a name on it
  node.appendChild(
    el("text", {
      x: x(0.52), y: y(0.62), class: "diagonal-label",
      transform: `rotate(-45 ${x(0.52)} ${y(0.62)})`, "text-anchor": "middle"
    }, labels.perfect)
  );
  return node;
}

/**
 * One thin bar per city, on a shared scale — a strip that makes a gradient
 * across locations visible at a glance.
 */
export function cityStrip(values, max) {
  const W = 150;
  const H = 18;
  const half = W / 2;
  const node = svg(W, H, { class: "chart chart-strip" });
  node.appendChild(el("line", { x1: half, y1: 0, x2: half, y2: H, class: "axis-zero" }));

  const barH = H / values.length - 1;
  values.forEach((v, i) => {
    const w = (v / max) * (half - 2);
    node.appendChild(
      el("rect", {
        x: w < 0 ? half + w : half,
        y: i * (barH + 1),
        width: Math.abs(w) || 0.7,
        height: barH,
        class: `bar ${v < 0 ? "negative" : "positive"}`
      })
    );
  });
  return node;
}

/** A 0–100% meter for a single probability. */
export function probabilityMeter(probability, climatology) {
  const W = 200;
  const H = 12;
  const node = svg(W, H, { class: "chart chart-meter" });
  node.appendChild(el("rect", { x: 0, y: 3, width: W, height: 6, rx: 3, class: "meter-track" }));
  node.appendChild(
    el("rect", {
      x: 0, y: 3, width: Math.max(2, probability * W), height: 6, rx: 3,
      class: `meter-fill ${probability >= 0.5 ? "wet" : "dry"}`
    })
  );
  // the monthly normal, as the reference the number should be read against
  const tick = el("line", {
    x1: climatology * W, y1: 0, x2: climatology * W, y2: H, class: "meter-climatology"
  });
  node.appendChild(tick);
  return node;
}
