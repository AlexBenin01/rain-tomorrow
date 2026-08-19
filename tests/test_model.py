"""The runtime must reproduce the training output exactly, for every location.

Each artefact carries reference vectors with the probability the training run
produced. If the feature order, the scaler or the sigmoid ever drift, this fails
immediately — rather than after weeks of quietly wrong published forecasts.
"""
import math
from datetime import date

import pytest

import config
import locations
import model as model_module

KEYS = locations.DEFAULT_ORDER


@pytest.fixture(scope="module", params=KEYS)
def model(request):
    return model_module.Model.load(request.param)


# --------------------------------------------------------------------------
# The artefact itself
# --------------------------------------------------------------------------
def test_artefact_is_internally_consistent(model):
    n = len(model.features)
    assert len(model.coefficients) == n
    assert len(model.mean) == n
    assert len(model.scale) == n
    assert all(s > 0 for s in model.scale), "a zero scale means broken standardisation"
    assert model.payload["horizon_days"] == 1
    assert model.payload["threshold_mm"] == config.RAIN_THRESHOLD_MM


def test_it_reproduces_the_training_output(model):
    """The check that matters: same numbers as Python, to 1e-9."""
    assert model.reference_vectors, "the artefact carries no reference vectors"
    model.self_check(tolerance=1e-9)


def test_self_check_actually_fails_when_the_model_is_wrong(model):
    """A test that never fails proves nothing, so break it deliberately."""
    broken = model_module.Model(dict(model.payload))
    broken.intercept = model.intercept + 5.0
    with pytest.raises(ValueError, match="reference vector"):
        broken.self_check()


def test_the_training_window_never_reaches_the_test_period(model):
    assert model.payload["train_window"][1] <= str(config.TRAIN_END_DATE)
    assert model.payload["test_window"][0] > str(config.TRAIN_END_DATE)


def test_the_stop_criterion_was_passed(model):
    criterion = model.payload["stop_criterion"]
    assert criterion["passed"], f"{model.location['key']} shipped without passing"
    assert criterion["achieved_gain"] >= criterion["min_gain"]


# --------------------------------------------------------------------------
# Physics
# --------------------------------------------------------------------------
def test_the_coefficients_agree_with_meteorology(model):
    """No physical rule was imposed. The signs come out right anyway.

    Only coefficients that are NOT inside a collinear block are asserted
    individually — see the test below for why that distinction matters.
    """
    coef = dict(zip(model.features, model.coefficients))
    assert coef["pressure_today"] < 0, "low pressure must raise the chance of rain"
    assert coef["d_pressure_1d"] < 0, "falling pressure means a front is approaching"
    assert coef["cloud_today"] > 0, "cloud today must raise the chance of rain tomorrow"
    assert coef["rh_today"] > 0, "humid air must raise the chance of rain"
    assert coef["wet_days_last_7"] > 0, "a wet spell must raise the chance of rain"
    assert coef["wind_from_east"] > 0, "easterly flow draws moisture off the Adriatic"


def test_the_persistence_signal_is_positive_as_a_whole(model):
    """`rain_today_log` and `rained_today` both encode "it rained today".

    Under strong regularisation the model splits that one signal between them
    however it likes, and at three of the five locations it loads all of it onto
    the binary term, leaving the log term very slightly negative. Reading either
    coefficient alone would be a mistake: inside a collinear block only the
    combination is interpretable.
    """
    coef = dict(zip(model.features, model.coefficients))
    combined = coef["rain_today_log"] + coef["rained_today"]
    assert combined > 0, f"persistence is negative overall: {combined:+.3f}"


def test_probabilities_stay_in_range_even_on_absurd_inputs(model):
    for scale in (-1e4, -1.0, 0.0, 1.0, 1e4):
        p = model.predict({name: scale for name in model.features})
        assert 0.0 <= p <= 1.0


def test_monthly_climatology_covers_the_year(model):
    assert sorted(model.monthly_climatology) == list(range(1, 13))
    assert all(0.0 < v < 1.0 for v in model.monthly_climatology.values())


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------
def _day(**kwargs):
    row = dict(
        date="2026-06-01", rainfall_mm=1.0, temp_min=10.0, temp_max=20.0,
        humidity_pct=70.0, leaf_wetness_h=5.0, pressure_hpa=1012.0,
        cloud_pct=40.0, wind_dir_deg=200.0, wind_speed_kmh=9.0,
    )
    row.update(kwargs)
    return row


def test_a_short_history_is_refused_not_padded():
    assert model_module.build_features([_day()] * 4, date(2026, 6, 5), 1.0) is None


def test_differences_use_the_right_days():
    history = [_day(pressure_hpa=1000.0 + i) for i in range(8)]
    f = model_module.build_features(history, date(2026, 6, 9), 1.0)
    assert f["d_pressure_1d"] == pytest.approx(1.0)
    assert f["d_pressure_2d"] == pytest.approx(2.0)


def test_wet_days_counts_only_above_the_threshold():
    history = [_day(rainfall_mm=0.5) for _ in range(5)] + [_day(rainfall_mm=5.0) for _ in range(3)]
    f = model_module.build_features(history, date(2026, 6, 9), 1.0)
    assert f["wet_days_last_7"] == pytest.approx(3.0)


def test_wind_direction_is_continuous_across_north():
    """359 and 1 degrees are close; the raw angle would put them 358 apart."""
    def wind(deg):
        return model_module.build_features(
            [_day(wind_dir_deg=deg) for _ in range(8)], date(2026, 6, 9), 1.0
        )
    a, b = wind(359.0), wind(1.0)
    assert abs(a["wind_from_east"] - b["wind_from_east"]) < 0.05
    assert abs(a["wind_from_south"] - b["wind_from_south"]) < 0.01
    assert wind(0.0)["wind_from_east"] == pytest.approx(wind(360.0)["wind_from_east"], abs=1e-12)


def test_wind_components_point_the_right_way():
    """Meteorological convention: the direction the wind blows FROM."""
    def wind(deg):
        return model_module.build_features(
            [_day(wind_dir_deg=deg) for _ in range(8)], date(2026, 6, 9), 1.0
        )
    assert wind(180.0)["wind_from_south"] == pytest.approx(1.0)
    assert wind(0.0)["wind_from_south"] == pytest.approx(-1.0)
    assert wind(90.0)["wind_from_east"] == pytest.approx(1.0)


def test_only_the_day_of_year_of_the_target_reaches_the_model():
    """If the weather being predicted ever leaked in, every metric would jump and
    it would look like success. This is the guard against that."""
    history = [_day() for _ in range(8)]
    june = model_module.build_features(history, date(2026, 6, 9), 1.0)
    december = model_module.build_features(history, date(2026, 12, 9), 1.0)
    differing = {k for k in june if june[k] != december[k]}
    assert differing == {"sin_doy", "cos_doy"}


def test_a_forecast_is_never_a_certainty(model):
    """Exactly 0 or 1 would be the signature of an oracle, not a model."""
    for rain in (0.0, 0.5, 5.0, 50.0):
        history = [_day(rainfall_mm=rain) for _ in range(8)]
        f = model_module.build_features(history, date(2026, 6, 9), model.threshold_mm)
        p = model.predict(f)
        assert 0.0 < p < 1.0
        assert not math.isclose(p, 0.0, abs_tol=1e-6)
