"""Project-wide invariants.

These constants are deliberately **global**, never per-location. The train/test
separation is the guarantee the whole project rests on: if it could vary by
city, it would eventually vary by accident.
"""
from datetime import date

# --- temporal invariants ---------------------------------------------------
# Training and validation stop here. Everything the model is ever tested on, and
# every day it forecasts in production, lies strictly after this date.
TRAIN_END_DATE = date(2024, 12, 31)
# The recent precipitation regime starts here. Before 2016 the wet-day frequency
# is ~14 points higher and a model trained on it would be tuned to a climate that
# no longer exists — see reports/METHOD_NOTES.md.
TRAIN_START_DATE = date(2016, 1, 1)
# Long window used ONLY for the stationarity analysis, never for training.
ANALYSIS_START_DATE = date(1996, 1, 1)
# Last year of training is held out to choose hyper-parameters.
VALIDATION_YEAR = 2024

# --- event definition ------------------------------------------------------
# 1 mm separates an agronomically meaningful event from a trace. Declared before
# measuring anything.
RAIN_THRESHOLD_MM = 1.0
DECISION_THRESHOLD = 0.5

# --- leaf wetness proxy (standard in viticulture literature) ---------------
LEAF_WETNESS_RH_PCT = 90.0
LEAF_WETNESS_RAIN_MM = 0.2

# --- Open-Meteo ------------------------------------------------------------
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/Rome"
HTTP_TIMEOUT_S = 120
# The free tier meters by request weight: one 29-year hourly pull can trip the
# per-minute limit by itself. Backoff base, multiplied by the attempt number.
RATE_LIMIT_WAIT_S = 65

# Daily variables pulled from the reanalysis. Order is irrelevant here; the
# model's feature order lives in the artefact.
DAILY_VARS = [
    "precipitation_sum",
    "temperature_2m_min",
    "temperature_2m_max",
    "relative_humidity_2m_mean",
    "pressure_msl_mean",
    "wind_speed_10m_mean",
    "wind_direction_10m_dominant",
    "cloud_cover_mean",
]
HOURLY_VARS = ["relative_humidity_2m", "precipitation"]

# Open-Meteo's own forecast, used as the operational benchmark.
FORECAST_VARS = [
    "precipitation_sum",
    "precipitation_probability_max",
    "precipitation_probability_mean",
]

# CSV column name -> Open-Meteo response name
COLUMN_MAP = {
    "rainfall_mm": "precipitation_sum",
    "temp_min": "temperature_2m_min",
    "temp_max": "temperature_2m_max",
    "humidity_pct": "relative_humidity_2m_mean",
    "pressure_hpa": "pressure_msl_mean",
    "wind_speed_kmh": "wind_speed_10m_mean",
    "wind_dir_deg": "wind_direction_10m_dominant",
    "cloud_pct": "cloud_cover_mean",
}

CSV_FIELDS = ["date", *COLUMN_MAP.keys(), "leaf_wetness_h"]

# --- paths -----------------------------------------------------------------
SCHEMA_VERSION = 1
LEDGER_PATH = "public/forecasts.jsonl"
