# Will it rain tomorrow?

Rain forecast for five towns in the Veneto, published every evening **before the day it forecasts**
and scored in public against what was observed.

**[Open the live page](https://alexbenin01.github.io/rain-tomorrow/)**

A logistic regression per intensity threshold: 25 coefficients, four thresholds, twenty models in
all. Small enough to run in the browser, so the page recomputes them from the published artefacts
and checks they reproduce the Python training output on reference cases stored inside those
artefacts.

It answers how much, not only whether: *at least 1 mm 63% · at least 5 mm 46% · at least 10 mm 33% ·
at least 20 mm 14%*.

---

## Results

589 held-out days per town, everything after 2024-12-31, never trained on:

| town | Brier | BSS vs climatology | gain over calibrated persistence |
|---|---|---|---|
| Bassano del Grappa | 0.1639 | +0.253 | +0.122 |
| Conegliano | 0.1597 | +0.256 | +0.157 |
| Vicenza | 0.1547 | +0.267 | +0.148 |
| Padova | 0.1506 | +0.277 | +0.124 |
| Venezia | 0.1558 | +0.255 | +0.163 |

That skill is not spread evenly across the year. The section on failure below is the one to read
before quoting these numbers.

Full baselines, reliability curves, threshold sweeps and coefficients: [`reports/REPORT.md`](reports/REPORT.md).
Data quality and stationarity: [`reports/METHOD_NOTES.md`](reports/METHOD_NOTES.md). What the
forecasts sound like and how they fail: [`reports/FORECAST_ANALYSIS.md`](reports/FORECAST_ANALYSIS.md).

---

## Three results worth the click

### The best predictor available scores worse than saying nothing

Persistence, "tomorrow like today", is the strongest single predictor there is. Stated as a flat yes
or no it scores a Brier skill score between **−0.21 and −0.39** across the five towns, worse than a
forecaster who repeats the same thing every day. The identical information, expressed as a
**calibrated probability**, scores **+0.09 to +0.15**.

Between 0.37 and 0.48 of skill, from the same signal, moved by calibration alone.

### The data refused the training window

The plan was to train on the full record back to 1996. Wet-day frequency turns out to be steady for
two decades and then to fall away, but only in the foothills:

| | 1996–2024 | 2016–2024 | change |
|---|---|---|---|
| Bassano del Grappa | 40.2% | 34.1% | −6.1 |
| Conegliano | 43.1% | 33.0% | −10.1 |
| Vicenza | 33.1% | 31.7% | −1.4 |
| Padova | 29.7% | 31.0% | +1.3 |
| Venezia | 29.9% | 28.6% | −1.3 |

Conegliano and Padova are 60 km apart and move in opposite directions. Decomposed by intensity, two
things happen at once: everywhere the heaviest days become more frequent and rain arrives in larger
portions, while only in the foothills does the count of light rain days collapse.

One location would have given "the series is non-stationary". Five made it specific.

### The shape of the day beats the day

Every variable started as a daily mean or sum, which cannot separate *cloudy all day* from
*clearing, then clouding over*. Eight predictors were added from the hourly series to recover that
shape, with everything else held identical. Skill rose **at all five towns, by +0.050 on average**.

The strongest of them is the pressure at 18:00 minus the pressure at 06:00, second only to the
pressure level itself and negative everywhere: pressure falling within the day is the front arriving.

It also superseded a predictor rather than adding to one. The old day-to-day pressure tendency was
negative at every town. Once the sharper measure arrived it flipped positive everywhere and became a
small correction, so its sign alone stopped being interpretable. Only the sum of the tendency terms
is, and that stays firmly negative.

---

## When it fails

The forecast correlates **0.68** with the rain that has already fallen and **0.51** with the rain
being predicted. It tracks today more closely than tomorrow.

Splitting the test set by whether the weather changed makes the consequence concrete. A day is a
transition when tomorrow differs from today: rain starting, or rain stopping.

| | share of days | Brier |
|---|---|---|
| weather unchanged | 72% | 0.076 |
| weather changed | 28% | 0.366 |

On transitions the skill score against climatology is **−0.27**. On the days when the weather
actually changes, the seasonal average does better than this model.

Calibrated persistence scores **0.470** on those same days against the model's **0.366**, so the
model recovers 0.104 of Brier that pure persistence loses. It carries real information about change,
and not enough of it. The headline skill of about +0.26 comes mostly from being right on the 72% of
days when nothing changes.

The live record reproduced this within four days of going up: it missed the onset of a rain event,
called the day in the middle correctly, missed the end, then recovered.

---

## Limitations

The comparison with Open-Meteo is a reference, not a contest, and not one this model can win. Behind
their forecast is numerical weather prediction: atmospheric physics on supercomputers, global data
assimilation, ensembles. A statistical model reading yesterday's observations at a single point
cannot see a front that has not arrived. Their forecast is recorded next to each of ours as the
operational reference a statistical baseline is always reported against.

Two caveats travel with their numbers. Their probability answers a different question, the chance of
rain at *some hour*, which is more frequent than a full millimetre across the whole day, so the
like-for-like comparison is the deterministic one. And their product is generated for the whole
world, continuously; nothing here evaluates their service.

Other limits:

- **One grid point per town**, not a spatial field. At the scale of a town that is a deliberate choice.
- **Consecutive days are not independent.** The effective sample size is far smaller than the row
  count and the confidence intervals are wider than they look.
- **The 20 mm threshold is not published at Vicenza or Padova.** It fires on 3 to 5% of days, which
  is 106 examples at Padova, and it failed its acceptance test there. The artefact records the
  failure so the absence is documented.
- **Sharper cost some calibration.** The intra-day predictors raised resolution by about a quarter
  and moved reliability from 0.003 to 0.006. The net is positive and it is a trade.
- **Gradient boosting scores slightly better at four of the five towns** (+0.011 on average). The
  linear model ships because it is 25 numbers per threshold that run in a browser, and because its
  coefficients can be read. The comparison is if anything unfair to boosting: the regression's
  regularisation was tuned on the validation year, the boosting hyper-parameters were not.
- **The most recent days of the reanalysis are preliminary.** Training and serving both use the
  archive, which removes the product mismatch, but that residual difference is not quantified.

---

## How the ledger works

Every evening a GitHub Action scores the days that have finished and issues tomorrow's forecast for
all five towns, appending to [`public/forecasts.jsonl`](public/forecasts.jsonl):

```jsonc
{
  "issued_at": "2026-08-22T21:20:11Z",   // committed before the day it forecasts
  "city": "vicenza",
  "target_date": "2026-08-23",
  "our_prob": 0.13,
  "our_probs": { "1": 0.13, "5": 0.07, "10": 0.02 },
  "om_precip_mm": 0.0,                   // Open-Meteo's forecast, as reference
  "om_rain": false,
  "climatology": 0.29,
  "model_version": "lr-v2@2026-08-20",
  "observed_mm": null,                   // filled in by a later run
  "observed_rain": null
}
```

The record is append-only and keyed on `(city, target_date)`. A published forecast is never
rewritten: only the outcome fields may be filled, and only once. A model cannot be tuned on data
that does not exist yet, and `git log` proves the order.

Scores are reported per `model_version` and never pooled. The ledger already spans one model change.

The run happens late in the evening because forecasting tomorrow needs today essentially complete. A
morning run would be forecasting today instead. It needs no `pip install`.

---

## Reproducing it

```bash
# 1. data, no API key needed
python src/fetch_weather.py --split analysis --all   # 1996-2024, stationarity study only
python src/fetch_weather.py --split train    --all   # 2016-2024
python src/fetch_weather.py --split test     --all   # everything after 2024

# 2. models, refusing to ship a threshold that misses the acceptance test
pip install -r requirements.txt
python src/train.py --all --thresholds --ablation padova
python src/train.py --all --compare-features    # does the day's shape help?
python src/stationarity.py --all
python src/analyse_forecasts.py                 # how the forecasts behave, and fail

# 3. tests, no database and no network
pip install pytest && python -m pytest tests -q
python scripts/check_prose.py                   # prose figures match the artefacts

# 4. the page
python src/build_site.py
python -m http.server 8080 --directory docs
```

The page render is checked in a simulated DOM: [`tests/render_check.mjs`](tests/render_check.mjs).

---

## Layout

```
src/        fetch, train, metrics, stationarity, daily run, ledger, analysis, site build
data/       the CSVs everything is built from
models/     one self-contained artefact per town, four thresholds each
public/     forecasts.jsonl, the ledger
reports/    REPORT.md, METHOD_NOTES.md, FORECAST_ANALYSIS.md, and the JSON they emit
docs/       the published page (GitHub Pages)
tests/      pytest, plus the DOM render check
scripts/    data download, prose check
```

The same model drives the weather in [AgroAgent](https://github.com/AlexBenin01/agroagent), a
simulated vineyard supervised by an LLM agent, where the forecast decides whether to postpone a
fungicide treatment. This repository is where it is trained and verified.

`models/conegliano.json` is consumed there **verbatim**, the whole file, unmodified: the vineyard
sits on the same ERA5 grid node. It reads the 1 mm threshold and ignores the other three. Anyone
changing the artefact schema has a downstream consumer to consider, and it will notice: AgroAgent
recomputes the reference vectors on startup and refuses to boot if they do not reproduce.

---

## Licences

Code MIT, see [`LICENSE`](LICENSE). Weather data CC BY 4.0 from Open-Meteo, derived from the ERA5
reanalysis of the Copernicus Climate Change Service at ECMWF, see [`DATA.md`](DATA.md).
