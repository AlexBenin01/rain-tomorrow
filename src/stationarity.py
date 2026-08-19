#!/usr/bin/env python3
"""Is the rainfall series stationary? The answer decided the training window.

This is not a side study. Training on 1996-2024 rather than 2016-2024 would give
a model tuned to a base rate that no longer exists, and the bias would show up on
every single day it ever forecast. The decision had to be made before any model
was fitted, so the analysis lives in its own module and runs on its own data
(the `analysis` split, which is never trained on).

What it computes, per location:

  * wet-day frequency by five-year period
  * the same frequency decomposed by intensity threshold, early period vs late
  * mean and median accumulation on wet days

The decomposition is what separates the two explanations. A drop concentrated in
light rain, monotone in intensity and reversing at the top, is the signature of
precipitation *intensification*: fewer wet days, same or more extreme events. A
change in how the reanalysis represents drizzle would show up only at the very
bottom and would not reverse.

    python src/stationarity.py --all
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import config
import locations

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = (0.2, 1.0, 5.0, 10.0, 20.0)
PERIODS = ((1996, 2000), (2001, 2005), (2006, 2010), (2011, 2015), (2016, 2020), (2021, 2024))
EARLY, LATE = (1996, 2005), (2016, 2024)


def load(location_key: str) -> list[tuple[str, float]]:
    path = ROOT / "data" / f"{location_key}_analysis.csv"
    if not path.is_file():
        raise SystemExit(
            f"missing {path.relative_to(ROOT)} — run:\n"
            f"  python src/fetch_weather.py --split analysis --location {location_key}"
        )
    with path.open(encoding="utf-8") as fh:
        return [(r["date"], float(r["rainfall_mm"])) for r in csv.DictReader(fh)]


def _slice(series, lo: int, hi: int) -> list[float]:
    return [mm for day, mm in series if lo <= int(day[:4]) <= hi]


def wet_fraction(values: list[float], threshold: float) -> float:
    return sum(1 for v in values if v >= threshold) / len(values) if values else float("nan")


def analyse(location_key: str) -> dict:
    series = load(location_key)

    by_period = []
    for lo, hi in PERIODS:
        values = _slice(series, lo, hi)
        by_period.append(
            {
                "period": f"{lo}-{hi}",
                "wet_fraction": round(wet_fraction(values, config.RAIN_THRESHOLD_MM), 4),
                "mm_per_year": round(sum(values) / (hi - lo + 1), 1),
            }
        )

    early, late = _slice(series, *EARLY), _slice(series, *LATE)
    decomposition = []
    for threshold in THRESHOLDS:
        a, b = wet_fraction(early, threshold), wet_fraction(late, threshold)
        decomposition.append(
            {
                "threshold_mm": threshold,
                "early": round(a, 4),
                "late": round(b, 4),
                "relative_change": round((b - a) / a, 4) if a else None,
            }
        )

    def intensity(values: list[float]) -> dict:
        wet = [v for v in values if v >= config.RAIN_THRESHOLD_MM]
        return {
            "mean_mm": round(statistics.mean(wet), 2),
            "median_mm": round(statistics.median(wet), 2),
        }

    # The signature test, stated as a claim the data can refuse:
    # light rain must fall more than heavy rain, and the extreme tail must not
    # fall at all. If either fails, "intensification" is not the right word.
    light = next(d for d in decomposition if d["threshold_mm"] == 1.0)["relative_change"]
    extreme = next(d for d in decomposition if d["threshold_mm"] == 20.0)["relative_change"]
    signature = light is not None and extreme is not None and light < -0.05 and extreme > light

    return {
        "location": location_key,
        "name": locations.get(location_key).name,
        "by_period": by_period,
        "early_window": f"{EARLY[0]}-{EARLY[1]}",
        "late_window": f"{LATE[0]}-{LATE[1]}",
        "decomposition": decomposition,
        "intensity_early": intensity(early),
        "intensity_late": intensity(late),
        "wet_fraction_full": round(wet_fraction([mm for _, mm in series],
                                                config.RAIN_THRESHOLD_MM), 4),
        "wet_fraction_late": round(wet_fraction(late, config.RAIN_THRESHOLD_MM), 4),
        "intensification_signature": signature,
    }


def report(result: dict) -> None:
    print(f"\n=== {result['name']} ===")
    print(f"  {'period':<12}{'wet days':>10}{'mm/yr':>9}")
    for p in result["by_period"]:
        print(f"  {p['period']:<12}{p['wet_fraction']:>9.1%}{p['mm_per_year']:>9.0f}")

    print(f"\n  by intensity, {result['early_window']} -> {result['late_window']}:")
    print(f"  {'threshold':<12}{'early':>8}{'late':>8}{'change':>10}")
    for d in result["decomposition"]:
        change = "—" if d["relative_change"] is None else f"{d['relative_change']:+.0%}"
        print(f"  >= {d['threshold_mm']:<9.1f}{d['early']:>7.1%}{d['late']:>8.1%}{change:>10}")

    a, b = result["intensity_early"], result["intensity_late"]
    print(f"\n  mean on wet days : {a['mean_mm']} -> {b['mean_mm']} mm"
          f"   (median {a['median_mm']} -> {b['median_mm']})")
    print(f"  intensification signature: "
          f"{'YES' if result['intensification_signature'] else 'no'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--location")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    keys = locations.DEFAULT_ORDER if args.all else [locations.get(args.location).key]
    results = [analyse(k) for k in keys]
    for r in results:
        report(r)

    if args.all:
        print("\n=== the gradient ===")
        print(f"  {'location':<22}{'1996-2024':>11}{'2016-2024':>11}{'change':>10}{'signature':>12}")
        for r in results:
            delta = r["wet_fraction_late"] - r["wet_fraction_full"]
            print(f"  {r['name']:<22}{r['wet_fraction_full']:>10.1%}"
                  f"{r['wet_fraction_late']:>11.1%}{delta:>+10.1%}"
                  f"{'YES' if r['intensification_signature'] else 'no':>12}")

        out = ROOT / "reports" / "stationarity.json"
        out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
