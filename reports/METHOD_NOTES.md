# Method notes

Working notes on the data sources and the decisions they forced. Written as the questions were
answered, not reconstructed afterwards.

---

## 1. API spike — 19 August 2026

Two Open-Meteo endpoints are involved, and confusing them would quietly break the whole project:

| Endpoint | What it is | Used here for |
|---|---|---|
| `archive-api.open-meteo.com/v1/archive` | **ERA5 / ERA5-Land reanalysis** | Training data, live features, observed outcomes |
| `api.open-meteo.com/v1/forecast` | **Operational NWP** (ECMWF IFS, ICON) | Open-Meteo's own forecast, as a benchmark |

Neither requires an API key.

### 1.1 Does the forecast API expose a daily rain probability?

**Yes — all three aggregations.** Verified at Vicenza:

```
precipitation_probability_max  -> [35, 78, 83]
precipitation_probability_mean -> [3, 32, 52]
precipitation_probability_min  -> [0, 0, 8]
```

This matters for fairness. Had only hourly probabilities been available, collapsing them to a
daily figure would have been **our** transformation applied to **their** product, and any
comparison would have been contaminated by our choice. Their own daily aggregate removes that
objection.

**But the events still do not match, and this must be stated wherever the comparison appears.**
`precipitation_probability_max` is the probability of rain *at some hour* of the day. Our target is
*daily accumulation ≥ 1 mm*. The first event is strictly more frequent than the second, so scoring
their `_max` against our target penalises them by construction.

**Decision.**
- **Primary comparison — deterministic and symmetric:** their forecast `precipitation_sum ≥ 1 mm`
  against our thresholded decision. Same event, same rule, no interpretation.
- **Secondary — probabilistic:** their `precipitation_probability_max` against our probability,
  reported *with the event mismatch stated in the same sentence as the number*. It is informative
  about calibration, not a like-for-like skill contest.

### 1.2 Does `past_days` return usable recent days?

Yes. With `past_days=7` the API returns every variable the model needs — precipitation, min/max
temperature, mean relative humidity, mean MSL pressure, mean cloud cover, mean wind speed, dominant
wind direction — with no nulls, for the seven completed days plus today plus the forecast horizon.

Timing consequence: to predict **tomorrow** the model needs **today** essentially complete. The
daily run must therefore happen **late in the evening**, not in the morning. A morning run using
yesterday's data would be predicting *today*, which is a different (and less useful) product.

### 1.3 How far apart are the two sources? — the finding that changed the design

Compared over **60 days** at Vicenza (2026-06-20 → 2026-08-18), the same variables from
`archive-api` and from `forecast-api`:

| variable | mean difference | mean absolute difference | max |
|---|---|---|---|
| `precipitation_sum` (mm) | +0.42 | 1.51 | 45.30 |
| `temperature_2m_min` (°C) | +0.24 | 0.74 | 3.00 |
| `temperature_2m_max` (°C) | **+1.89** | 1.89 | 4.40 |
| `relative_humidity_2m_mean` (%) | −2.72 | 4.18 | 11.00 |
| `pressure_msl_mean` (hPa) | −0.11 | 0.14 | 0.40 |
| `cloud_cover_mean` (%) | **+9.20** | **11.37** | 49.00 |
| `wind_speed_10m_mean` (km/h) | +0.88 | 1.09 | 3.40 |

And the number that actually bites:

> **On 8 days out of 60 — 13% — the two sources disagree on whether it rained at all** (≥ 1 mm).
> Examples: 2026-06-22, 5.4 mm real-time against 0.1 mm in the archive; 2026-07-17, 0.0 mm against
> 3.6 mm.

This is **not a latency artefact**. The discrepancy is spread evenly across the whole 60-day window,
including days where the archive has long since settled on final ERA5. It is a genuine difference
between two products: a global reanalysis on a coarse grid versus an operational high-resolution
model analysis. Over the Prealpine foothills, where convective rain is small-scale, that resolution
gap is exactly where one would expect it to show.

**Impact on the model's output, quantified.** Propagating the mean biases through the standardised
coefficients:

```
cloud_today      bias  +9.20   ->  +0.1152 logit
tmean_today      bias  +1.07   ->  +0.0263 logit
rh_today         bias  -2.72   ->  -0.0460 logit
pressure_today   bias  -0.11   ->  +0.0053 logit
wind_speed       bias  +0.88   ->  -0.0577 logit
                                   --------
                          net      +0.0432 logit   (a 30% probability becomes 30.9%)
```

The *systematic* effect is small because the biases largely cancel. The *random* day-to-day
disagreement does not cancel and would add noise to every individual forecast — and, worse, it
would make the recorded outcome depend on which source we happened to ask.

### 1.4 Decision

**Features and observed outcomes both come from `archive-api`, the same product the model was
trained on.** Verified that it serves right up to the current day with no nulls:

```
2026-08-17   1.6 mm   RH 73   1011.5 hPa   cloud 73
2026-08-18   0.0 mm   RH 74   1011.0 hPa   cloud 51
2026-08-19   0.3 mm   RH 73   1011.1 hPa   cloud 35   <- today, already served
```

`forecast-api` is used **only** for Open-Meteo's own prediction, which is what it is for. This
removes the train/serve product skew entirely rather than trying to correct for it.

