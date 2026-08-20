"""The two Open-Meteo endpoints, behind one interface.

Confusing them would quietly break the project, so they are separated here and
each is labelled with what it may be used for:

    reanalysis(...)   archive-api, ERA5/ERA5-Land.
                      Training data, live features, observed outcomes.
                      This is the ONLY source the model ever sees.

    nwp_forecast(...) forecast-api, operational NWP (ECMWF IFS, ICON).
                      Open-Meteo's own prediction, used purely as a benchmark.
                      Never fed to the model.

The two disagree substantially — 13% of days flip their rain/no-rain
classification. Serving the model from the same product it was trained on is
what removes that skew, rather than trying to correct for it afterwards. See
reports/METHOD_NOTES.md §1.3.

Standard library only: the daily GitHub Action then runs with no `pip install`
at all, which makes it both faster and harder to break.
"""
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import config


class SourceError(RuntimeError):
    """The upstream data is unusable. Fail loudly rather than write a partial record."""


def _get(url: str, params: dict, attempts: int = 4) -> dict:
    """One request, with backoff on rate limiting.

    The free tier meters by request *weight*, not count: a single 29-year hourly
    pull is heavy enough to trip the per-minute limit on its own. Retrying is
    correct here — the request is valid, the server is asking us to slow down —
    but only for 429 and transient network errors, never for a 400 that means we
    asked for something impossible.
    """
    query = urllib.parse.urlencode(params)
    last: Exception | None = None

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                f"{url}?{query}", timeout=config.HTTP_TIMEOUT_S
            ) as resp:
                payload = json.load(resp)
            if "error" in payload:
                raise SourceError(f"Open-Meteo: {payload.get('reason', payload['error'])}")
            return payload
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code != 429:
                raise SourceError(f"HTTP {exc.code} from Open-Meteo: {detail}") from exc
            last = SourceError(f"HTTP 429 from Open-Meteo: {detail}")
        except urllib.error.URLError as exc:
            last = SourceError(f"network unreachable: {exc.reason}")

        if attempt < attempts - 1:
            wait = config.RATE_LIMIT_WAIT_S * (attempt + 1)
            print(f"  rate limited, waiting {wait}s ({attempt + 1}/{attempts - 1})",
                  file=sys.stderr, flush=True)
            time.sleep(wait)

    raise last or SourceError("request failed for an unknown reason")


def leaf_wetness_by_day(hourly: dict) -> dict[str, int]:
    """Hours of leaf wetness per day: RH >= 90% OR precipitation > 0.2 mm.

    The standard proxy in viticulture literature. It is the duration of the
    water film on the leaf, not the humidity of the air, that governs spore
    germination.
    """
    counts: dict[str, int] = {}
    for stamp, rh, rain in zip(
        hourly["time"], hourly["relative_humidity_2m"], hourly["precipitation"]
    ):
        day = stamp[:10]
        counts.setdefault(day, 0)
        if (rh is not None and rh >= config.LEAF_WETNESS_RH_PCT) or (
            rain is not None and rain > config.LEAF_WETNESS_RAIN_MM
        ):
            counts[day] += 1
    return counts


def _bucket(day_hours: dict, variable: str, hours) -> list[float]:
    """Values of `variable` for the given local hours of one day, nulls dropped."""
    return [
        v for h, v in day_hours.get(variable, {}).items() if h in hours and v is not None
    ]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _mean_direction(degrees: list[float]) -> float | None:
    """Vector mean of wind directions. Averaging 350 and 10 arithmetically gives
    180, which is the exact opposite of the answer."""
    if not degrees:
        return None
    x = sum(math.sin(math.radians(d)) for d in degrees)
    y = sum(math.cos(math.radians(d)) for d in degrees)
    if x == 0 and y == 0:
        return None
    return math.degrees(math.atan2(x, y)) % 360.0


def _signed_turn(start: float, end: float) -> float:
    """Shortest signed rotation from `start` to `end`, in (-180, 180].

    Positive is veering (clockwise), which classically accompanies a frontal
    passage; negative is backing.
    """
    return (end - start + 180.0) % 360.0 - 180.0


