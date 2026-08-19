#!/usr/bin/env python3
"""Assemble everything the published page needs into one JSON bundle.

The page is fully static and makes no network requests at all: the model runs in
the reader's browser from the same coefficients Python used, and the bundle
carries the evidence alongside it.

Kept deliberately small. The full 588-day probability series per location is not
included — that belongs to the interactive scrubber, which is a later addition.

    python src/build_site.py
"""
import json
import sys
from pathlib import Path

import ledger
import locations

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "bundle.json"
MAX_BUNDLE_KB = 200

# what the browser needs to reproduce the model, and nothing more
MODEL_FIELDS = (
    "feature_names", "coefficients", "intercept", "scaler_mean", "scaler_scale",
    "monthly_climatology", "base_rate", "threshold_mm", "decision_threshold",
    "trained_at", "train_window", "validation_window", "test_window",
    "regularization_C", "reference_vectors", "test_comparison", "reliability",
    "brier_decomposition", "threshold_sweep", "stop_criterion", "test_metrics",
)


def build() -> dict:
    cities = []
    for location in locations.all_locations():
        path = ROOT / "models" / f"{location.key}.json"
        if not path.is_file():
            raise SystemExit(f"missing {path.name} — run src/train.py --all first")
        artefact = json.loads(path.read_text(encoding="utf-8"))
        cities.append(
            {
                "key": location.key,
                "name": location.name,
                "lat": location.lat,
                "lon": location.lon,
                "note": location.note,
                **{k: artefact[k] for k in MODEL_FIELDS if k in artefact},
            }
        )

    stationarity_path = ROOT / "reports" / "stationarity.json"
    stationarity = (
        json.loads(stationarity_path.read_text(encoding="utf-8"))
        if stationarity_path.is_file()
        else []
    )

    records = ledger.load()
    return {
        "generated_at": max((r["issued_at"] for r in records), default=None),
        "cities": cities,
        "ledger": records,
        "stationarity": stationarity,
    }


def main() -> int:
    bundle = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({size_kb:.0f} KB)")
    print(f"  {len(bundle['cities'])} locations, {len(bundle['ledger'])} ledger records")

    # The page promises to stay light. Enforced, so the promise cannot rot as
    # the ledger grows.
    if size_kb > MAX_BUNDLE_KB:
        print(f"\nFAILED: bundle is {size_kb:.0f} KB, over the {MAX_BUNDLE_KB} KB budget.\n"
              "The ledger has probably outgrown inline embedding and needs paging.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
