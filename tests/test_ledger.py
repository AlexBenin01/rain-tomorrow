"""The ledger's contract: append-only, and a published forecast is never rewritten.

That contract is the entire evidential value of the project. If a forecast could
be edited after the outcome were known, the git history would prove nothing and
the live record would be worth exactly as much as a backtest.
"""
import json

import pytest

import ledger


def _forecast(city="vicenza", target="2026-08-20", prob=0.34):
    return {
        "issued_at": "2026-08-19T21:04:11Z",
        "city": city,
        "target_date": target,
        "our_prob": prob,
        "our_rain": prob >= 0.5,
        "om_prob": 0.55,
        "om_prob_mean": 0.31,
        "om_precip_mm": 2.3,
        "om_rain": True,
        "climatology": 0.29,
        "model_version": "lr-v1@2026-08-19",
    }


# --------------------------------------------------------------------------
# Append-only
# --------------------------------------------------------------------------
def test_a_forecast_is_added_once():
    records = []
    assert ledger.add_forecast(records, _forecast()) is True
    assert len(records) == 1
    assert records[0]["observed_rain"] is None, "it must be born unscored"


def test_the_same_day_is_never_issued_twice():
    records = []
    ledger.add_forecast(records, _forecast(prob=0.34))
    assert ledger.add_forecast(records, _forecast(prob=0.99)) is False
    assert len(records) == 1
    assert records[0]["our_prob"] == 0.34, "the first forecast must survive"


def test_different_cities_on_the_same_day_coexist():
    records = []
    ledger.add_forecast(records, _forecast(city="vicenza"))
    ledger.add_forecast(records, _forecast(city="padova"))
    assert len(records) == 2


def test_an_incomplete_record_is_refused():
    broken = _forecast()
    del broken["climatology"]
    with pytest.raises(ledger.LedgerError, match="missing fields"):
        ledger.add_forecast([], broken)


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
def test_scoring_fills_the_outcome_and_only_the_outcome():
    records = []
    ledger.add_forecast(records, _forecast(prob=0.34))
    before = {k: v for k, v in records[0].items() if k in ledger.ISSUED_FIELDS}

    assert ledger.score(records[0], 4.6, 1.0, "2026-08-21T21:00:00Z") is True
    assert records[0]["observed_mm"] == 4.6
    assert records[0]["observed_rain"] is True

    after = {k: v for k, v in records[0].items() if k in ledger.ISSUED_FIELDS}
    assert after == before, "scoring must not touch the forecast itself"


def test_a_scored_record_cannot_be_rescored():
    """Otherwise a later run could quietly correct an inconvenient outcome."""
    records = []
    ledger.add_forecast(records, _forecast())
    ledger.score(records[0], 4.6, 1.0, "2026-08-21T21:00:00Z")
    assert ledger.score(records[0], 0.0, 1.0, "2026-08-22T21:00:00Z") is False
    assert records[0]["observed_mm"] == 4.6


def test_the_threshold_decides_the_outcome():
    records = []
    ledger.add_forecast(records, _forecast(target="2026-08-20"))
    ledger.add_forecast(records, _forecast(target="2026-08-21"))
    ledger.score(records[0], 0.9, 1.0, "t")
    ledger.score(records[1], 1.0, 1.0, "t")
    assert records[0]["observed_rain"] is False
    assert records[1]["observed_rain"] is True, "the threshold is inclusive"


def test_verified_and_pending_partition_the_ledger():
    records = []
    ledger.add_forecast(records, _forecast(target="2026-08-20"))
    ledger.add_forecast(records, _forecast(target="2026-08-21"))
    ledger.score(records[0], 4.6, 1.0, "t")
    assert len(ledger.verified(records)) == 1
    assert len(ledger.pending(records)) == 1


# --------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------
def test_saving_and_loading_preserves_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "path", lambda: tmp_path / "forecasts.jsonl")
    records = []
    ledger.add_forecast(records, _forecast(city="padova", target="2026-08-21"))
    ledger.add_forecast(records, _forecast(city="vicenza", target="2026-08-20"))
    ledger.score(records[1], 4.6, 1.0, "t")
    ledger.save(records)

    reloaded = ledger.load()
    assert len(reloaded) == 2
    # sorted by target date, so the older day comes first regardless of insertion
    assert reloaded[0]["target_date"] == "2026-08-20"
    assert reloaded[0]["observed_rain"] is True


def test_a_corrupt_line_is_reported_with_its_number(tmp_path, monkeypatch):
    file = tmp_path / "forecasts.jsonl"
    file.write_text(json.dumps(_forecast()) + "\nnot json at all\n", encoding="utf-8")
    monkeypatch.setattr(ledger, "path", lambda: file)
    with pytest.raises(ledger.LedgerError, match=":2"):
        ledger.load()


def test_a_missing_ledger_is_empty_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "path", lambda: tmp_path / "nothing.jsonl")
    assert ledger.load() == []


# --------------------------------------------------------------------------
# The real file
# --------------------------------------------------------------------------
def test_the_published_ledger_is_well_formed():
    records = ledger.load()
    seen = set()
    for record in records:
        assert ledger.key(record) not in seen, f"duplicate entry for {ledger.key(record)}"
        seen.add(ledger.key(record))
        for field in ledger.ISSUED_FIELDS:
            assert field in record, f"{field} missing from a published record"
        assert 0.0 <= record["our_prob"] <= 1.0
        # nothing may be forecast for a day inside the training period
        assert record["target_date"] > "2024-12-31"
