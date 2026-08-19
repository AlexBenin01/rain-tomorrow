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

FEATURES = [
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
}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def build_frame(csv_path: Path) -> pd.DataFrame:
    if not csv_path.is_file():
        raise SystemExit(f"missing {csv_path} — run src/fetch_weather.py first")
    df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)

    gaps = df["date"].diff().dt.days.dropna()
    if not (gaps == 1).all():
        raise SystemExit(f"{csv_path.name}: the series has gaps — refusing to train on it")

    wet = (df["rainfall_mm"] >= config.RAIN_THRESHOLD_MM).astype(int)
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
def train_location(location, train_split: str = "train", quiet: bool = False) -> dict:
    """Fit one location. `train_split` selects the training file, for the ablation."""
    frame = build_frame(ROOT / "data" / f"{location.key}_{train_split}.csv")
    test = build_frame(ROOT / "data" / f"{location.key}_test.csv")

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
    scaler_sel = StandardScaler().fit(train[FEATURES])
    ref_val = [bl_train["base_rate"]] * len(val)
    scores = {}
    for c in C_GRID:
        model = LogisticRegression(C=c, max_iter=2000).fit(scaler_sel.transform(train[FEATURES]),
                                                           y_train)
        probs = model.predict_proba(scaler_sel.transform(val[FEATURES]))[:, 1].tolist()
        scores[c] = metrics.brier_skill_score(probs, y_val, ref_val)
    best_c = max(scores, key=scores.get)
    say(f"  C selected on validation: {best_c}  (BSS {scores[best_c]:+.4f})")

    # --- final fit on train+validation; baselines refitted on the same data,
    #     otherwise the comparison is rigged in the model's favour
    fit_df = pd.concat([train, val], ignore_index=True)
    y_fit = fit_df["target"].tolist()
    bl = fit_baselines(fit_df)
    scaler = StandardScaler().fit(fit_df[FEATURES])

    lr = LogisticRegression(C=best_c, max_iter=2000).fit(scaler.transform(fit_df[FEATURES]), y_fit)
    gb = HistGradientBoostingClassifier(
        max_depth=3, max_iter=200, learning_rate=0.05, random_state=0
    ).fit(fit_df[FEATURES], y_fit)

    p_lr = lr.predict_proba(scaler.transform(test[FEATURES]))[:, 1].tolist()
    p_gb = gb.predict_proba(test[FEATURES])[:, 1].tolist()

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
        "best_c": best_c,
        "validation_scores": scores,
        "baselines": bl,
        "rows": rows,
        "coefficients": dict(zip(FEATURES, (float(c) for c in lr.coef_[0]))),
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
                "features": {f: float(test.iloc[i][f]) for f in FEATURES},
                "expected_probability": float(p_lr[i]),
            }
            for i in probe
        ],
    }


def write_artifact(result: dict) -> Path:
    location = result["location"]
    lr_row = next(r for r in result["rows"] if r["name"] == "logistic regression")
    artifact = {
        "schema_version": config.SCHEMA_VERSION,
        "model": "logistic_regression",
        "location": {
            "key": location.key, "name": location.name,
            "lat": location.lat, "lon": location.lon,
            "source": "Open-Meteo Archive / ERA5 (C3S-ECMWF), CC-BY 4.0",
        },
        "target": f"next-day precipitation >= {config.RAIN_THRESHOLD_MM} mm",
        "horizon_days": 1,
        "threshold_mm": config.RAIN_THRESHOLD_MM,
        "decision_threshold": config.DECISION_THRESHOLD,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "train_window": result["windows"]["train"],
        "validation_window": result["windows"]["validation"],
        "test_window": result["windows"]["test"],
        "regularization_C": result["best_c"],
        "feature_names": FEATURES,
        "coefficients": [result["coefficients"][f] for f in FEATURES],
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
                "name": r["name"],
                "brier": r["brier"],
                "bss": r["bss"],
                "POD": r["POD"],
                "FAR": r["FAR"],
                "CSI": r["CSI"],
                "hit_rate": r["hit_rate"],
                "roc_auc": r.get("roc_auc"),
                "pr_auc": r.get("pr_auc"),
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
    out = ROOT / "models" / f"{location.key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return out


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
    args = parser.parse_args()

    targets = locations.all_locations() if args.all else [locations.get(args.location)]
    results = [train_location(loc) for loc in targets]

    for result in results:
        path = write_artifact(result)
        print(f"  artefact -> {path.relative_to(ROOT)}")

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
        report_writer.write(results, ablation)
        print(f"\nreport -> reports/REPORT.md")

    return 0 if all(r["passed"] for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
