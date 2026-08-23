#!/usr/bin/env python3
"""Keeps the page and the README from drifting, in wording and in numbers.

Two jobs.

**Style.** The prose follows a house style: no em dash used as a rhetorical
pause, no rhetorical questions as headings, no "not X, it is Y" construction.
Without a check these creep back within a couple of edits, because they are
comfortable to write.

**Numbers.** The page states figures in prose. Those figures come from the
artefacts and from reports/transitions.json, and nothing otherwise stops them
from going stale after a retrain, which has already happened once: the tagline
said "17 coefficients" for three days after there were 25.

    python scripts/check_prose.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "js" / "i18n.js"
README = ROOT / "README.md"

# Style rules. Kept few and mechanical: a check nobody trusts gets switched off.
BANNED = [
    ("—", "em dash used as a rhetorical pause; use a full stop, comma or colon"),
    (r"\bnon è [^.,;]{2,40}, è\b", "the \"non è X, è Y\" construction"),
    (r"\bis not [^.,;]{2,40}, it is\b", "the \"is not X, it is Y\" construction"),
]
# Headings are labels, not lessons. Anything ending in a question mark is a
# heading pretending to teach, with two deliberate exceptions that are the
# actual subject of their section.
HEADING_QUESTION_ALLOWED = {"site.title", "reliability.heading"}


def page_strings() -> dict[str, str]:
    """Pull the prose out of i18n.js without running JavaScript.

    A parser would be overkill: the file is a flat table of string literals, and
    a regex that grabs quoted runs is enough to see what a reader would see.
    """
    text = PAGE.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for match in re.finditer(r'^\s{4}"([\w.\- ()/]+)":\s*(.+?)(?=\n\s{4}"|\n\s*\}|\Z)',
                             text, re.S | re.M):
        key, raw = match.group(1), match.group(2)
        pieces = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
        out.setdefault(key, " ".join(pieces))
    return out


def check_style(problems: list[str]) -> None:
    for key, value in page_strings().items():
        for pattern, why in BANNED:
            if re.search(pattern, value):
                problems.append(f"i18n {key}: {why}")
        if key.endswith(".heading") and "?" in value and key not in HEADING_QUESTION_ALLOWED:
            problems.append(f"i18n {key}: heading is a rhetorical question, use a label")

    readme = README.read_text(encoding="utf-8")
    # Code fences and tables are exempt: an em dash inside a generated table is
    # not a rhetorical flourish.
    prose = re.sub(r"```.*?```", "", readme, flags=re.S)
    prose = "\n".join(l for l in prose.splitlines() if not l.lstrip().startswith("|"))
    for pattern, why in BANNED:
        for line in prose.splitlines():
            if re.search(pattern, line):
                problems.append(f"README: {why}\n    {line.strip()[:90]}")
                break


def check_numbers(problems: list[str]) -> None:
    """Every figure quoted in prose must match the data it claims to come from."""
    strings = page_strings()
    blob = " ".join(strings.values()) + " " + README.read_text(encoding="utf-8")

    model = json.loads((ROOT / "models" / "vicenza.json").read_text(encoding="utf-8"))
    n_features = len(model["feature_names"])
    n_test = model["thresholds"]["1"]["test_metrics"]["n"]
    n_models = sum(
        len(json.loads(p.read_text(encoding="utf-8"))["thresholds"])
        for p in (ROOT / "models").glob("*.json")
    )

    expected = [
        (rf"\b{n_features} (?:coefficient|coefficienti|numeri|numbers)", "feature count"),
        (rf"\b{n_test}\b", "held-out day count"),
    ]
    for pattern, what in expected:
        if not re.search(pattern, blob):
            problems.append(f"no prose states the correct {what} ({pattern})")

    stale = [
        (r"\b17 (?:coefficient|coefficienti|numbers|numeri)", "17 features"),
        (r"\b58[0-8] (?:held-out|giorni|days)", "an old held-out count"),
        (r"~9 KB", "the old artefact size"),
    ]
    for pattern, what in stale:
        if re.search(pattern, blob):
            problems.append(f"stale figure still published: {what}")

    path = ROOT / "reports" / "transitions.json"
    if not path.is_file():
        problems.append("reports/transitions.json missing; run src/analyse_forecasts.py")
        return
    t = json.loads(path.read_text(encoding="utf-8"))

    # Figures the prose quotes, allowing the rounding a sentence naturally uses
    # and both decimal conventions. 0.683 may appear as 0.68 or 0,68; what is
    # rejected is a number that rounds to something else entirely.
    def quoted(value: float, label: str) -> None:
        forms = {f"{round(value, d):g}" for d in (2, 3, 4)}
        forms |= {f.replace(".", ",") for f in forms}
        if not any(f in blob for f in forms):
            problems.append(
                f"prose does not quote the measured {label} "
                f"({', '.join(sorted(forms))})"
            )

    quoted(t["corr_today"], "correlation with today")
    quoted(t["corr_tomorrow"], "correlation with tomorrow")
    quoted(t["brier_change"], "Brier on transition days")
    quoted(t["brier_change_persistence"], "persistence Brier on transition days")
    quoted(abs(t["bss_change"]), "skill on transition days")

    share = round(t["transition_share"] * 100)
    if f"{share}%" not in blob:
        problems.append(f"prose does not quote the measured transition share ({share}%)")


def main() -> int:
    problems: list[str] = []
    check_style(problems)
    check_numbers(problems)

    if problems:
        print(f"{len(problems)} problem(s):\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("prose: style rules hold, and every quoted figure matches the data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
