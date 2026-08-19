"""Every claim this project makes rests on these functions.

So they are checked against cases worked out by hand, not against themselves.
"""
import pytest

import metrics


# --------------------------------------------------------------------------
# Brier score
# --------------------------------------------------------------------------
def test_perfect_forecast_scores_zero():
    assert metrics.brier_score([1.0, 0.0, 1.0], [1.0, 0.0, 1.0]) == 0.0


def test_maximally_wrong_forecast_scores_one():
    assert metrics.brier_score([0.0, 1.0], [1.0, 0.0]) == 1.0


def test_brier_by_hand():
    # (0.3-1)^2 + (0.8-1)^2 + (0.1-0)^2 = 0.49 + 0.04 + 0.01 = 0.54, over 3
    assert metrics.brier_score([0.3, 0.8, 0.1], [1, 1, 0]) == pytest.approx(0.54 / 3)


def test_a_constant_forecast_of_the_base_rate_equals_the_variance():
    """Climatology's Brier score IS the uncertainty term: p(1-p)."""
    outcomes = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]  # base rate 0.3
    assert metrics.brier_score([0.3] * 10, outcomes) == pytest.approx(0.3 * 0.7)


def test_brier_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        metrics.brier_score([0.5, 0.5], [1])


def test_brier_rejects_an_empty_series():
    with pytest.raises(ValueError):
        metrics.brier_score([], [])


# --------------------------------------------------------------------------
# Brier skill score
# --------------------------------------------------------------------------
def test_matching_the_reference_scores_zero_skill():
    outcomes = [1, 0, 1, 0]
    reference = [0.5] * 4
    assert metrics.brier_skill_score(reference, outcomes, reference) == pytest.approx(0.0)


def test_a_perfect_forecast_scores_one():
    outcomes = [1, 0, 1, 0]
    assert metrics.brier_skill_score(
        [1.0, 0.0, 1.0, 0.0], outcomes, [0.5] * 4
    ) == pytest.approx(1.0)


def test_skill_can_be_negative():
    """The finding at the heart of the project: a confident wrong answer scores
    worse than saying nothing."""
    outcomes = [1, 0, 1, 0, 1, 0, 1, 0]
    hard = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]  # always exactly wrong
    assert metrics.brier_skill_score(hard, outcomes, [0.5] * 8) < 0


def test_skill_against_a_perfect_reference_is_undefined_not_infinite():
    outcomes = [1, 0]
    assert metrics.brier_skill_score([0.5, 0.5], outcomes, [1.0, 0.0]) is None


# --------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------
def test_decomposition_reconstructs_the_brier_score():
    """Brier = reliability - resolution + uncertainty. The identity must hold."""
    probs = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95] * 4
    outcomes = [0, 0, 0, 1, 0, 1, 1, 0, 1, 1] * 4
    d = metrics.brier_decomposition(probs, outcomes)
    rebuilt = d["reliability"] - d["resolution"] + d["uncertainty"]
    assert rebuilt == pytest.approx(metrics.brier_score(probs, outcomes))


def test_a_perfectly_calibrated_forecast_has_zero_reliability_term():
    # in each bin the forecast probability equals the observed frequency
    probs = [0.5] * 4 + [1.0] * 2
    outcomes = [1, 1, 0, 0] + [1, 1]
    d = metrics.brier_decomposition(probs, outcomes)
    assert d["reliability"] == pytest.approx(0.0)


def test_climatology_has_zero_resolution():
    """Saying the same thing every day separates nothing."""
    outcomes = [1, 0, 1, 0, 0, 0, 1, 0]
    base = sum(outcomes) / len(outcomes)
    d = metrics.brier_decomposition([base] * len(outcomes), outcomes)
    assert d["resolution"] == pytest.approx(0.0)
    assert d["uncertainty"] == pytest.approx(base * (1 - base))


# --------------------------------------------------------------------------
# Contingency
# --------------------------------------------------------------------------
def test_contingency_by_hand():
    #      p     o    at threshold 0.5
    #     0.9    1    hit
    #     0.7    0    false alarm
    #     0.2    1    miss
    #     0.1    0    correct negative
    c = metrics.contingency([0.9, 0.7, 0.2, 0.1], [1, 0, 1, 0], 0.5)
    assert (c["hits"], c["false_alarms"], c["misses"], c["correct_negatives"]) == (1, 1, 1, 1)
    assert c["POD"] == pytest.approx(0.5)
    assert c["FAR"] == pytest.approx(0.5)
    assert c["CSI"] == pytest.approx(1 / 3)
    assert c["hit_rate"] == pytest.approx(0.5)


def test_lowering_the_threshold_never_lowers_pod():
    """The trade-off the decision threshold governs, as a monotonicity."""
    probs = [0.1, 0.25, 0.4, 0.55, 0.7, 0.85]
    outcomes = [0, 1, 0, 1, 1, 1]
    pods = [metrics.contingency(probs, outcomes, t)["POD"] for t in (0.2, 0.4, 0.6, 0.8)]
    assert pods == sorted(pods, reverse=True)


def test_never_warning_gives_undefined_far_not_a_crash():
    c = metrics.contingency([0.1, 0.2], [1, 0], 0.9)
    assert c["hits"] == 0 and c["n_warnings"] == 0
    assert c["FAR"] is None
    assert c["POD"] == pytest.approx(0.0)


def test_the_accuracy_trap_is_real():
    """'It never rains' scores 70% on a 30% event. This is why hit_rate never
    travels alone in this project."""
    outcomes = [1] * 30 + [0] * 70
    c = metrics.contingency([0.0] * 100, outcomes, 0.5)
    assert c["hit_rate"] == pytest.approx(0.70)
    assert c["POD"] == pytest.approx(0.0)  # it caught nothing at all


# --------------------------------------------------------------------------
# Reliability curve
# --------------------------------------------------------------------------
def test_reliability_curve_bins_and_counts():
    probs = [0.05, 0.15, 0.85, 0.95]
    outcomes = [0, 0, 1, 1]
    curve = metrics.reliability_curve(probs, outcomes, bins=5, min_count=1)
    assert [b["n"] for b in curve] == [2, 2]
    assert curve[0]["observed"] == pytest.approx(0.0)
    assert curve[-1]["observed"] == pytest.approx(1.0)


def test_thin_bins_are_dropped_rather_than_plotted():
    """A point built on two samples is noise wearing the costume of evidence."""
    probs = [0.05] * 20 + [0.95] * 2
    outcomes = [0] * 20 + [1, 1]
    curve = metrics.reliability_curve(probs, outcomes, bins=5, min_count=10)
    assert len(curve) == 1
