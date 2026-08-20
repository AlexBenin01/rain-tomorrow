#!/usr/bin/env python3
"""Download ERA5 reanalysis for one location and write a validated CSV.

Three splits, and the boundaries between them are enforced, not documented:

    analysis   1996-01-01 .. 2024-12-31   stationarity study only, never trained on
    train      2016-01-01 .. 2024-12-31   training + validation
    test       2025-01-01 .. today-1      held out, and the region the live
                                          forecasts also live in

Every check runs BEFORE anything is written: the script fails loudly rather than
leave a silently broken CSV on disk.

    python src/fetch_weather.py --location vicenza --split train
    python src/fetch_weather.py --all --split test
"""
import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import config
import locations
import sources

ROOT = Path(__file__).resolve().parent.parent


class DataQualityError(RuntimeError):
    """A check failed. Nothing is written."""


def window_for(split: str, today: date) -> tuple[date, date]:
    if split == "analysis":
        return config.ANALYSIS_START_DATE, config.TRAIN_END_DATE
    if split == "train":
        return config.TRAIN_START_DATE, config.TRAIN_END_DATE
    if split == "train_long":
        # Full history WITH leaf wetness. Exists only to answer whether the
        # uniform 2016 window costs skill; never used for a shipped model.
        return config.ANALYSIS_START_DATE, config.TRAIN_END_DATE
    if split == "test":
        return config.TRAIN_END_DATE + timedelta(days=1), today - timedelta(days=1)
    raise ValueError(f"unknown split: {split}")


# Everything derived from the hourly series: leaf wetness plus the intra-day
# shape features.
HOURLY_DERIVED = {"leaf_wetness_h", *config.INTRADAY_FIELDS}


def fields_for(split: str) -> list[str]:
    """The `analysis` split carries nothing derived from the hourly series.

    Deriving those needs 29 years of hourly data across five cities for columns
    the stationarity study never reads. Absent columns are better than columns
    silently filled with zeros.
    """
    if split == "analysis":
        return [f for f in config.CSV_FIELDS if f not in HOURLY_DERIVED]
    return config.CSV_FIELDS


def validate(rows: list[dict], start: date, end: date, fields: list[str]) -> None:
    expected = (end - start).days + 1
    if len(rows) != expected:
        raise DataQualityError(f"expected {expected} rows, got {len(rows)}")

    for row in rows:
        for key in fields:
            if row.get(key) is None:
                raise DataQualityError(f"missing {key!r} on {row['date']}")

    # The missing value hides among the valid ones: negative rainfall means a
    # broken sensor, not a dry day. Checking the numbers, not just the shape.
    negatives = [r["date"] for r in rows if r["rainfall_mm"] < 0]
    if negatives:
        raise DataQualityError(
            f"{len(negatives)} days with negative precipitation, first {negatives[0]}"
        )

    for i, row in enumerate(rows):
        want = start + timedelta(days=i)
        if row["date"] != want.isoformat():
            raise DataQualityError(f"gap in series: expected {want}, found {row['date']}")

    for row in rows:
        if not -40 <= row["temp_min"] <= 50 or not -40 <= row["temp_max"] <= 55:
            raise DataQualityError(f"implausible temperature on {row['date']}")
        if row["temp_max"] < row["temp_min"]:
            raise DataQualityError(f"temp_max < temp_min on {row['date']}")
        if not 0 <= row["humidity_pct"] <= 100:
            raise DataQualityError(f"humidity out of range on {row['date']}")
        if "leaf_wetness_h" in fields:
            if not 0 <= row["leaf_wetness_h"] <= 24:
                raise DataQualityError(f"leaf wetness out of range on {row['date']}")
            if not 0 <= row["precip_hours_today"] <= 24:
                raise DataQualityError(f"wet-hour count out of range on {row['date']}")
            if not -180 <= row["wind_veer"] <= 180:
                raise DataQualityError(f"wind veer out of range on {row['date']}")
            if not 0 <= row["cloud_evening"] <= 100:
                raise DataQualityError(f"evening cloud out of range on {row['date']}")
            if row["pressure_drop_today"] < 0:
                raise DataQualityError(f"negative pressure drop on {row['date']}")
        if not 900 <= row["pressure_hpa"] <= 1100:
            raise DataQualityError(f"implausible pressure on {row['date']}")
        if not 0 <= row["wind_dir_deg"] <= 360:
            raise DataQualityError(f"wind direction out of range on {row['date']}")
        if not 0 <= row["cloud_pct"] <= 100:
            raise DataQualityError(f"cloud cover out of range on {row['date']}")

    # A physical check, not just a technical one: over a year or more the hottest
    # day belongs to summer and the coldest to winter. A series that fails this
    # is wrong in a way no range check would catch.
    if len(rows) >= 365:
        hottest = max(rows, key=lambda r: r["temp_max"])
        coldest = min(rows, key=lambda r: r["temp_min"])
        if int(hottest["date"][5:7]) not in (6, 7, 8, 9):
            raise DataQualityError(f"hottest day falls on {hottest['date']}: not physical")
        if int(coldest["date"][5:7]) not in (11, 12, 1, 2, 3):
            raise DataQualityError(f"coldest day falls on {coldest['date']}: not physical")


