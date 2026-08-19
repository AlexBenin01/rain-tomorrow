// The model, in the browser. The same 17 coefficients Python used.
//
// This file exists to make one claim checkable rather than merely stated: the
// page recomputes the model from the published artefact and compares against
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

export function predict(city, features) {
  let z = city.intercept;
  for (let i = 0; i < city.feature_names.length; i++) {
    const name = city.feature_names[i];
    const scale = city.scaler_scale[i] || 1;
    z += city.coefficients[i] * ((features[name] - city.scaler_mean[i]) / scale);
  }
  return sigmoid(z);
}

// Reproduce the training output on the stored reference vectors.
// Returns { ok, cases, coefficients, error }.
export function selfCheck(cities, tolerance = 1e-9) {
  let cases = 0;
  for (const city of cities) {
    for (const [i, reference] of (city.reference_vectors || []).entries()) {
      const got = predict(city, reference.features);
      const want = reference.expected_probability;
      if (Math.abs(got - want) > tolerance) {
        return {
          ok: false,
          error: `${city.key} case ${i}: ${got.toPrecision(12)} vs ${want.toPrecision(12)}`
        };
      }
      cases++;
    }
  }
  return { ok: true, cases, coefficients: cities[0].feature_names.length };
}
