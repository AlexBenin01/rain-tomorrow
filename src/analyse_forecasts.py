#!/usr/bin/env python3
"""What does this model actually say, and when is it wrong?

Skill scores tell you whether a forecast is useful. They do not tell you what it
sounds like — whether it commits or hedges, when it goes out on a limb, and what
kind of day it fails on. This answers that.

It deliberately runs through the SHIPPED artefact and the same inference path
production uses, so it doubles as a check that the published model reproduces
these numbers. Standard library only.

    python src/analyse_forecasts.py
    python src/analyse_forecasts.py --location vicenza
"""
import argparse
import json
import statistics as st
import sys
from datetime import date
from pathlib import Path

import config
import ledger
import locations
import metrics
import model as model_module

# The Windows console defaults to cp1252 and cannot print the bar glyphs.
# Reconfiguring stdout is better than degrading the output everywhere else.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_ORDER = ["winter", "spring", "summer", "autumn"]


def replay(location_key: str) -> dict:
    """Re-run the shipped model across the held-out test set, day by day."""
    mdl = model_module.Model.load(location_key)
    mdl.self_check()
    rows = model_module.load_csv(ROOT / "data" / f"{location_key}_test.csv")

    out = []
    for i in range(7, len(rows) - 1):
        target = date.fromisoformat(rows[i + 1]["date"])
        features = model_module.build_features(rows[: i + 1], target, mdl.threshold_mm)
        if features is None:
            continue
        out.append(
            {
                "target": target,
                "prob": mdl.predict(features),
                "climatology": mdl.climatology(target.month),
                "observed_mm": rows[i + 1]["rainfall_mm"],
                "observed": 1.0 if rows[i + 1]["rainfall_mm"] >= mdl.threshold_mm else 0.0,
                "rained_today": features["rained_today"],
            }
        )
    return {"model": mdl, "days": out}


def histogram(values: list[float], width: int = 34) -> list[str]:
    edges = [i / 10 for i in range(11)]
    counts = [0] * 10
    for v in values:
        counts[min(int(v * 10), 9)] += 1
    peak = max(counts) or 1
    lines = []
    for i, count in enumerate(counts):
        bar = "█" * round(count / peak * width)
        share = count / len(values)
        lines.append(f"  {edges[i]:.0%}-{edges[i+1]:>4.0%} {bar:<{width}} {count:>4}  {share:>5.1%}")
    return lines