def summarize(rows: list[dict], fields: list[str]) -> None:
    n = len(rows)
    wet = sum(1 for r in rows if r["rainfall_mm"] >= config.RAIN_THRESHOLD_MM)
    total = sum(r["rainfall_mm"] for r in rows)
    hottest = max(rows, key=lambda r: r["temp_max"])
    coldest = min(rows, key=lambda r: r["temp_min"])
    print(f"  rows            : {n}  ({rows[0]['date']} -> {rows[-1]['date']})")
    print(f"  wet days >= 1mm : {wet}  ({100 * wet / n:.1f}%)")
    print(f"  rainfall        : {total:.0f} mm  ({total / (n / 365.25):.0f} mm/yr)")
    if "leaf_wetness_h" in fields:
        print(f"  leaf wetness    : {sum(r['leaf_wetness_h'] for r in rows) / n:.1f} h/day")
    print(f"  hottest/coldest : {hottest['date']} {hottest['temp_max']}C"
          f" / {coldest['date']} {coldest['temp_min']}C")


def csv_path(location_key: str, split: str) -> Path:
    return ROOT / "data" / f"{location_key}_{split}.csv"


def fetch_one(location, split: str, today: date) -> Path:
    start, end = window_for(split, today)

    if start > end:
        raise DataQualityError(
            f"inverted window {start} -> {end}: no data yet for split {split!r}"
        )
    if split == "test" and start <= config.TRAIN_END_DATE:
        raise DataQualityError(
            f"INVARIANT VIOLATED: test split would start {start}, inside the training "
            f"period (through {config.TRAIN_END_DATE})"
        )
    if split in ("train", "train_long", "analysis") and end > config.TRAIN_END_DATE:
        raise DataQualityError(
            f"INVARIANT VIOLATED: {split} would reach {end}, past {config.TRAIN_END_DATE}"
        )

    fields = fields_for(split)
    print(f"[{split}] {location.name} ({location.lat}, {location.lon})")
    print(f"  GET {start} -> {end} ({(end - start).days + 1} days)")
    rows = sources.reanalysis(
        location.lat, location.lon, start, end,
        with_hourly=bool(HOURLY_DERIVED & set(fields)),
    )

    validate(rows, start, end, fields)
    summarize(rows, fields)

    out = csv_path(location.key, split)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {out.relative_to(ROOT)}  ({out.stat().st_size / 1024:.0f} KB)")
    print("  all checks passed")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split",
                        choices=["analysis", "train", "train_long", "test"], required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--location", help="one of: " + ", ".join(locations.DEFAULT_ORDER))
    group.add_argument("--all", action="store_true", help="every location")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for reproducible runs")
    args = parser.parse_args()

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    )
    targets = (
        locations.all_locations() if args.all else [locations.get(args.location)]
    )

    for i, location in enumerate(targets):
        if i:
            print()
        fetch_one(location, args.split, today)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (DataQualityError, sources.SourceError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
