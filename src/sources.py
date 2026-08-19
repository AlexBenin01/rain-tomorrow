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


def reanalysis(
    lat: float, lon: float, start: date, end: date, with_leaf_wetness: bool = True
) -> list[dict]:
    """ERA5 reanalysis, one row per day. The only source the model is fed.

    `with_leaf_wetness` pulls the hourly series as well; 29 years of hourly data
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
    if with_leaf_wetness:
        params["hourly"] = ",".join(config.HOURLY_VARS)

    payload = _get(config.ARCHIVE_URL, params)
    daily = payload["daily"]
    wetness = leaf_wetness_by_day(payload["hourly"]) if with_leaf_wetness else {}

    rows = []
    for i, day in enumerate(daily["time"]):
        row = {"date": day, "leaf_wetness_h": float(wetness.get(day, 0))}
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
