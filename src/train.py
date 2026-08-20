#!/usr/bin/env python3
"""Fit the next-day rain model for one location, or for all of them.

Protocol, in this order — the baselines come BEFORE the model, because without
them there is no way to know whether the model is worth anything:

  1. baselines    constant climatology, monthly climatology, raw persistence,
                  calibrated persistence (a two-state Markov chain)
  2. split        train 2016-2023 | validation 2024 | test everything after 2024
  3. selection    regularisation chosen on the VALIDATION year only. The test set
                  is touched once, at the end, and never again
  4. models       logistic regression (primary), gradient boosting (comparison)
  5. verdict      the stop criterion is applied before anything is serialised

Stop criterion, fixed in writing before any number was seen:

    the model must beat CALIBRATED PERSISTENCE by at least 0.05 of Brier Skill
    Score on the held-out test set.

It is deliberately relative rather than an absolute threshold. Calibrated
persistence is a three-line Markov chain and already scores well; beating
climatology proves nothing, beating persistence does. An absolute number would
also have to differ per location, which invites tuning.

    python src/train.py --location vicenza
    python src/train.py --all
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

import config
import locations
import metrics
import report as report_writer

ROOT = Path(__file__).resolve().parent.parent

MIN_GAIN_OVER_PERSISTENCE = 0.05
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0)

# v1: everything derivable from daily aggregates.
FEATURES_DAILY = [
    "rain_today_log",
    "rained_today",
    "wet_days_last_7",
    "rh_today",
    "d_rh_1d",
    "tmean_today",
    "d_tmean_1d",
    "leaf_wetness_today",
    "pressure_today",
    "d_pressure_1d",
    "d_pressure_2d",
    "cloud_today",
    "wind_from_south",
    "wind_from_east",
    "wind_speed",
    "sin_doy",
    "cos_doy",
]

# v2 adds the SHAPE of the day, which the daily means throw away.
FEATURES_INTRADAY = [
    "d_pressure_intraday",
    "pressure_drop_today",
    "cloud_evening",
    "cloud_trend",
    "dewpoint_depression_pm",
    "wind_veer",
    "precip_hours_today",
    "rh_evening_excess",
]

FEATURE_SETS = {
    "daily": FEATURES_DAILY,
    "full": FEATURES_DAILY + FEATURES_INTRADAY,
}
FEATURES = FEATURE_SETS["full"]

FEATURE_GLOSS = {
    "rain_today_log": "today's rain, log(1+mm) — the strongest single predictor",
    "rained_today": "did it rain today (>= 1 mm) — persistence, in binary form",
    "wet_days_last_7": "wet days in the last 7 — the state of the regime",
    "rh_today": "today's mean relative humidity",
    "d_rh_1d": "change in humidity since yesterday — the trend",
    "tmean_today": "today's mean temperature",
    "d_tmean_1d": "temperature change since yesterday — pre-frontal warm advection",
    "leaf_wetness_today": "hours of leaf wetness today",
    "pressure_today": "mean sea-level pressure — low means unsettled",
    "d_pressure_1d": "**24-hour pressure tendency** — falling means a front is coming",
    "d_pressure_2d": "48-hour pressure tendency — how long it has been falling",
    "cloud_today": "today's mean cloud cover",
    "wind_from_south": "southerly wind component — warm, moist pre-frontal flow",
    "wind_from_east": "easterly wind component — moisture drawn off the Adriatic",
    "wind_speed": "mean wind speed",
    "sin_doy": "annual cycle (sine)",
    "cos_doy": "annual cycle (cosine)",
    "d_pressure_intraday": "pressure at 18:00 minus 06:00 — the fall *within* the day",
    "pressure_drop_today": "how far pressure dipped below its own daily mean",
    "cloud_evening": "mean cloud 15-21, the state the day closes on",
    "cloud_trend": "evening cloud minus morning cloud — clouding over, or clearing",
    "dewpoint_depression_pm": "mean (T − dew point) 12-18 — low-level moisture",
    "wind_veer": "signed wind rotation morning → evening — frontal passage",
    "precip_hours_today": "hours with rain: a downpour and drizzle differ at equal mm",
    "rh_evening_excess": "evening humidity above the daily mean",
}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def build_frame(csv_path: Path, threshold_mm: float = config.RAIN_THRESHOLD_MM) -> pd.DataFrame:
    if not csv_path.is_file():
        raise SystemExit(f"missing {csv_path} — run src/fetch_weather.py first")
    df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)

    gaps = df["date"].diff().dt.days.dropna()
    if not (gaps == 1).all():
        raise SystemExit(f"{csv_path.name}: the series has gaps — refusing to train on it")

    # `wet` drives the persistence features; `target` is the event being predicted.
    # They use the same threshold so "it rained today" means the same thing as
    # "it rains tomorrow" for whichever intensity is being modelled.
    wet = (df["rainfall_mm"] >= threshold_mm).astype(int)
    tmean = (df["temp_min"] + df["temp_max"]) / 2.0
    doy = df["date"].dt.dayofyear

    df["rain_today_log"] = np.log1p(df["rainfall_mm"])
    df["rained_today"] = wet
    # includes today: it is the information available when the forecast is issued
    df["wet_days_last_7"] = wet.rolling(7, min_periods=7).sum()
    df["rh_today"] = df["humidity_pct"]
    df["d_rh_1d"] = df["humidity_pct"].diff()
    df["tmean_today"] = tmean
    df["d_tmean_1d"] = tmean.diff()
    df["leaf_wetness_today"] = df["leaf_wetness_h"]
    df["pressure_today"] = df["pressure_hpa"]
    df["d_pressure_1d"] = df["pressure_hpa"].diff()
    df["d_pressure_2d"] = df["pressure_hpa"].diff(2)
    df["cloud_today"] = df["cloud_pct"]
    # a direction is an angle: decomposed, or 359 and 1 look far apart.
    # Meteorological convention: the direction the wind blows FROM.
    wind = np.deg2rad(df["wind_dir_deg"])
    df["wind_from_south"] = -np.cos(wind)
    df["wind_from_east"] = np.sin(wind)
    df["wind_speed"] = df["wind_speed_kmh"]
    df["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    df["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    # the intra-day features arrive as CSV columns already, computed at fetch
    # time from the hourly series — see src/sources.py:intraday_features

    # the target is TOMORROW: no feature may look past today
    df["target"] = wet.shift(-1)
    df["target_date"] = df["date"].shift(-1)

    return df.dropna(subset=FEATURES + ["target"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Baselines — before the model, always
# --------------------------------------------------------------------------
def fit_baselines(frame: pd.DataFrame) -> dict:
    return {
        "base_rate": float(frame["target"].mean()),
        "monthly": {
            int(m): float(g["target"].mean())
            for m, g in frame.groupby(frame["target_date"].dt.month)
        },
        "markov": {
            int(s): float(frame.loc[frame["rained_today"] == s, "target"].mean())
            for s in (0, 1)
        },
    }


def apply_baselines(bl: dict, frame: pd.DataFrame) -> dict[str, list[float]]:
    months = frame["target_date"].dt.month.to_numpy()
    return {
        "constant climatology": [bl["base_rate"]] * len(frame),
        "monthly climatology": [bl["monthly"][int(m)] for m in months],
        "raw persistence (0/1)": [float(s) for s in frame["rained_today"]],
        "calibrated persistence": [bl["markov"][int(s)] for s in frame["rained_today"]],
    }


def evaluate(name: str, probs: list[float], outcomes: list[float], ref: list[float]) -> dict:
    probs = [min(max(p, 1e-6), 1 - 1e-6) for p in probs]
    row = {
        "name": name,
        "brier": metrics.brier_score(probs, outcomes),
        "bss": metrics.brier_skill_score(probs, outcomes, ref),
        **metrics.contingency(probs, outcomes, config.DECISION_THRESHOLD),
    }
    if len(set(probs)) > 1:
        row["roc_auc"] = float(roc_auc_score(outcomes, probs))
        row["pr_auc"] = float(average_precision_score(outcomes, probs))
    return row


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
def train_location(location, train_split: str = "train", quiet: bool = False,
                   feature_set: str = "full",
                   threshold_mm: float = config.RAIN_THRESHOLD_MM) -> dict:
    """Fit one location.

    `train_split` selects the training file (for the window ablation);
    `feature_set` selects which predictors are available, so v1 and v2 can be
    compared with everything else held identical.
    """
    features = FEATURE_SETS[feature_set]
    frame = build_frame(ROOT / "data" / f"{location.key}_{train_split}.csv", threshold_mm)
    test = build_frame(ROOT / "data" / f"{location.key}_test.csv", threshold_mm)

    train = frame[frame["date"].dt.year < config.VALIDATION_YEAR].reset_index(drop=True)
    val = frame[frame["date"].dt.year == config.VALIDATION_YEAR].reset_index(drop=True)

    if test["date"].min().date() <= config.TRAIN_END_DATE:
        raise SystemExit("INVARIANT VIOLATED: the test set reaches into the training period")

    say = (lambda *a: None) if quiet else print
    say(f"\n=== {location.name} ===")
    say(f"  train      {train['date'].min().date()} -> {train['date'].max().date()}  "
        f"n={len(train):5d}  base rate {train['target'].mean():.3f}")
    say(f"  validation {val['date'].min().date()} -> {val['date'].max().date()}  "
        f"n={len(val):5d}  base rate {val['target'].mean():.3f}")
    say(f"  test       {test['date'].min().date()} -> {test['date'].max().date()}  "
        f"n={len(test):5d}  base rate {test['target'].mean():.3f}")

    y_train = train["target"].tolist()
    y_val = val["target"].tolist()
    y_test = test["target"].tolist()

    # --- regularisation chosen on the validation year, never on the test set
    bl_train = fit_baselines(train)
    scaler_sel = StandardScaler().fit(train[features])
    ref_val = [bl_train["base_rate"]] * len(val)
    scores = {}
    for c in C_GRID:
        model = LogisticRegression(C=c, max_iter=2000).fit(scaler_sel.transform(train[features]),
                                                           y_train)
        probs = model.predict_proba(scaler_sel.transform(val[features]))[:, 1].tolist()
        scores[c] = metrics.brier_skill_score(probs, y_val, ref_val)
    best_c = max(scores, key=scores.get)
    say(f"  C selected on validation: {best_c}  (BSS {scores[best_c]:+.4f})")

    # --- final fit on train+validation; baselines refitted on the same data,
    #     otherwise the comparison is rigged in the model's favour
    fit_df = pd.concat([train, val], ignore_index=True)
    y_fit = fit_df["target"].tolist()
    bl = fit_baselines(fit_df)
    scaler = StandardScaler().fit(fit_df[features])

    lr = LogisticRegression(C=best_c, max_iter=2000).fit(scaler.transform(fit_df[features]), y_fit)
    gb = HistGradientBoostingClassifier(
        max_depth=3, max_iter=200, learning_rate=0.05, random_state=0
    ).fit(fit_df[features], y_fit)

    p_lr = lr.predict_proba(scaler.transform(test[features]))[:, 1].tolist()
    p_gb = gb.predict_proba(test[features])[:, 1].tolist()

    ref_test = [bl["base_rate"]] * len(test)
    rows = [evaluate(k, v, y_test, ref_test) for k, v in apply_baselines(bl, test).items()]
    rows.append(evaluate("logistic regression", p_lr, y_test, ref_test))
    rows.append(evaluate("gradient boosting", p_gb, y_test, ref_test))

    lr_row = next(r for r in rows if r["name"] == "logistic regression")
    persistence = next(r for r in rows if r["name"] == "calibrated persistence")
    gain = lr_row["bss"] - persistence["bss"]
    passed = gain >= MIN_GAIN_OVER_PERSISTENCE

    say(f"  BSS {lr_row['bss']:+.3f} vs climatology, "
        f"{gain:+.3f} over calibrated persistence -> "
        f"{'PASS' if passed else 'FAIL'}")

    sweep = [
        metrics.contingency(p_lr, y_test, t) for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
    ]
    probe = np.linspace(0, len(test) - 1, 5, dtype=int)

    return {
        "location": location,
        "threshold_mm": threshold_mm,
        "features": features,
        "feature_set": feature_set,
        "best_c": best_c,
        "validation_scores": scores,
        "baselines": bl,
        "rows": rows,
        "coefficients": dict(zip(features, (float(c) for c in lr.coef_[0]))),
        "intercept": float(lr.intercept_[0]),
        "scaler_mean": [float(v) for v in scaler.mean_],
        "scaler_scale": [float(v) for v in scaler.scale_],
        "gain": gain,
        "passed": passed,
        "windows": {
            "train": [str(train["date"].min().date()), str(train["date"].max().date())],
            "validation": [str(val["date"].min().date()), str(val["date"].max().date())],
            "test": [str(test["date"].min().date()), str(test["date"].max().date())],
        },
        "sizes": {"train": len(train), "validation": len(val), "test": len(test)},
        "base_rates": {
            "train": float(train["target"].mean()),
            "test": float(test["target"].mean()),
        },
        "reliability": metrics.reliability_curve(p_lr, y_test, bins=5, min_count=10),
        "decomposition": metrics.brier_decomposition(p_lr, y_test),
        "threshold_sweep": sweep,
        "test_probabilities": [round(p, 4) for p in p_lr],
        "test_dates": [d.date().isoformat() for d in test["target_date"]],
        "test_outcomes": [int(o) for o in y_test],
        "test_rainfall": [float(v) for v in test["rainfall_mm"].shift(-1).fillna(0)],
        "reference_vectors": [
            {
                "features": {f: float(test.iloc[i][f]) for f in features},
                "expected_probability": float(p_lr[i]),
            }
            for i in probe
        ],
    }


def _threshold_block(result: dict) -> dict:
    """Everything specific to one intensity threshold."""
    lr_row = next(r for r in result["rows"] if r["name"] == "logistic regression")
    return {
        "threshold_mm": result["threshold_mm"],
        "target": f"next-day precipitation >= {result['threshold_mm']:g} mm",
        "regularization_C": result["best_c"],
        "coefficients": [result["coefficients"][f] for f in result["features"]],
        "intercept": result["intercept"],
        "scaler_mean": result["scaler_mean"],
        "scaler_scale": result["scaler_scale"],
        "monthly_climatology": {str(k): v for k, v in result["baselines"]["monthly"].items()},
        "base_rate": result["baselines"]["base_rate"],
        "test_metrics": {k: v for k, v in lr_row.items() if k != "name"},
        # every forecaster scored on the same test set, so the published page can
        # show the ladder without having to re-derive the baselines itself
        "test_comparison": [
            {
                "name": r["name"], "brier": r["brier"], "bss": r["bss"],
                "POD": r["POD"], "FAR": r["FAR"], "CSI": r["CSI"],
                "hit_rate": r["hit_rate"],
                "roc_auc": r.get("roc_auc"), "pr_auc": r.get("pr_auc"),
            }
            for r in result["rows"]
        ],
        "reliability": result["reliability"],
        "brier_decomposition": result["decomposition"],
        "threshold_sweep": result["threshold_sweep"],
        "stop_criterion": {
            "rule": "BSS gain over calibrated persistence >= 0.05 on the held-out test set",
            "min_gain": MIN_GAIN_OVER_PERSISTENCE,
            "achieved_gain": result["gain"],
            "passed": bool(result["passed"]),
        },
        "reference_vectors": result["reference_vectors"],
    }


def write_artifact(results: list[dict]) -> Path:
    """One artefact per location, carrying every threshold that earned its place.

    A threshold that fails the stop criterion is recorded but marked `shipped:
    false`, so the reason it is absent from the page stays in the file rather
    than only in someone's memory.
    """
    first = results[0]
    location = first["location"]
    artifact = {
        "schema_version": config.SCHEMA_VERSION,
        "model": "logistic_regression",
        "location": {
            "key": location.key, "name": location.name,
            "lat": location.lat, "lon": location.lon,
            "source": "Open-Meteo Archive / ERA5 (C3S-ECMWF), CC-BY 4.0",
        },
        "horizon_days": 1,
        "decision_threshold": config.DECISION_THRESHOLD,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "train_window": first["windows"]["train"],
        "validation_window": first["windows"]["validation"],
        "test_window": first["windows"]["test"],
        "feature_names": first["features"],
        "feature_set": first["feature_set"],
        "thresholds": {},
    }
    for result in results:
        block = _threshold_block(result)
        block["shipped"] = bool(result["passed"])
        artifact["thresholds"][f"{result['threshold_mm']:g}"] = block

    artifact["shipped_thresholds"] = [
        k for k, v in artifact["thresholds"].items() if v["shipped"]
    ]
    out = ROOT / "models" / f"{location.key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return out


def feature_ablation(location) -> dict:
    """Does the shape of the day add anything the daily means do not?

    Both variants trained with everything else held identical — same split, same
    grid, same test set, same protocol — so the difference is attributable to the
    features and to nothing else.
    """
    v1 = train_location(location, feature_set="daily", quiet=True)
    v2 = train_location(location, feature_set="full", quiet=True)

    def bss(result):
        return next(r for r in result["rows"] if r["name"] == "logistic regression")["bss"]

    return {
        "location": location.name,
        "daily": {"n_features": len(v1["features"]), "bss": bss(v1), "C": v1["best_c"]},
        "full": {"n_features": len(v2["features"]), "bss": bss(v2), "C": v2["best_c"]},
        "gain": bss(v2) - bss(v1),
    }


def window_ablation(location) -> dict:
    """Does the uniform 2016 window cost skill where the regime is stable?

    Asked rather than assumed. Trained both ways, compared on the same held-out
    test set. Whatever comes out is what gets reported.
    """
    long_csv = ROOT / "data" / f"{location.key}_train_long.csv"
    if not long_csv.is_file():
        raise SystemExit(
            f"missing {long_csv.name} — run:\n"
            f"  python src/fetch_weather.py --split train_long --location {location.key}"
        )
    short = train_location(location, quiet=True)
    long = train_location(location, train_split="train_long", quiet=True)

    def bss(result):
        return next(r for r in result["rows"] if r["name"] == "logistic regression")["bss"]

    return {
        "location": location.name,
        "short_window": {"start": "2016-01-01", "n": short["sizes"]["train"], "bss": bss(short)},
        "long_window": {"start": "1996-01-01", "n": long["sizes"]["train"], "bss": bss(long)},
        "difference": bss(long) - bss(short),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--location")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--ablation", metavar="LOCATION",
                        help="also train this location on the long window and compare")
    parser.add_argument("--feature-set", choices=list(FEATURE_SETS), default="full",
                        help="which predictors the model may use")
    parser.add_argument("--thresholds", action="store_true",
                        help="train every intensity threshold, not just 1 mm")
    parser.add_argument("--compare-features", action="store_true",
                        help="train daily-only and full side by side, and report the difference")
    args = parser.parse_args()

    targets = locations.all_locations() if args.all else [locations.get(args.location)]

    if args.compare_features:
        print("=== does the shape of the day help? ===")
        print(f"  {'location':<20}{'v1 daily':>11}{'v2 + shape':>13}{'gain':>10}{'C':>8}")
        gains = []
        for loc in targets:
            a = feature_ablation(loc)
            gains.append(a["gain"])
            print(f"  {loc.name:<20}{a['daily']['bss']:>+11.4f}{a['full']['bss']:>+13.4f}"
                  f"{a['gain']:>+10.4f}{a['full']['C']:>8}")
        mean_gain = sum(gains) / len(gains)
        wins = sum(1 for g in gains if g > 0)
        print("")
        print(f"  mean gain {mean_gain:+.4f}, better at {wins}/{len(gains)} locations")
        print("  -> " + ("keep v2" if mean_gain > 0 and wins > len(gains) / 2
                         else "KEEP v1: the extra features do not earn their place"))
        return 0

    thresholds = config.INTENSITY_THRESHOLDS if args.thresholds else [config.RAIN_THRESHOLD_MM]
    per_location = {}
    for loc in targets:
        per_location[loc.key] = [
            train_location(loc, feature_set=args.feature_set, threshold_mm=t)
            for t in thresholds
        ]

    print("")
    print("=== which thresholds earned their place ===")
    print(f"  {'location':<20}" + "".join(f"{t:g} mm".rjust(12) for t in thresholds))
    for loc in targets:
        cells = ""
        for r in per_location[loc.key]:
            mark = "PASS" if r["passed"] else "no"
            cells += f"{r['gain']:+.3f} {mark}".rjust(12)
        print(f"  {loc.name:<20}{cells}")

    for loc in targets:
        path = write_artifact(per_location[loc.key])
        shipped = sum(1 for r in per_location[loc.key] if r["passed"])
        print(f"  artefact -> {path.relative_to(ROOT)}  ({shipped}/{len(thresholds)} shipped)")

    results = [per_location[loc.key][0] for loc in targets]

    ablation = None
    if args.ablation:
        print(f"\n=== window ablation: {args.ablation} ===")
        ablation = window_ablation(locations.get(args.ablation))
        s, l = ablation["short_window"], ablation["long_window"]
        print(f"  2016 window: n={s['n']:5d}  BSS {s['bss']:+.4f}")
        print(f"  1996 window: n={l['n']:5d}  BSS {l['bss']:+.4f}")
        print(f"  difference : {ablation['difference']:+.4f} in favour of "
              f"{'the long window' if ablation['difference'] > 0 else 'the short window'}")

    if args.all:
        gains = [feature_ablation(loc) for loc in targets] if args.thresholds else None
        report_writer.write(
            results, ablation,
            thresholds={loc.name: per_location[loc.key] for loc in targets}
            if args.thresholds else None,
            feature_gain=gains,
        )
        print(f"\nreport -> reports/REPORT.md")

    return 0 if all(r["passed"] for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
