"""The data the models were built on, checked as data rather than as files.

The point of these is the one lesson that generalises: the missing value hides
among the valid ones. A file of the right size, with the right columns and no
nulls, can still be physically impossible.
"""
from datetime import date, timedelta

import pytest

import config
import locations
import model as model_module
from fetch_weather import ROOT

SPLITS = ("train", "test")
KEYS = locations.DEFAULT_ORDER


def load(key: str, split: str) -> list[dict]:
    path = ROOT / "data" / f"{key}_{split}.csv"
    if not path.is_file():
        pytest.skip(f"{path.name} not fetched")
    return model_module.load_csv(path)


@pytest.fixture(scope="module", params=[(k, s) for k in KEYS for s in SPLITS])
def dataset(request):
    key, split = request.param
    return key, split, load(key, split)


def test_no_gaps_in_the_series(dataset):
    _, _, rows = dataset
    for previous, current in zip(rows, rows[1:]):
        expected = date.fromisoformat(previous["date"]) + timedelta(days=1)
        assert current["date"] == expected.isoformat(), f"gap before {current['date']}"


def test_precipitation_is_never_negative(dataset):
    """Negative rainfall is a broken sensor wearing the costume of a dry day."""
    _, _, rows = dataset
    offenders = [r["date"] for r in rows if r["rainfall_mm"] < 0]
    assert not offenders, f"negative precipitation on {offenders[:3]}"


def test_values_stay_inside_physical_ranges(dataset):
    _, _, rows = dataset
    for row in rows:
        assert -40 <= row["temp_min"] <= 50, row["date"]
        assert row["temp_max"] >= row["temp_min"], row["date"]
        assert 0 <= row["humidity_pct"] <= 100, row["date"]
        assert 900 <= row["pressure_hpa"] <= 1100, row["date"]
        assert 0 <= row["cloud_pct"] <= 100, row["date"]
        assert 0 <= row["wind_dir_deg"] <= 360, row["date"]
        assert 0 <= row["leaf_wetness_h"] <= 24, row["date"]


def test_the_seasons_are_in_the_right_place(dataset):
    """A technical check would never catch a series with summer in January."""
    _, _, rows = dataset
    if len(rows) < 365:
        pytest.skip("less than a year")
    hottest = max(rows, key=lambda r: r["temp_max"])
    coldest = min(rows, key=lambda r: r["temp_min"])
    assert int(hottest["date"][5:7]) in (6, 7, 8, 9), hottest["date"]
    assert int(coldest["date"][5:7]) in (11, 12, 1, 2, 3), coldest["date"]


# --------------------------------------------------------------------------
# The invariant the whole project rests on
# --------------------------------------------------------------------------
def test_training_data_never_reaches_past_the_boundary():
    for key in KEYS:
        rows = load(key, "train")
        assert rows[-1]["date"] <= str(config.TRAIN_END_DATE), key


def test_test_data_never_reaches_back_before_the_boundary():
    for key in KEYS:
        rows = load(key, "test")
        assert rows[0]["date"] > str(config.TRAIN_END_DATE), key


def test_train_and_test_do_not_overlap_at_any_location():
    for key in KEYS:
        train_days = {r["date"] for r in load(key, "train")}
        test_days = {r["date"] for r in load(key, "test")}
        assert not (train_days & test_days), f"{key}: {len(train_days & test_days)} shared days"


# --------------------------------------------------------------------------
# The gradient the five locations were chosen for
# --------------------------------------------------------------------------
def test_the_rainfall_gradient_runs_the_way_it_should():
    """Bassano is in the foothills and Venezia is on the lagoon. If the ordering
    ever inverted, a coordinate would have been typed wrong."""
    totals = {}
    for key in KEYS:
        rows = load(key, "train")
        totals[key] = sum(r["rainfall_mm"] for r in rows) / (len(rows) / 365.25)
    assert totals["bassano"] > totals["padova"], totals
    assert totals["conegliano"] > totals["venezia"], totals
    assert all(700 < v < 2000 for v in totals.values()), totals
