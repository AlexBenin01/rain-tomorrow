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
MAX_PAGE_KB = 200

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


def build() -> dict:
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

    # The page promises to stay light, and the promise is about the PAGE, not
    # about one file inside it. Enforced here so it cannot rot as the ledger
    # grows or as thresholds are added.
    page = ROOT / "docs"
    total_kb = sum(
        f.stat().st_size
        for pattern in ("*.html", "css/*.css", "js/*.js", "data/*.json")
        for f in page.glob(pattern)
    ) / 1024
    print(f"  whole page: {total_kb:.0f} KB of {MAX_PAGE_KB} KB budget")

    if total_kb > MAX_PAGE_KB:
        print(
            f"FAILED: the page is {total_kb:.0f} KB, over the {MAX_PAGE_KB} KB budget. "
            "Trim what the bundle carries, or page the ledger.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
