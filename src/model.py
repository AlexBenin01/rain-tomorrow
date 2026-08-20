"""Inference. A serialised logistic regression is a vector of coefficients.

Standardise, sum, apply a sigmoid — that is the whole model. No scikit-learn, no
numpy, no pandas: the artefact is a ~10 KB JSON produced offline by src/train.py,
and this module is the only thing needed to use it.

That property is what lets the same model run in a GitHub Action with no
`pip install` at all, and be re-implemented in twenty lines of JavaScript so the
published page can verify it in the reader's browser.
"""
import csv
import json
import math
from datetime import date
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent


def _sigmoid(z: float) -> float:
    """Numerically stable logistic function.

    The textbook form `1 / (1 + exp(-z))` overflows for strongly negative z:
    exp(710) is beyond a float64. It never happens on real weather, which is
    precisely why it would have been found in production rather than in a test.
    Branching on the sign keeps the exponent negative on both paths.
    """
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


class Threshold:
    """One intensity threshold: its own coefficients, scaler and climatology."""

    def __init__(self, block: dict, feature_names: list[str]):
        self.mm = block["threshold_mm"]
        self.features = feature_names
        self.coefficients = block["coefficients"]
        self.intercept = block["intercept"]
        self.mean = block["scaler_mean"]
        self.scale = block["scaler_scale"]
        self.monthly_climatology = {int(k): v for k, v in block["monthly_climatology"].items()}
        self.base_rate = block["base_rate"]
        self.reference_vectors = block.get("reference_vectors", [])
        self.shipped = block.get("shipped", True)

    def predict(self, features: dict[str, float]) -> float:
        z = self.intercept
        for name, coef, mu, sigma in zip(
            self.features, self.coefficients, self.mean, self.scale
        ):
            z += coef * (features[name] - mu) / (sigma or 1.0)
        return _sigmoid(z)

    def climatology(self, month: int) -> float:
        return self.monthly_climatology.get(month, self.base_rate)


class Model:
    """One location's models, loaded from its artefact.

    Carries one logistic regression per intensity threshold. They are fitted
    independently, so nothing stops P(>= 5 mm) coming out above P(>= 1 mm) on
    some day — which is impossible, and would destroy the credibility of every
    other number on the page. `predict_all` enforces the ordering.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.location = payload["location"]
        self.features = payload["feature_names"]
        self.decision_threshold = payload["decision_threshold"]
        self.version = f"lr-v{payload['schema_version']}@{payload['trained_at'][:10]}"

        blocks = payload["thresholds"]
        self.thresholds = {
            float(k): Threshold(v, self.features) for k, v in blocks.items()
        }
        self.shipped_mm = sorted(mm for mm, t in self.thresholds.items() if t.shipped)
        # the headline event, and the one the ledger has always recorded
        self.primary = self.thresholds[min(self.thresholds)]
        self.threshold_mm = self.primary.mm

    @classmethod
    def load(cls, location_key: str) -> "Model":
        path = ROOT / "models" / f"{location_key}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"no model for {location_key!r} — run: python src/train.py --all --thresholds"
            )
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def predict(self, features: dict[str, float]) -> float:
        """The headline probability: at least 1 mm."""
        return self.primary.predict(features)

    def predict_all(self, features: dict[str, float]) -> dict[float, float]:
        """Every shipped threshold, in order, with the ordering enforced.

        Clamping downwards rather than upwards is deliberate: the lower
        threshold is the better-estimated one (many more events), so where the
        two disagree it is the one to trust.
        """
        out: dict[float, float] = {}
        ceiling = 1.0
        for mm in self.shipped_mm:
            probability = min(self.thresholds[mm].predict(features), ceiling)
            out[mm] = probability
            ceiling = probability
        return out

    def climatology(self, month: int) -> float:
        return self.primary.climatology(month)

    def self_check(self, tolerance: float = 1e-9) -> None:
        """Reproduce the training output on the stored reference vectors.

        Checks EVERY threshold, not just the headline one: a mismatch in the
        10 mm model would otherwise go unnoticed until someone read the page.
        """
        for mm, threshold in sorted(self.thresholds.items()):
            for i, case in enumerate(threshold.reference_vectors):
                got = threshold.predict(case["features"])
                if abs(got - case["expected_probability"]) > tolerance:
                    raise ValueError(
                        f"{self.location['key']} at {mm:g} mm: reference vector {i} "
                        f"gives {got}, expected {case['expected_probability']}"
                    )


def build_features(history: list[dict], target_day: date, threshold_mm: float) -> dict | None:
    """Features from the daily rows, ascending by date and ending on 'today'.

    Needs at least 7 days: without them `wet_days_last_7` and the 1- and 2-day
    differences cannot be computed, and returning None is better than inventing
    a value.

    The target day enters ONLY as a day-of-year, for the annual cycle. Nothing
    about the weather being predicted is ever available to the model.
    """
    if len(history) < 7:
        return None
    today, yesterday, before = history[-1], history[-2], history[-3]

    def tmean(row: dict) -> float:
        return (row["temp_min"] + row["temp_max"]) / 2.0

    doy = target_day.timetuple().tm_yday
    wind = math.radians(today["wind_dir_deg"])

    return {
        "rain_today_log": math.log1p(today["rainfall_mm"]),
        "rained_today": 1.0 if today["rainfall_mm"] >= threshold_mm else 0.0,
        "wet_days_last_7": float(
            sum(1 for r in history[-7:] if r["rainfall_mm"] >= threshold_mm)
        ),
        "rh_today": today["humidity_pct"],
        "d_rh_1d": today["humidity_pct"] - yesterday["humidity_pct"],
        "tmean_today": tmean(today),
        "d_tmean_1d": tmean(today) - tmean(yesterday),
        "leaf_wetness_today": today["leaf_wetness_h"],
        "pressure_today": today["pressure_hpa"],
        "d_pressure_1d": today["pressure_hpa"] - yesterday["pressure_hpa"],
        "d_pressure_2d": today["pressure_hpa"] - before["pressure_hpa"],
        "cloud_today": today["cloud_pct"],
        # meteorological convention: the direction the wind blows FROM
        "wind_from_south": -math.cos(wind),
        "wind_from_east": math.sin(wind),
        "wind_speed": today["wind_speed_kmh"],
        "sin_doy": math.sin(2 * math.pi * doy / 365.25),
        "cos_doy": math.cos(2 * math.pi * doy / 365.25),
        # The shape of the day. Computed once at fetch time from the hourly
        # series (src/sources.py:intraday_features) and carried in the CSV, so
        # training and the daily run read exactly the same numbers.
        **{name: today[name] for name in config.INTRADAY_FIELDS},
    }


def load_csv(path: Path) -> list[dict]:
    """Read a data CSV into float rows, keeping `date` as a string."""
    with path.open(encoding="utf-8") as fh:
        rows = []
        for record in csv.DictReader(fh):
            row = {"date": record["date"]}
            for key, value in record.items():
                if key != "date":
                    row[key] = float(value)
            rows.append(row)
    return rows
