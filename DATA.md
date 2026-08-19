# Data sources and attribution

## Weather data

All weather data in this repository — the CSV files under `data/`, the daily ledger under
`public/`, and everything derived from them — comes from the [Open-Meteo](https://open-meteo.com/)
API and is licensed **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**.

Two Open-Meteo products are used, and they are kept strictly apart:

| Product | Endpoint | Underlying data | Used for |
|---|---|---|---|
| Historical archive | `archive-api.open-meteo.com/v1/archive` | **ERA5 / ERA5-Land** reanalysis | Training, live features, observed outcomes |
| Forecast | `api.open-meteo.com/v1/forecast` | Operational NWP (ECMWF IFS, ICON, …) | Open-Meteo's own forecast, as a benchmark only |

The reanalysis is produced by the **Copernicus Climate Change Service (C3S)** at the European
Centre for Medium-Range Weather Forecasts (**ECMWF**).

> Generated using Copernicus Climate Change Service information (2026).
>
> Neither the European Commission nor ECMWF is responsible for any use that may be made of the
> Copernicus information or data it contains.

## Why the benchmark is not a competitor

Open-Meteo's forecast is used here as an **operational reference**, the way a statistical baseline
is always reported against one in meteorology. It comes from full numerical weather prediction —
atmospheric physics on supercomputers, global data assimilation, ensembles. A 17-coefficient
logistic regression is not competing with that and is not expected to win on discrimination.

The interesting quantity is how much skill can be recovered from statistics alone, and where the
two differ once the Brier score is decomposed into reliability and resolution.

Two caveats travel with every use of their numbers:

1. **The events do not match.** `precipitation_probability_max` is the chance of rain at *some hour*
   of the day; the target here is *daily accumulation ≥ 1 mm*. The first is strictly more frequent,
   so scoring their probability against this target penalises them by construction. The
   like-for-like comparison is the deterministic one — their forecast accumulation against the
   same 1 mm rule.
2. **They forecast; we also verify.** Their product is generated for the whole world, continuously.
   Nothing here should be read as an evaluation of Open-Meteo's service.

## Code

The code in this repository is MIT licensed — see [`LICENSE`](LICENSE). The licences are separate
on purpose: MIT does not and cannot apply to the weather data.
