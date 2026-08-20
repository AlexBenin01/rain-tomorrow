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

# "Will it rain" is half the question. These are the intensities the model is
# also asked about, as exceedance probabilities: P(tomorrow >= X mm).
#
# Chosen for what they mean on the ground rather than for statistical
# convenience: 1 mm separates an event from a trace, 5 mm is a proper wet day,
# 10 mm is enough to interrupt outdoor work, 20 mm is heavy.
#
# The last one is declared FRAGILE before it is trained: it fires on 3-5% of
# days, which is 106 examples at Padova. If it fails the stop criterion it is
# not shipped, and the report says why.
INTENSITY_THRESHOLDS = [1.0, 5.0, 10.0, 20.0]

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
# Hourly series. Two of them feed the leaf-wetness proxy; the rest exist to
# recover the SHAPE of the day, which a daily mean throws away. Verified that
# the archive serves all of these 24/24 (`cape` is empty in the archive, so it
# is not an option).
HOURLY_VARS = [
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "wind_direction_10m",
    "temperature_2m",
    "dew_point_2m",
]

# Derived from the hourly series at fetch time and stored in the CSV, so the
# training pipeline and the daily run read them the same way.
#
# Two of them are expressed as DEVIATIONS rather than levels: an evening
# humidity level would be almost collinear with the daily mean already in the
# model, whereas the excess over that mean is information the mean cannot carry.
INTRADAY_FIELDS = [
    "d_pressure_intraday",   # pressure at 18:00 minus pressure at 06:00
    "pressure_drop_today",   # daily mean minus daily minimum: how far it dipped
    "cloud_evening",         # mean cloud 15-21, the state the day closes on
    "cloud_trend",           # evening cloud minus morning cloud
    "dewpoint_depression_pm",  # mean (T - Td) 12-18: low-level moisture
    "wind_veer",             # signed direction change morning -> evening
    "precip_hours_today",    # hours with rain: drizzle and downpour differ
    "rh_evening_excess",     # evening humidity minus the daily mean
]

# Hour buckets, in local time (requests carry timezone=Europe/Rome).
MORNING_HOURS = range(6, 13)
AFTERNOON_HOURS = range(12, 19)
EVENING_HOURS = range(15, 22)
LATE_HOURS = range(18, 24)
WET_HOUR_MM = 0.1

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

CSV_FIELDS = ["date", *COLUMN_MAP.keys(), "leaf_wetness_h", *INTRADAY_FIELDS]

# --- paths -----------------------------------------------------------------
SCHEMA_VERSION = 2
LEDGER_PATH = "public/forecasts.jsonl"
