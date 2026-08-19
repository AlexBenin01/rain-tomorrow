# Will it rain tomorrow?

A statistical rain forecast for five towns in the Veneto, **published every evening before the day
it forecasts** and scored in public against what actually happened.

**[→ Open the live page](https://alessandro001.github.io/rain-tomorrow/)**

The model is a logistic regression: 17 coefficients, a 9 KB JSON file, and a sigmoid. It runs in
your browser — the page recomputes it from the published artefact and checks it reproduces the
Python training output exactly, on reference cases stored inside the artefact.

---

## Three results worth the click

### 1. The best predictor there is scores worse than saying nothing

Persistence — *"tomorrow like today"* — is the strongest single predictor of rain there is.
Expressed as a flat yes or no, it scores a Brier skill score between **−0.22 and −0.39** across the
five towns: worse than a forecaster who says the same thing every single day. The identical
information, expressed as a **calibrated probability**, scores **+0.09 to +0.15**.

That is between 0.37 and 0.48 of skill from the same signal, moved entirely by calibration. Having
the right predictor is not enough. It has to be expressed as a probability.

### 2. The data refused the training window I had chosen

The plan was to train on the full record back to 1996. Wet-day frequency turns out to be steady for
two decades and then to fall away sharply — **but only in the foothills**:

| | 1996–2024 | 2016–2024 | change |
|---|---|---|---|
| Bassano del Grappa | 40.2% | 34.1% | **−6.2** |
| Conegliano | 43.1% | 33.0% | **−10.1** |
| Vicenza | 33.1% | 31.7% | −1.4 |
| Padova | 29.7% | 31.0% | **+1.3** |
| Venezia | 29.9% | 28.6% | −1.3 |

Conegliano and Padova are 60 km apart and move in opposite directions. Decomposed by intensity, two
things are happening at once: everywhere the heaviest days become *more* frequent and rain arrives
in larger portions, while only in the foothills does the count of light rain days collapse.

Built on one location, the conclusion would have been "the series is non-stationary". Five locations
made it specific.

### 3. The model missed a pre-registered threshold, and the threshold did not move

The stop criterion was written down before any result was seen. The first attempt fell short of it.
The fix was not to relax the criterion — it was to add the physics that had been left out: pressure,
the 24-hour pressure tendency, wind direction, cloud cover. Skill rose consistently in validation
*and* test, and the criterion was met on its own terms.

---

## Results

588 held-out days per location, everything after 2024-12-31, never trained on:

| location | Brier | BSS vs climatology | gain over calibrated persistence |
|---|---|---|---|
| Bassano del Grappa | 0.1746 | +0.205 | +0.074 |
| Conegliano | 0.1696 | +0.210 | +0.111 |
| Vicenza | 0.1656 | +0.216 | +0.097 |
| Padova | 0.1625 | +0.221 | +0.068 |
| Venezia | 0.1653 | +0.210 | +0.119 |

Full baselines, reliability curves, threshold sweeps and coefficients per location:
**[`reports/REPORT.md`](reports/REPORT.md)**. Data-quality and stationarity work:
**[`reports/METHOD_NOTES.md`](reports/METHOD_NOTES.md)**.

### Nobody told it about weather

No physical rule was imposed anywhere — it is least squares on a sigmoid. The signs come out right
anyway, and identically at all five locations: **pressure** strongest and negative, **falling
pressure** negative, **cloud cover** positive, **humidity** positive, and the **easterly wind**
component positive in every town — moisture drawn off the Adriatic.

The weights also shift along the gradient: pressure and cloud carry steadily more of the load from
the foothills to the lagoon. Inland, rain forming over the hills adds variance the synoptic picture
cannot explain; on the coast the rain is more purely synoptic.

---

## What this is not

**It is not competing with Open-Meteo, and it would lose.** Behind their forecast is numerical
weather prediction: atmospheric physics on supercomputers, global data assimilation, ensembles. A
statistical model reading yesterday's observations at a single point cannot see a front that has not
arrived yet. Their forecast is recorded next to each of ours as the **operational reference** a
statistical baseline is always reported against — the interesting question is how much skill is
recoverable without any of that machinery.

Two caveats travel with their numbers wherever they appear: their probability answers a different
question (rain at *some hour*, more frequent than a full millimetre over the whole day), so the
like-for-like comparison is the deterministic one; and their product is generated for the whole
world, continuously. Nothing here evaluates their service.

Other limits, stated rather than discovered later:

- **One grid point per town**, not a spatial field. At the scale of a town that is a choice.
- **Consecutive days are not independent.** The effective sample size is far smaller than the row
  count, and the confidence intervals are wider than they look.
- **Gradient boosting scores slightly better at four of the five towns** (+0.011 on average). The
  linear model ships anyway — it is 17 numbers that run in a browser, and its coefficients are the
  finding above. The comparison is if anything unfair *to* boosting: the regression's
  regularisation was tuned on the validation year, the boosting hyper-parameters were not.
- **The most recent days of the reanalysis are preliminary.** Training and serving both use the
  archive, which removes the product mismatch, but that residual difference is not yet quantified.

---

## How the ledger works

Every evening a GitHub Action scores the days that have finished and issues tomorrow's forecast for
all five towns, appending to [`public/forecasts.jsonl`](public/forecasts.jsonl):

```jsonc
{
  "issued_at": "2026-08-19T21:04:11Z",   // committed before the day it forecasts
  "city": "vicenza",
  "target_date": "2026-08-20",
  "our_prob": 0.36,
  "our_rain": false,
  "om_precip_mm": 3.4,                   // Open-Meteo's forecast, as reference
  "om_rain": true,
  "climatology": 0.29,
  "observed_mm": null,                   // filled in by a later run
  "observed_rain": null
}
```

The record is append-only and keyed on `(city, target_date)`. **A published forecast is never
rewritten** — only the outcome fields may be filled, and only once. That is the whole point: you
cannot tune a model on data that does not exist yet, and `git log` proves the order. It is the one
thing a backtest can never demonstrate.

The run happens late in the evening because forecasting *tomorrow* needs *today* essentially
complete; a morning run would be forecasting today instead. It needs no `pip install` at all.

---

## Reproducing it

```bash
# 1. data — no API key needed
python src/fetch_weather.py --split analysis --all   # 1996-2024, stationarity study only
python src/fetch_weather.py --split train    --all   # 2016-2024
python src/fetch_weather.py --split test     --all   # everything after 2024

# 2. models — refuses to ship one that misses the stop criterion
pip install -r requirements.txt
python src/train.py --all --ablation padova
python src/stationarity.py --all

# 3. tests — no database, no network
pip install pytest && python -m pytest tests -q

# 4. the page
python src/build_site.py
python -m http.server 8080 --directory docs
```

The page render is checked too, in a simulated DOM — see
[`tests/render_check.mjs`](tests/render_check.mjs).

---

## Layout

```
src/        fetch, train, metrics, stationarity, daily run, ledger, site build
data/       the CSVs everything is built from
models/     one self-contained artefact per town
public/     forecasts.jsonl — the ledger
reports/    REPORT.md, METHOD_NOTES.md, stationarity.json
docs/       the published page (GitHub Pages)
tests/      pytest, plus the DOM render check
```

The same model also drives the weather in [AgroAgent](https://github.com/Alessandro001/agroagent),
a simulated vineyard supervised by an LLM agent, where the forecast decides whether to postpone a
fungicide treatment. This repository is where it is trained and verified.

---

## Licences

Code MIT — [`LICENSE`](LICENSE). Weather data CC BY 4.0 from Open-Meteo, derived from the ERA5
reanalysis of the Copernicus Climate Change Service at ECMWF — [`DATA.md`](DATA.md).