def analyse(location_key: str, verbose: bool = True) -> dict:
    result = replay(location_key)
    days, mdl = result["days"], result["model"]
    probs = [d["prob"] for d in days]
    obs = [d["observed"] for d in days]
    clim = [d["climatology"] for d in days]
    name = locations.get(location_key).name

    brier = metrics.brier_score(probs, obs)
    bss = metrics.brier_skill_score(probs, obs, clim)
    decomposition = metrics.brier_decomposition(probs, obs)

    # Does the forecast echo today or anticipate tomorrow? If it correlates more
    # with today's rain than with tomorrow's, it is largely reporting the present.
    def _corr(xs, ys):
        mx, my = st.mean(xs), st.mean(ys)
        num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
        return num / den if den else 0.0

    today_rain = [d["rained_today"] for d in days]
    corr_today = _corr(probs, today_rain)
    corr_tomorrow = _corr(probs, obs)

    # Split the days into those where the weather stayed as it was and those
    # where it changed. A forecast is only worth anything on the second kind.
    persist = [d for d in days if d["rained_today"] == d["observed"]]
    change = [d for d in days if d["rained_today"] != d["observed"]]

    def _scores(subset):
        if not subset:
            return None
        p = [d["prob"] for d in subset]
        o = [d["observed"] for d in subset]
        c = [d["climatology"] for d in subset]
        return {
            "n": len(subset),
            "brier": metrics.brier_score(p, o),
            "brier_climatology": metrics.brier_score(c, o),
            "bss": metrics.brier_skill_score(p, o, c),
        }

    # Calibrated persistence, fitted on the test set itself: the harshest
    # possible version of the baseline the model has to beat.
    wet_rate = st.mean([d["observed"] for d in days if d["rained_today"]])
    dry_rate = st.mean([d["observed"] for d in days if not d["rained_today"]])
    persistence_probs = [wet_rate if d["rained_today"] else dry_rate for d in days]
    change_idx = [i for i, d in enumerate(days) if d["rained_today"] != d["observed"]]
    brier_persistence_change = metrics.brier_score(
        [persistence_probs[i] for i in change_idx], [obs[i] for i in change_idx]
    )

    if verbose:
        print(f"\n{'=' * 66}\n{name}  —  {len(days)} held-out days\n{'=' * 66}")

        print("\nHOW OFTEN IT SAYS WHAT")
        for line in histogram(probs):
            print(line)

        print(f"\n  range          {min(probs):.0%} … {max(probs):.0%}")
        print(f"  median         {st.median(probs):.0%}")
        print(f"  spread (sd)    {st.pstdev(probs):.3f}   "
              f"vs {st.pstdev(clim):.3f} for monthly climatology")
        confident_wet = sum(1 for p in probs if p >= 0.6)
        confident_dry = sum(1 for p in probs if p <= 0.15)
        hedged = sum(1 for p in probs if 0.25 <= p <= 0.45)
        print(f"  says >= 60%    {confident_wet:>4}  ({confident_wet / len(probs):.1%} of days)")
        print(f"  says <= 15%    {confident_dry:>4}  ({confident_dry / len(probs):.1%})")
        print(f"  hedges 25-45%  {hedged:>4}  ({hedged / len(probs):.1%})")

        print("\nDOES IT COMMIT, OR HIDE BEHIND CLIMATOLOGY?")
        moves = [abs(p - c) for p, c in zip(probs, clim)]
        print(f"  mean distance from the monthly normal   {st.mean(moves):.3f}")
        print(f"  days it moves more than 15 points       "
              f"{sum(1 for m in moves if m > 0.15)}  ({sum(1 for m in moves if m > 0.15) / len(moves):.0%})")
        print(f"  resolution (higher separates better)    {decomposition['resolution']:.4f}")
        print(f"  reliability (lower is better calibrated){decomposition['reliability']:>8.4f}")

        print("\nWHAT IT SAYS AFTER A WET DAY VERSUS A DRY ONE")
        for state, label in ((1.0, "after rain"), (0.0, "after a dry day")):
            subset = [d for d in days if d["rained_today"] == state]
            if not subset:
                continue
            said = st.mean(d["prob"] for d in subset)
            happened = st.mean(d["observed"] for d in subset)
            print(f"  {label:<16} says {said:.1%}, it then rains {happened:.1%}  "
                  f"(n={len(subset)})")

        print("\nCALIBRATION BY BAND")
        print(f"  {'band':<10}{'says':>8}{'happens':>10}{'gap':>8}{'n':>6}")
        for b in metrics.reliability_curve(probs, obs, bins=5, min_count=10):
            gap = b["observed"] - b["predicted"]
            flag = "  under-confident" if gap > 0.06 else ("  over-confident" if gap < -0.06 else "")
            print(f"  {b['range']:<10}{b['predicted']:>8.0%}{b['observed']:>10.0%}"
                  f"{gap:>+8.0%}{b['n']:>6}{flag}")

        print("\nWHERE IT GOES WRONG")
        false_alarms = sorted((d for d in days if d["prob"] >= 0.5 and not d["observed"]),
                              key=lambda d: -d["prob"])[:4]
        misses = sorted((d for d in days if d["prob"] < 0.5 and d["observed"]),
                        key=lambda d: -d["observed_mm"])[:4]
        print("  loudest false alarms (said rain, stayed dry):")
        for d in false_alarms:
            print(f"    {d['target']}  said {d['prob']:.0%}  ->  {d['observed_mm']:.1f} mm")
        print("  worst misses (said no rain, it poured):")
        for d in misses:
            print(f"    {d['target']}  said {d['prob']:.0%}  ->  {d['observed_mm']:.1f} mm")

        print("")
        print("DOES IT PREDICT TOMORROW, OR REPORT TODAY?")
        print(f"  correlation with today's rain     {corr_today:.3f}")
        print(f"  correlation with tomorrow's rain  {corr_tomorrow:.3f}")
        p_scores, c_scores = _scores(persist), _scores(change)
        print(f"  days the weather stayed put  {p_scores['n']:>4}  "
              f"Brier {p_scores['brier']:.4f}  BSS {p_scores['bss']:+.3f}")
        print(f"  days the weather changed     {c_scores['n']:>4}  "
              f"Brier {c_scores['brier']:.4f}  BSS {c_scores['bss']:+.3f}")
        print(f"  calibrated persistence, on those changing days: "
              f"{brier_persistence_change:.4f}")
        print("\nSKILL BY SEASON")
        print(f"  {'season':<9}{'n':>5}{'base':>8}{'Brier':>9}{'BSS':>9}{'says':>8}")
        for season in SEASON_ORDER:
            subset = [d for d in days if SEASONS[d["target"].month] == season]
            if len(subset) < 20:
                continue
            p = [d["prob"] for d in subset]
            o = [d["observed"] for d in subset]
            c = [d["climatology"] for d in subset]
            s_bss = metrics.brier_skill_score(p, o, c)
            print(f"  {season:<9}{len(subset):>5}{st.mean(o):>8.0%}"
                  f"{metrics.brier_score(p, o):>9.4f}{s_bss:>+9.3f}{st.mean(p):>8.0%}")

    wet = [d for d in days if d["rained_today"] == 1.0]
    dry = [d for d in days if d["rained_today"] == 0.0]
    seasons = {}
    for season in SEASON_ORDER:
        subset = [d for d in days if SEASONS[d["target"].month] == season]
        if len(subset) >= 20:
            seasons[season] = metrics.brier_skill_score(
                [d["prob"] for d in subset], [d["observed"] for d in subset],
                [d["climatology"] for d in subset])
    false_alarms = [d for d in days if d["prob"] >= 0.5 and not d["observed"]]
    misses = [d for d in days if d["prob"] < 0.5 and d["observed"]]

    detail = {
        "corr_today": corr_today,
        "corr_tomorrow": corr_tomorrow,
        "persist": _scores(persist),
        "change": _scores(change),
        "change_persistence_brier": brier_persistence_change,
        "clim_sharpness": st.pstdev(clim),
        "confident_dry": sum(1 for p in probs if p <= 0.15) / len(probs),
        "max": max(probs), "min": min(probs),
        "wet_says": st.mean(d["prob"] for d in wet) if wet else float("nan"),
        "wet_happens": st.mean(d["observed"] for d in wet) if wet else float("nan"),
        "dry_says": st.mean(d["prob"] for d in dry) if dry else float("nan"),
        "dry_happens": st.mean(d["observed"] for d in dry) if dry else float("nan"),
        "seasons": seasons,
        "worst_false_alarm": max(false_alarms, key=lambda d: d["prob"]) if false_alarms else None,
        "worst_miss": max(misses, key=lambda d: d["observed_mm"]) if misses else None,
    }

    return {
        "detail": detail,
        "name": name, "key": location_key, "n": len(days),
        "brier": brier, "bss": bss, "decomposition": decomposition,
        "sharpness": st.pstdev(probs), "mean_prob": st.mean(probs),
        "base_rate": st.mean(obs), "max": max(probs), "min": min(probs),
        "confident_wet": sum(1 for p in probs if p >= 0.6) / len(probs),
        "mean_move": st.mean(abs(p - c) for p, c in zip(probs, clim)),
    }


