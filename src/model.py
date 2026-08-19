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


class Model:
    """One location's model, loaded from its artefact."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.location = payload["location"]
        self.features = payload["feature_names"]
        self.coefficients = payload["coefficients"]
        self.intercept = payload["intercept"]
        self.mean = payload["scaler_mean"]
        self.scale = payload["scaler_scale"]
        self.threshold_mm = payload["threshold_mm"]
        self.decision_threshold = payload["decision_threshold"]
        self.monthly_climatology = {int(k): v for k, v in payload["monthly_climatology"].items()}
        self.base_rate = payload["base_rate"]
        self.reference_vectors = payload.get("reference_vectors", [])
        self.version = f"lr-v{payload['schema_version']}@{payload['trained_at'][:10]}"

    @classmethod
    def load(cls, location_key: str) -> "Model":
        path = ROOT / "models" / f"{location_key}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"no model for {location_key!r} — run: python src/train.py --location {location_key}"
            )
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def predict(self, features: dict[str, float]) -> float:
        z = self.intercept
        for name, coef, mu, sigma in zip(
            self.features, self.coefficients, self.mean, self.scale
        ):
            z += coef * (features[name] - mu) / (sigma or 1.0)
        return _sigmoid(z)

    def climatology(self, month: int) -> float:
        return self.monthly_climatology.get(month, self.base_rate)

    def self_check(self, tolerance: float = 1e-9) -> None:
        """Reproduce the training output on the stored reference vectors.

        Cheap insurance against a silently mismatched artefact: if the feature
        order, the scaler or the sigmoid ever drift, this fails immediately
        rather than after weeks of quietly wrong forecasts.
        """
        for i, case in enumerate(self.reference_vectors):
            got = self.predict(case["features"])
            if abs(got - case["expected_probability"]) > tolerance:
                raise ValueError(
                    f"{self.location['key']}: reference vector {i} gives {got}, "
                    f"expected {case['expected_probability']}"
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
