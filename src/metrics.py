"""Forecast verification metrics.

Pure standard library on purpose: training, the daily run and the tests all use
the same functions, and the tests need no heavy dependencies to exercise them.

Every claim this project makes rests on these fifty lines, so they are tested
directly against cases worked out by hand in tests/test_metrics.py.

On the choice of metrics: accuracy is a trap on imbalanced events. With rain on
roughly 30% of days, "it never rains" scores 70% and looks competent. The Brier
score and its skill score against a reference are the honest measures, and the
contingency scores (POD/FAR/CSI) say what a decision at a given threshold
actually costs.
"""
import math


def brier_score(probabilities: list[float], outcomes: list[float]) -> float:
    """Mean squared error of probabilistic forecasts. Lower is better; 0 is perfect."""
    if not probabilities:
        raise ValueError("no forecasts to score")
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes have different lengths")
    return sum((p - o) ** 2 for p, o in zip(probabilities, outcomes)) / len(probabilities)


def brier_skill_score(
    probabilities: list[float], outcomes: list[float], reference: list[float]
) -> float | None:
    """Improvement over a reference forecast. Positive means better than it.

    None when the reference is itself perfect, in which case there is no room to
    improve and the ratio is undefined — better than returning an infinity that
    silently propagates into a chart.
    """
    reference_score = brier_score(reference, outcomes)
    if reference_score == 0:
        return None
    return 1.0 - brier_score(probabilities, outcomes) / reference_score


def brier_decomposition(
    probabilities: list[float], outcomes: list[float], bins: int = 10
) -> dict:
    """Murphy's decomposition: Brier = reliability - resolution + uncertainty.

    This is the tool that makes a comparison against a numerical weather model
    informative rather than just a verdict. An NWP system has far more
    *resolution* — it separates rainy days from dry ones better. A statistical
    model calibrated by construction can still win on *reliability* — when it
    says 30%, it rains 30% of the time. Reporting only the total hides which of
    the two is happening.

    reliability  mean squared gap between forecast probability and observed
                 frequency within each bin. Lower is better.
    resolution   how far the binned outcome frequencies sit from the base rate.
                 Higher is better.
    uncertainty  the variance of the event itself. Not a property of the
                 forecast: it is the Brier score climatology would obtain.
    """
    n = len(probabilities)
    if n == 0:
        raise ValueError("no forecasts to score")
    base_rate = sum(outcomes) / n

    grouped: dict[int, list[tuple[float, float]]] = {}
    for p, o in zip(probabilities, outcomes):
        index = min(int(p * bins), bins - 1)
        grouped.setdefault(index, []).append((p, o))

    reliability = resolution = 0.0
    for group in grouped.values():
        count = len(group)
        mean_p = sum(p for p, _ in group) / count
        mean_o = sum(o for _, o in group) / count
        reliability += count * (mean_p - mean_o) ** 2
        resolution += count * (mean_o - base_rate) ** 2

    return {
        "reliability": reliability / n,
        "resolution": resolution / n,
        "uncertainty": base_rate * (1.0 - base_rate),
        "base_rate": base_rate,
        "n": n,
    }


def contingency(probabilities: list[float], outcomes: list[float], threshold: float) -> dict:
    """The 2x2 table and the scores forecasters actually use.

    POD  probability of detection — the share of real events that were warned of
    FAR  false alarm ratio — the share of warnings that came to nothing
    CSI  critical success index — hits over everything that mattered

    hit_rate is included because it is what a reader understands at a glance,
    and immediately next to it so nobody quotes it alone.
    """
    hits = misses = false_alarms = correct_negatives = 0
    for p, o in zip(probabilities, outcomes):
        predicted, observed = p >= threshold, o >= 0.5
        if predicted and observed:
            hits += 1
        elif not predicted and observed:
            misses += 1
        elif predicted and not observed:
            false_alarms += 1
        else:
            correct_negatives += 1

    total = hits + misses + false_alarms + correct_negatives
    events, warnings = hits + misses, hits + false_alarms
    return {
        "threshold": threshold,
        "hits": hits,
        "misses": misses,
        "false_alarms": false_alarms,
        "correct_negatives": correct_negatives,
        "POD": hits / events if events else None,
        "FAR": false_alarms / warnings if warnings else None,
        "CSI": (
            hits / (hits + misses + false_alarms) if hits + misses + false_alarms else None
        ),
        "hit_rate": (hits + correct_negatives) / total if total else None,
        "n_warnings": warnings,
        "n": total,
    }


def reliability_curve(
    probabilities: list[float], outcomes: list[float], bins: int = 5, min_count: int = 1
) -> list[dict]:
    """When the forecast says 70%, does it rain 70% of the time?

    Bins with fewer than `min_count` members are dropped rather than plotted:
    a point built on two samples is noise wearing the costume of evidence.
    """
    grouped: dict[int, list[tuple[float, float]]] = {}
    for p, o in zip(probabilities, outcomes):
        index = min(int(p * bins), bins - 1)
        grouped.setdefault(index, []).append((p, o))

    curve = []
    for index in sorted(grouped):
        group = grouped[index]
        if len(group) < min_count:
            continue
        low, high = index / bins, (index + 1) / bins
        curve.append(
            {
                "range": f"{low:.0%}-{high:.0%}",
                "predicted": sum(p for p, _ in group) / len(group),
                "observed": sum(o for _, o in group) / len(group),
                "n": len(group),
            }
        )
    return curve


def log_loss(probabilities: list[float], outcomes: list[float], eps: float = 1e-15) -> float:
    """Kept for completeness; the Brier score is the one reported.

    Log loss punishes a confident mistake without limit, which makes it very
    sensitive to a single forecast of 0 or 1. For a public daily scoreboard that
    is the wrong property.
    """
    total = 0.0
    for p, o in zip(probabilities, outcomes):
        p = min(max(p, eps), 1 - eps)
        total += -(o * math.log(p) + (1 - o) * math.log(1 - p))
    return total / len(probabilities)