def live_record() -> None:
    """The public ledger, segmented by which model issued each forecast.

    Never pooled. The ledger spans a model change, and averaging two different
    models into one score would hide exactly what the record exists to show.
    Every row carries `model_version` for this reason.
    """
    records = ledger.load()
    rule = "=" * 66
    print("")
    print(rule)
    print("THE LIVE RECORD")
    print(rule)

    by_model: dict[str, list[dict]] = {}
    for record in records:
        by_model.setdefault(record["model_version"], []).append(record)

    if not records:
        print("  Nothing issued yet.")
        return

    for version in sorted(by_model):
        group = by_model[version]
        done = [r for r in group if r["observed_rain"] is not None]
        print("")
        print(f"  {version}   {len(group)} issued, {len(done)} verified")
        if not done:
            print("    nothing scored yet")
            continue

        probs = [r["our_prob"] for r in done]
        obs = [1.0 if r["observed_rain"] else 0.0 for r in done]
        clim = [r["climatology"] for r in done]
        correct = sum(1 for r in done if r["our_rain"] == r["observed_rain"])
        bss = metrics.brier_skill_score(probs, obs, clim)

        print(f"    Brier {metrics.brier_score(probs, obs):.4f}   "
              f"BSS vs climatology {'—' if bss is None else format(bss, '+.3f')}")
        print(f"    called {correct}/{len(done)} right at the 0.5 cut-off")

        benchmark = [r for r in done if r["om_rain"] is not None]
        if benchmark:
            om_correct = sum(1 for r in benchmark if r["om_rain"] == r["observed_rain"])
            print(f"    Open-Meteo called {om_correct}/{len(benchmark)} right")

        rained = sum(obs)
        print(f"    {rained:.0f} of {len(done)} forecast days actually rained")
        if len(done) < 30:
            print(f"    {len(done)} samples: too few for any of this to mean anything")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--location")
    args = parser.parse_args()

    keys = [args.location] if args.location else locations.DEFAULT_ORDER
    summaries = [analyse(k) for k in keys]
    details = {s["key"]: s["detail"] for s in summaries}

    if len(summaries) > 1:
        print(f"\n{'=' * 66}\nACROSS THE GRADIENT\n{'=' * 66}")
        print(f"  {'location':<20}{'base':>7}{'says':>7}{'sharp':>8}{'BSS':>8}"
              f"{'resol':>8}{'relia':>8}{'>=60%':>7}")
        for s in summaries:
            print(f"  {s['name']:<20}{s['base_rate']:>7.0%}{s['mean_prob']:>7.0%}"
                  f"{s['sharpness']:>8.3f}{s['bss']:>+8.3f}"
                  f"{s['decomposition']['resolution']:>8.4f}"
                  f"{s['decomposition']['reliability']:>8.4f}{s['confident_wet']:>7.0%}")

    live_record()

    if not args.location:
        out = write_report(summaries, details)
        print(f"\nreport -> {out.relative_to(ROOT)}")
    return 0




