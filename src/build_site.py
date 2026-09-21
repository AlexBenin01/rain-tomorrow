#!/usr/bin/env python3
"""Assemble what the published page needs: a bundle, and the ledger archive.

The page calls no weather service at all: the model runs in the reader's browser
from the same coefficients Python used, and the files here carry the evidence
alongside it.

Two files rather than one, because only one of them grows. bundle.json is the
first load, and its weight is set by the models and the prose. ledger.json is
the whole record, five rows longer every evening, and the page fetches it only
when the reader reaches the section that reads it. Before the split the record
travelled inside the bundle: on 2026-09-06 its growth pushed the page over the
budget below, and the nightly job stayed red for fifteen days.

Kept deliberately small. The full 588-day probability series per location is not
included — that belongs to the interactive scrubber, which is a later addition.

    python src/build_site.py
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import ledger
import locations

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "bundle.json"
ARCHIVE = ROOT / "docs" / "data" / "ledger.json"

# What the reader downloads before anything appears: everything index.html pulls
# for itself, and nothing that is fetched later.
FIRST_LOAD = ("*.html", "css/*.css", "js/*.js", "data/bundle.json")
MAX_FIRST_LOAD_KB = 200
# The archive is fetched on demand, so its size is a courtesy rather than a
# promise. Warned about, never fatal: it grows on its own every evening, and a
# check that can fail without anybody touching the repository is a check that
# stops the nightly job.
ARCHIVE_WARN_KB = 1024

# Scored days that ride along in the bundle. Forecasts still awaiting their
# outcome are kept whatever their age, so this is only context: two days, so
# that the live section still stands up on its own if the archive fails to load.
RECENT_DAYS = 2

# What the browser needs to reproduce the model, and nothing more.
LOCATION_FIELDS = (
    "feature_names", "feature_set", "decision_threshold", "trained_at",
    "train_window", "validation_window", "test_window", "shipped_thresholds",
)
# Every threshold needs enough to run and to verify itself.
THRESHOLD_FIELDS = (
    "threshold_mm", "coefficients", "intercept", "scaler_mean", "scaler_scale",
    "monthly_climatology", "base_rate", "regularization_C", "reference_vectors",
    "reliability", "stop_criterion", "test_metrics", "shipped",
)
# Only the headline threshold needs the material behind the evidence sections:
# the baseline ladder and the decision-threshold table are shown once, not four
# times. Carrying them for all four pushed the page over its own weight budget.
PRIMARY_ONLY_FIELDS = ("test_comparison", "brier_decomposition", "threshold_sweep")
# Two reference vectors prove the browser reproduces Python just as well as five
# do, at 25 features each across four thresholds and five towns.
REFERENCE_VECTORS_KEPT = 2


def _threshold(block: dict, primary: bool) -> dict:
    fields = THRESHOLD_FIELDS + (PRIMARY_ONLY_FIELDS if primary else ())
    out = {k: block[k] for k in fields if k in block}
    out["reference_vectors"] = block.get("reference_vectors", [])[:REFERENCE_VECTORS_KEPT]
    return out


def recent(records: list[dict]) -> list[dict]:
    """The slice of the record the page needs before it can show anything.

    Every forecast still open, whatever its age, plus the last few scored days
    for context. An open forecast is never dropped: the live section is the one
    thing a reader expects to find already there.
    """
    if not records:
        return []
    newest = max(r["target_date"] for r in records)
    cutoff = (date.fromisoformat(newest) - timedelta(days=RECENT_DAYS)).isoformat()
    return [
        r for r in records
        if r["target_date"] >= cutoff or r.get("observed_rain") is None
    ]


def build(records: list[dict]) -> dict:
    cities = []
    for location in locations.all_locations():
        path = ROOT / "models" / f"{location.key}.json"
        if not path.is_file():
            raise SystemExit(f"missing {path.name} — run src/train.py --all first")
        artefact = json.loads(path.read_text(encoding="utf-8"))
        primary_key = min(artefact["thresholds"], key=float)
        cities.append(
            {
                "key": location.key,
                "name": location.name,
                "lat": location.lat,
                "lon": location.lon,
                "note": location.note,
                **{k: artefact[k] for k in LOCATION_FIELDS if k in artefact},
                "thresholds": {
                    mm: _threshold(block, primary=(mm == primary_key))
                    for mm, block in artefact["thresholds"].items()
                },
            }
        )

    stationarity_path = ROOT / "reports" / "stationarity.json"
    stationarity = (
        json.loads(stationarity_path.read_text(encoding="utf-8"))
        if stationarity_path.is_file()
        else []
    )

    transitions_path = ROOT / "reports" / "transitions.json"
    transitions = (
        json.loads(transitions_path.read_text(encoding="utf-8"))
        if transitions_path.is_file()
        else {}
    )

    return {
        "generated_at": max((r["issued_at"] for r in records), default=None),
        "cities": cities,
        "ledger": recent(records),
        "ledger_records": len(records),
        "stationarity": stationarity,
        "transitions": transitions,
    }


def main() -> int:
    records = ledger.load()
    bundle = build(records)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    ARCHIVE.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")

    archive_kb = ARCHIVE.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(bundle['cities'])} locations, "
          f"{len(bundle['ledger'])} of {len(records)} ledger records")
    print(f"wrote {ARCHIVE.relative_to(ROOT)}  ({archive_kb:.0f} KB, "
          f"{len(records)} records)")

    # The page promises to stay light, and the promise is about what the reader
    # waits for. Enforced here so it cannot rot as thresholds or sections are
    # added. It no longer moves on its own: the part that grows daily left the
    # first load on 2026-09-21.
    page = ROOT / "docs"
    first_load_kb = sum(
        f.stat().st_size for pattern in FIRST_LOAD for f in page.glob(pattern)
    ) / 1024
    print(f"  first load: {first_load_kb:.0f} KB of {MAX_FIRST_LOAD_KB} KB budget")

    if archive_kb > ARCHIVE_WARN_KB:
        print(f"note: the archive is {archive_kb:.0f} KB, past the "
              f"{ARCHIVE_WARN_KB} KB mark. Worth paging it by year.", file=sys.stderr)

    if first_load_kb > MAX_FIRST_LOAD_KB:
        print(
            f"FAILED: the first load is {first_load_kb:.0f} KB, over the "
            f"{MAX_FIRST_LOAD_KB} KB budget. Trim what the bundle carries; the "
            "record is no longer part of it.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