The residual skew is now the narrower one — preliminary ERA5T for the most recent days versus final
ERA5 once it settles — and it is the honest one to keep monitoring rather than the one we could have
avoided and did not.

---

## 2. Stationarity — and a finding that only five locations could reveal

The training window was going to be 1996-2024. It is 2016-2024 instead, and the reason is in the
`analysis` split (1996-2024, never trained on).

### 2.1 Wet-day frequency, whole series versus recent regime

| location | 1996-2024 | 2016-2024 | change | intensification signature |
|---|---|---|---|---|
| Bassano del Grappa | 40.2% | 34.1% | **−6.2** | **yes** |
| Conegliano | 43.1% | 33.0% | **−10.1** | **yes** |
| Vicenza | 33.1% | 31.7% | −1.4 | no |
| Padova | 29.7% | 31.0% | **+1.3** | no |
| Venezia | 29.9% | 28.6% | −1.3 | no |

Built on Conegliano alone, the conclusion would have been *"the series is non-stationary"*. With
five locations it is sharper and more interesting: **the drying is concentrated in the foothills and
disappears over the plain.** Conegliano and Padova are about 60 km apart and move in opposite
directions.

### 2.2 The decomposition by intensity, and what it separates

`1996-2005 → 2016-2024`, relative change in the frequency of days above each threshold:

| threshold | Bassano | Conegliano | Vicenza | Padova | Venezia |
|---|---|---|---|---|---|
| ≥ 0.2 mm | −16% | −24% | −3% | +9% | −1% |
| ≥ 1.0 mm | **−19%** | **−30%** | −4% | +9% | −4% |
| ≥ 5.0 mm | −9% | −11% | +3% | +10% | −4% |
| ≥ 10.0 mm | +3% | −3% | +7% | +12% | +2% |
| ≥ 20.0 mm | **+12%** | **+7%** | **+12%** | **+6%** | **+4%** |

Mean accumulation on wet days, over the same windows:

| | Bassano | Conegliano | Vicenza | Padova | Venezia |
|---|---|---|---|---|---|
| early → late (mm) | 8.41 → 9.85 | 8.16 → 10.21 | 8.60 → 9.44 | 8.71 → 8.91 | 8.92 → 9.13 |

Two separate things are happening, and only the spatial spread makes them separable:

1. **Region-wide:** the extreme tail rises everywhere (≥ 20 mm up at all five sites) and the mean
   accumulation on a wet day rises everywhere. Rain is arriving in larger portions.
2. **Foothills only:** the frequency of light and moderate rain days falls sharply. This is what
   drags the wet-day count down at Bassano and Conegliano and leaves the plain untouched.

At the two foothill sites the change is monotone in intensity and reverses at the top — the
signature of precipitation intensification. A change in how the reanalysis represents drizzle would
appear only at the very bottom of the scale and would not reverse.

**The honest caveat.** A −10 point shift at Conegliano against +1.3 at Padova, 60 km away, is a
large contrast for two neighbouring grid cells. Real orographic changes in the Prealps are
documented and plausible, but a signal this sharp at a single reanalysis grid point also deserves
caution: part of it may reflect how ERA5 resolves that particular cell rather than the atmosphere
above it. The two explanations cannot be separated from a single reanalysis, and the decision below
does not depend on separating them.

### 2.3 Decision, and what it costs

**One training window for every location: 2016-01-01 onwards.** The rule is uniform and chosen by
the worst case, rather than tuned per city — a per-location knob picked after seeing the analysis
would be exactly the kind of freedom this project is trying not to take.

It is not free. At Vicenza, Padova and Venezia the regime is stable, so the short window discards
roughly two thirds of the available history for no benefit: ~2 900 day pairs instead of ~10 500.
Whether that costs measurable skill is a question the data can answer, so it is answered rather
than assumed — see `REPORT.md`, where Padova is trained on both windows and compared on the same
held-out test set.

The train/test boundary is a different matter and stays global and absolute: **nothing after
2024-12-31 is ever trained on, at any location, for any reason.**

---

## 2b. The current day is never returned truncated — it is filled

Measured on 2026-08-20 at 19:00 local: the archive returns **all 24 hours** for the day in
progress, including hours that have not happened yet.

```
hours returned for 2026-08-20 : 24
hours with a value            : 24
last hour with data           : 2026-08-20T23:00
```

This is useful and slightly uncomfortable at the same time.

**Useful,** because it removes a whole class of error: the daily aggregate is never computed over a
truncated day, so `temperature_2m_max` and `precipitation_sum` are not silently biased low just
because the evening has not arrived.

**Uncomfortable,** because it means the feature day always contains some model output rather than
pure analysis. The claim "trained on reanalysis, served from reanalysis" is therefore true of the
*product*, but the most recent day is a blend. The size of the blend depends on when the run
happens: the scheduled 21:00 UTC run leaves roughly one hour filled, while a run at 17:00 UTC leaves
about five.

It is a smaller problem than the one avoided — feeding the model an operational analysis it was
never trained on, which disagrees with the reanalysis on 13% of rain days (§1.3) — but it is not
zero, and it belongs in the record rather than in a footnote.

---

## 3. Licence

Weather data from Open-Meteo, **CC BY 4.0**, derived from the **ERA5 / ERA5-Land** reanalysis of the
**Copernicus Climate Change Service (C3S)** at ECMWF. Attribution is mandatory and lives in
[`DATA.md`](../DATA.md).