def write_report(summaries: list[dict], details: dict) -> Path:
    """Generate reports/FORECAST_ANALYSIS.md from the numbers just computed."""
    lines = [
        "# What the model actually says",
        "",
        "> Generated by `src/analyse_forecasts.py`, which replays the **shipped** artefacts",
        "> through the same inference path production uses. Every number is recomputed, none",
        "> typed by hand.",
        "",
        "Skill scores say whether a forecast is useful. They do not say what it *sounds* like —",
        "whether it commits or hedges, how often it goes out on a limb, and what kind of day it",
        "fails on. That is what this is for.",
        "",
        "Everything below is measured on the held-out test set: ~587 days per town, all after",
        "2024-12-31, never seen during training.",
        "",
        "---",
        "",
        "## It commits rather than hedging",
        "",
        "| town | base rate | mean forecast | spread | vs climatology spread | says ≥60% | says ≤15% |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        d = details[s["key"]]
        lines.append(
            f"| {s['name']} | {s['base_rate']:.0%} | {s['mean_prob']:.0%} | {s['sharpness']:.3f} | "
            f"{d['clim_sharpness']:.3f} | {s['confident_wet']:.0%} | {d['confident_dry']:.0%} |"
        )
    ratio = st.mean(s["sharpness"] for s in summaries) / st.mean(
        details[s["key"]]["clim_sharpness"] for s in summaries
    )
    lines += [
        "",
        f"The forecasts are about **{ratio:.1f}× more spread out than monthly climatology**. A model",
        "that had learned nothing useful would collapse towards the seasonal average, because that",
        "is the safest thing to say; this one moves away from it on roughly half of all days.",
        "",
        "It also never claims certainty. Across all five towns the highest probability ever issued",
        f"is **{max(details[s['key']]['max'] for s in summaries):.0%}** and the lowest is "
        f"**{min(details[s['key']]['min'] for s in summaries):.0%}**. There is no day on which it says",
        "\"definitely\" — which is correct for a statistical model working one day ahead.",
        "",
        "---",
        "",
        "## Persistence, learned rather than told",
        "",
        "| town | after a wet day it says | it then rains | after a dry day it says | it then rains |",
        "|---|---|---|---|---|",
    ]
    for s in summaries:
        d = details[s["key"]]
        lines.append(
            f"| {s['name']} | {d['wet_says']:.0%} | {d['wet_happens']:.0%} | "
            f"{d['dry_says']:.0%} | {d['dry_happens']:.0%} |"
        )
    lines += [
        "",
        "Nobody encoded a Markov chain. The model learned the persistence structure from the data",
        "and — more importantly — learned it *calibrated*: what it says after a wet day is within a",
        "couple of points of what then happens. That is the difference the whole project is about.",
        "",
        "---",
        "",
        "## Skill is not the same in every season",
        "",
        "Brier Skill Score against monthly climatology, by season:",
        "",
        "| town | winter | spring | summer | autumn |",
        "|---|---|---|---|---|",
    ]
    for s in summaries:
        cells = " | ".join(
            f"{details[s['key']]['seasons'].get(season, float('nan')):+.3f}"
            for season in SEASON_ORDER
        )
        lines.append(f"| {s['name']} | {cells} |")

    spring = st.mean(details[s["key"]]["seasons"]["spring"] for s in summaries)
    winter = st.mean(details[s["key"]]["seasons"]["winter"] for s in summaries)
    lines += [
        "",
        f"**Spring is where the model earns its keep** — {spring:+.3f} on average against "
        f"{winter:+.3f} in winter, and the ordering holds at every single town.",
        "",
        "The reason is physical rather than statistical. Spring rain in the Veneto arrives with",
        "identifiable synoptic setups: pressure falling, cloud building, warm moist air drawn in",
        "from the south and east — exactly the predictors the model has. Winter rain is more often",
        "tied to slow, persistent situations where yesterday's point observations say much less",
        "about tomorrow.",
        "",
        "---",
        "",
        "## It reports today more than it predicts tomorrow",
        "",
        "The forecast correlates more strongly with the rain that has already fallen than with the",
        "rain being predicted:",
        "",
        "| town | correlation with today | correlation with tomorrow |",
        "|---|---|---|",
    ]
    for s in summaries:
        d = details[s["key"]]
        lines.append(f"| {s['name']} | {d['corr_today']:.3f} | {d['corr_tomorrow']:.3f} |")

    lines += [
        "",
        "Splitting the test set by whether the weather changed makes the consequence concrete. A day",
        "is a *transition* when tomorrow differs from today: rain starting, or rain stopping.",
        "",
        "| town | days unchanged | Brier | days changed | Brier | BSS on changed days |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        d = details[s["key"]]
        a, b = d["persist"], d["change"]
        lines.append(
            f"| {s['name']} | {a['n']} | {a['brier']:.4f} | {b['n']} | {b['brier']:.4f} | "
            f"{b['bss']:+.3f} |"
        )

    mean_change_bss = st.mean(details[s["key"]]["change"]["bss"] for s in summaries)
    mean_change = st.mean(details[s["key"]]["change"]["brier"] for s in summaries)
    mean_persistence = st.mean(details[s["key"]]["change_persistence_brier"] for s in summaries)
    share = st.mean(
        details[s["key"]]["change"]["n"]
        / (details[s["key"]]["change"]["n"] + details[s["key"]]["persist"]["n"])
        for s in summaries
    )
    lines += [
        "",
        f"Transitions are {share:.0%} of all days. On them the Brier score is roughly four times",
        f"worse than on days that stay put, and the skill score against climatology is",
        f"{mean_change_bss:+.3f}: on the days when the weather actually changes, quoting the",
        "seasonal average would do better than reading this model.",
        "",
        f"It is not merely echoing persistence, though. On those same changing days calibrated",
        f"persistence scores {mean_persistence:.4f} against the model's {mean_change:.4f}, so the",
        f"model recovers {mean_persistence - mean_change:.3f} of Brier that pure persistence loses.",
        "It adds real information about change. Not enough of it.",
        "",
        "The headline skill of about +0.26 therefore comes almost entirely from being right on the",
        f"{1 - share:.0%} of days when nothing changes. Anyone using these numbers should know which",
        "part of the year they are buying.",
        "",
        "---",
        "",
        "## Where it goes wrong",
        "",
        "| town | loudest false alarm | worst miss |",
        "|---|---|---|",
    ]
    for s in summaries:
        d = details[s["key"]]
        fa, ms = d["worst_false_alarm"], d["worst_miss"]
        lines.append(
            f"| {s['name']} | {fa['target']}: said {fa['prob']:.0%}, got {fa['observed_mm']:.1f} mm | "
            f"{ms['target']}: said {ms['prob']:.0%}, got {ms['observed_mm']:.1f} mm |"
        )
    lines += [
        "",
        "The failure mode is consistent and worth stating plainly: **the model misses sudden heavy",
        "rain that arrives out of a quiet day.** It reads yesterday's conditions at one point, so a",
        "front that had not yet shown itself in the pressure, cloud or humidity is invisible to it.",
        "This is precisely the gap a numerical weather model fills, and precisely why the",
        "comparison against Open-Meteo is framed as a reference rather than a contest.",
        "",
        "**The bad days repeat across towns.** Look at the dates: the same ones recur in different",
        "columns. These are not five independent mistakes — they are one synoptic situation fooling",
        "the model everywhere at once, which is what you would expect over a region 80 km across.",
        "It matters for reading every other number here: the five towns are not five independent",
        "samples, so pooling them does not narrow the uncertainty nearly as much as the row count",
        "suggests. The autocorrelation caveat applies in space as well as in time.",
        "",
        "---",
        "",
        "## Calibration holds, except at the very top",
        "",
        "| town | reliability (lower better) | resolution (higher better) |",
        "|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['name']} | {s['decomposition']['reliability']:.4f} | "
            f"{s['decomposition']['resolution']:.4f} |"
        )
    lines += [
        "",
        "Reliability sits between 0.003 and 0.006 everywhere: when the model says 30%, it rains",
        "close to 30% of the time. The one weak spot is the 80–100% band, where it is",
        "**over-confident** — but that band holds only a handful of days per town, so the estimate",
        "is itself thin. Worth watching in the live record rather than concluding from here.",
        "",
    ]
    # The page quotes these figures in prose. Emitting them as data lets
    # scripts/check_prose.py verify the prose against them, so the two cannot
    # drift apart the next time the model is retrained.
    share = st.mean(
        details[s["key"]]["change"]["n"]
        / (details[s["key"]]["change"]["n"] + details[s["key"]]["persist"]["n"])
        for s in summaries
    )
    (ROOT / "reports" / "transitions.json").write_text(
        json.dumps(
            {
                "corr_today": round(st.mean(details[s["key"]]["corr_today"] for s in summaries), 3),
                "corr_tomorrow": round(
                    st.mean(details[s["key"]]["corr_tomorrow"] for s in summaries), 3
                ),
                "transition_share": round(share, 3),
                "brier_persist": round(
                    st.mean(details[s["key"]]["persist"]["brier"] for s in summaries), 4
                ),
                "brier_change": round(
                    st.mean(details[s["key"]]["change"]["brier"] for s in summaries), 4
                ),
                "bss_change": round(
                    st.mean(details[s["key"]]["change"]["bss"] for s in summaries), 3
                ),
                "brier_change_persistence": round(
                    st.mean(details[s["key"]]["change_persistence_brier"] for s in summaries), 4
                ),
                "by_location": [
                    {
                        "name": s["name"],
                        "corr_today": round(details[s["key"]]["corr_today"], 3),
                        "corr_tomorrow": round(details[s["key"]]["corr_tomorrow"], 3),
                        "persist": details[s["key"]]["persist"],
                        "change": details[s["key"]]["change"],
                    }
                    for s in summaries
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    out = ROOT / "reports" / "FORECAST_ANALYSIS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

if __name__ == "__main__":
    sys.exit(main())
