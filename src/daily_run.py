#!/usr/bin/env python3
"""The daily run: score yesterday, forecast tomorrow, commit the ledger.

Runs from a GitHub Action late in the evening. The timing is not arbitrary: to
forecast **tomorrow** the model needs **today** essentially complete, so a
morning run would be predicting today instead — a different and less useful
product.

Order matters. Scoring happens first, so that a run which fails while fetching
the forecast still leaves yesterday's outcome recorded.

Nothing here needs pip: standard library plus the JSON artefacts.

    python src/daily_run.py --dry-run   # print what would happen, write nothing
    python src/daily_run.py
"""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import config
import ledger
import locations
import model as model_module
import sources

ROOT = Path(__file__).resolve().parent.parent

# Enough history for the 7-day window plus the 2-day differences, with slack for
# any day the archive has not settled yet.
HISTORY_DAYS = 14


def score_pending(records: list[dict], today: date, dry_run: bool) -> int:
    """Fill in outcomes for every forecast whose day is now fully past.

    Only strictly-past days are scored: 'today' is still in progress, and an
    outcome read from a partial day would be wrong in a way nothing downstream
    could detect.
    """
    outstanding = [
        r for r in ledger.pending(records)
        if date.fromisoformat(r["target_date"]) < today
    ]
    if not outstanding:
        return 0

    scored_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    scored = 0
    by_city: dict[str, list[dict]] = {}
    for record in outstanding:
        by_city.setdefault(record["city"], []).append(record)

    for city, city_records in by_city.items():
        location = locations.get(city)
        days = sorted(date.fromisoformat(r["target_date"]) for r in city_records)
        rows = sources.reanalysis(
            location.lat, location.lon, days[0], days[-1], with_leaf_wetness=False
        )
        observed = {r["date"]: r["rainfall_mm"] for r in rows}

        for record in city_records:
            rainfall = observed.get(record["target_date"])
            if rainfall is None:
                print(f"  {city} {record['target_date']}: not in the archive yet, leaving open")
                continue
            if dry_run:
                hit = (rainfall >= config.RAIN_THRESHOLD_MM) == record["our_rain"]
                print(f"  would score {city} {record['target_date']}: "
                      f"{rainfall} mm -> {'correct' if hit else 'WRONG'}")
                scored += 1
            elif ledger.score(record, rainfall, config.RAIN_THRESHOLD_MM, scored_at):
                mark = "correct" if record["observed_rain"] == record["our_rain"] else "WRONG"
                print(f"  scored {city} {record['target_date']}: "
                      f"{rainfall} mm, forecast {record['our_prob']:.0%} -> {mark}")
                scored += 1
    return scored


def issue_forecasts(records: list[dict], today: date, dry_run: bool) -> int:
    """Issue tomorrow's forecast for every location."""
    target = today + timedelta(days=1)
    issued_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    issued = 0

    for location in locations.all_locations():
        if (location.key, target.isoformat()) in ledger.index(records):
            print(f"  {location.key}: forecast for {target} already issued, not touching it")
            continue

        mdl = model_module.Model.load(location.key)
        mdl.self_check()

        history = sources.reanalysis(
            location.lat, location.lon, today - timedelta(days=HISTORY_DAYS), today
        )
        history = [row for row in history if row["date"] <= today.isoformat()]
        features = model_module.build_features(history, target, mdl.threshold_mm)
        if features is None:
            raise sources.SourceError(
                f"{location.key}: only {len(history)} days of history, need 7"
            )

        probability = mdl.predict(features)
        benchmark = sources.nwp_forecast(location.lat, location.lon, target) or {
            "om_prob": None, "om_prob_mean": None, "om_precip_mm": None, "om_rain": None
        }

        record = {
            "issued_at": issued_at,
            "city": location.key,
            "target_date": target.isoformat(),
            "our_prob": round(probability, 4),
            "our_rain": bool(probability >= mdl.decision_threshold),
            "climatology": round(mdl.climatology(target.month), 4),
            "model_version": mdl.version,
            **benchmark,
        }

        om = "—" if record["om_prob"] is None else f"{record['om_prob']:.0%}"
        print(f"  {location.name:<20} {probability:>5.0%}   "
              f"(climatology {record['climatology']:.0%}, Open-Meteo {om})")

        if not dry_run and ledger.add_forecast(records, record):
            issued += 1
        elif dry_run:
            issued += 1
    return issued


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    args = parser.parse_args()

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    )
    records = ledger.load()
    print(f"run for {today} — ledger holds {len(records)} records "
          f"({len(ledger.verified(records))} verified)")

    print("\nscoring days that have finished:")
    scored = score_pending(records, today, args.dry_run)
    if not scored:
        print("  nothing to score")

    print(f"\nforecasts for {today + timedelta(days=1)}:")
    issued = issue_forecasts(records, today, args.dry_run)

    if args.dry_run:
        print(f"\ndry run: would score {scored} and issue {issued}, nothing written")
        return 0

    ledger.save(records)
    print(f"\nscored {scored}, issued {issued} -> {ledger.path().relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (sources.SourceError, ledger.LedgerError, FileNotFoundError, ValueError) as exc:
        # Fail loudly. A red Action is visible; a silent gap in the ledger is not.
        print(f"\nFAILED: {exc}", file=sys.stderr)
        sys.exit(1)