def intraday_features(hourly: dict) -> dict[str, dict[str, float]]:
    """Recover the shape of each day from the hourly series.

    A daily mean answers "how cloudy was it"; these answer "was it clouding
    over". The second question is the one that says something about tomorrow,
    and it is thrown away by aggregation.

    Every feature degrades gracefully: if the hours it needs are missing, it
    falls back to whatever the day does have, and to 0.0 only when there is
    nothing at all. A run that crashed on one absent hour would be worse than a
    slightly poorer feature.
    """
    by_day: dict[str, dict[str, dict[int, float]]] = {}
    for i, stamp in enumerate(hourly["time"]):
        day, hour = stamp[:10], int(stamp[11:13])
        slot = by_day.setdefault(day, {})
        for variable in config.HOURLY_VARS:
            slot.setdefault(variable, {})[hour] = hourly[variable][i]

    out: dict[str, dict[str, float]] = {}
    for day, hours in by_day.items():
        pressure = hours.get("pressure_msl", {})
        p06, p18 = pressure.get(6), pressure.get(18)
        all_pressure = [v for v in pressure.values() if v is not None]

        morning_cloud = _mean(_bucket(hours, "cloud_cover", config.MORNING_HOURS))
        evening_cloud = _mean(_bucket(hours, "cloud_cover", config.EVENING_HOURS))

        temps = hours.get("temperature_2m", {})
        dews = hours.get("dew_point_2m", {})
        depressions = [
            temps[h] - dews[h]
            for h in config.AFTERNOON_HOURS
            if temps.get(h) is not None and dews.get(h) is not None
        ]

        morning_wind = _mean_direction(_bucket(hours, "wind_direction_10m", config.MORNING_HOURS))
        evening_wind = _mean_direction(_bucket(hours, "wind_direction_10m", config.EVENING_HOURS))

        rh_all = _mean([v for v in hours.get("relative_humidity_2m", {}).values() if v is not None])
        rh_late = _mean(_bucket(hours, "relative_humidity_2m", config.LATE_HOURS))

        out[day] = {
            "d_pressure_intraday": (
                p18 - p06 if p06 is not None and p18 is not None else 0.0
            ),
            "pressure_drop_today": (
                _mean(all_pressure) - min(all_pressure) if all_pressure else 0.0
            ),
            "cloud_evening": evening_cloud if evening_cloud is not None else 0.0,
            "cloud_trend": (
                evening_cloud - morning_cloud
                if evening_cloud is not None and morning_cloud is not None
                else 0.0
            ),
            "dewpoint_depression_pm": _mean(depressions) or 0.0,
            "wind_veer": (
                _signed_turn(morning_wind, evening_wind)
                if morning_wind is not None and evening_wind is not None
                else 0.0
            ),
            "precip_hours_today": float(
                sum(
                    1
                    for v in hours.get("precipitation", {}).values()
                    if v is not None and v > config.WET_HOUR_MM
                )
            ),
            "rh_evening_excess": (
                rh_late - rh_all if rh_late is not None and rh_all is not None else 0.0
            ),
        }
    return out


def reanalysis(
    lat: float, lon: float, start: date, end: date, with_hourly: bool = True
) -> list[dict]:
    """ERA5 reanalysis, one row per day. The only source the model is fed.

    `with_hourly` pulls the hourly series as well; 29 years of hourly data
    is ~7 MB and comes back in one request, so there is no need to page it.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(config.DAILY_VARS),
        "timezone": config.TIMEZONE,
    }
    if with_hourly:
        params["hourly"] = ",".join(config.HOURLY_VARS)

    payload = _get(config.ARCHIVE_URL, params)
    daily = payload["daily"]
    wetness = leaf_wetness_by_day(payload["hourly"]) if with_hourly else {}
    shape = intraday_features(payload["hourly"]) if with_hourly else {}

    rows = []
    for i, day in enumerate(daily["time"]):
        row = {"date": day, "leaf_wetness_h": float(wetness.get(day, 0))}
        row.update({k: float(v) for k, v in shape.get(day, {}).items()})
        for column, api_name in config.COLUMN_MAP.items():
            value = daily[api_name][i]
            if value is None:
                raise SourceError(f"null {column} on {day} — refusing to guess")
            row[column] = float(value)
        rows.append(row)
    return rows


def nwp_forecast(lat: float, lon: float, target: date) -> dict | None:
    """Open-Meteo's own forecast for `target`. The operational benchmark.

    Returns None if the target day is outside the horizon, so the caller can
    record "no benchmark available" rather than an invented one.

    Note on the event mismatch, which must travel with every use of `prob`:
    `precipitation_probability_max` is the chance of rain at *some hour*, a
    strictly more frequent event than *daily accumulation >= 1 mm*. The
    like-for-like comparison is the deterministic one, `rain`.
    """
    payload = _get(
        config.FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(config.FORECAST_VARS),
            "timezone": config.TIMEZONE,
            "forecast_days": 3,
        },
    )
    daily = payload["daily"]
    key = target.isoformat()
    if key not in daily["time"]:
        return None
    i = daily["time"].index(key)

    precip = daily["precipitation_sum"][i]
    prob = daily["precipitation_probability_max"][i]
    return {
        "om_precip_mm": None if precip is None else float(precip),
        "om_prob": None if prob is None else round(float(prob) / 100.0, 4),
        "om_prob_mean": (
            None
            if daily["precipitation_probability_mean"][i] is None
            else round(float(daily["precipitation_probability_mean"][i]) / 100.0, 4)
        ),
        "om_rain": None if precip is None else bool(precip >= config.RAIN_THRESHOLD_MM),
    }
