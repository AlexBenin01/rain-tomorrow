// The models, in the browser. The same coefficients Python used.
//
// This file exists to make one claim checkable rather than merely stated: the
// page recomputes every model from the published artefact and compares against
// reference cases produced by the training run. If the feature order, the
// standardisation or the sigmoid ever drift apart, the page says so at the
// bottom instead of quietly showing different numbers.

// Numerically stable logistic function. `1 / (1 + exp(-z))` overflows for
// strongly negative z — never on real weather, which is exactly why it is the
// kind of bug that surfaces in production rather than in testing.
export function sigmoid(z) {
  if (z >= 0) return 1 / (1 + Math.exp(-z));
  const e = Math.exp(z);
  return e / (1 + e);
}

export function predictThreshold(city, block, features) {
  let z = block.intercept;
  for (let i = 0; i < city.feature_names.length; i++) {
    const name = city.feature_names[i];
    const scale = block.scaler_scale[i] || 1;
    z += block.coefficients[i] * ((features[name] - block.scaler_mean[i]) / scale);
  }
  return sigmoid(z);
}

// Thresholds a town actually publishes, lowest first. A threshold that failed
// the stop criterion during training is present in the artefact but not shipped,
// so the reason it is missing stays in the file rather than in someone's memory.
export function shippedThresholds(city) {
  return Object.keys(city.thresholds)
    .filter((mm) => city.thresholds[mm].shipped)
    .map(Number)
    .sort((a, b) => a - b);
}

export function primaryThreshold(city) {
  return shippedThresholds(city)[0];
}

// The ladder, with the ordering enforced.
//
// The four models are fitted independently, so nothing stops P(>= 5 mm) coming
// out above P(>= 1 mm) on a given day — which is impossible, and happens on
// about 7% of days. Clamping downwards is deliberate: the lower threshold has
// far more events behind it, so where two disagree it is the one to trust.
// Measured cost of the clamp: none, to five decimal places.
export function predictLadder(city, features) {
  const out = new Map();
  let ceiling = 1;
  for (const mm of shippedThresholds(city)) {
    const p = Math.min(predictThreshold(city, city.thresholds[mm], features), ceiling);
    out.set(mm, p);
    ceiling = p;
  }
  return out;
}

// Reproduce the training output on the stored reference vectors, for EVERY
// threshold — a mismatch in the 10 mm model would otherwise go unnoticed until
// somebody read the page.
export function selfCheck(cities, tolerance = 1e-9) {
  let cases = 0;
  let models = 0;
  for (const city of cities) {
    for (const [mm, block] of Object.entries(city.thresholds)) {
      models++;
      for (const [i, reference] of (block.reference_vectors || []).entries()) {
        const got = predictThreshold(city, block, reference.features);
        const want = reference.expected_probability;
        if (Math.abs(got - want) > tolerance) {
          return {
            ok: false,
            error: `${city.key} at ${mm} mm, case ${i}: ` +
              `${got.toPrecision(12)} vs ${want.toPrecision(12)}`
          };
        }
        cases++;
      }
    }
  }
  return { ok: true, cases, models, coefficients: cities[0].feature_names.length };
}
