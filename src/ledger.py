"""The forecast ledger — the thing that makes this project hard to argue with.

One append-only JSON Lines file. Each record is written with its outcome EMPTY
and filled in by a later run, so the git history proves the forecast existed
before the day it forecast. That is a property no backtest can have: you cannot
tune on data that does not exist yet.

Two rules follow, and both are enforced here rather than trusted:

  1. keyed on (city, target_date) — a second run on the same day must not
     duplicate a record;
  2. an issued forecast is NEVER rewritten. Only the observation fields may be
     filled, and only once. Rewriting a prediction would destroy exactly the
     property that makes the ledger worth keeping.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# fields written when the forecast is issued; immutable afterwards
ISSUED_FIELDS = (
    "issued_at", "city", "target_date", "our_prob", "our_rain",
    "om_prob", "om_prob_mean", "om_precip_mm", "om_rain",
    "climatology", "model_version",
)
# fields a later run may fill in, exactly once
OUTCOME_FIELDS = ("observed_mm", "observed_rain", "scored_at")


class LedgerError(RuntimeError):
    """An attempt to violate the append-only contract."""


def path() -> Path:
    return ROOT / "public" / "forecasts.jsonl"


def load() -> list[dict]:
    file = path()
    if not file.is_file():
        return []
    records = []
    for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise LedgerError(f"{file.name}:{line_no} is not valid JSON: {exc}") from exc
    return records


def save(records: list[dict]) -> None:
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda r: (r["target_date"], r["city"]))
    file.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in ordered), encoding="utf-8"
    )


def key(record: dict) -> tuple[str, str]:
    return record["city"], record["target_date"]


def index(records: list[dict]) -> dict[tuple[str, str], dict]:
    return {key(r): r for r in records}


def add_forecast(records: list[dict], record: dict) -> bool:
    """Append a newly issued forecast. Returns False if one already exists.

    Refusing rather than replacing is the whole point: whatever was published
    first is what gets scored.
    """
    if key(record) in index(records):
        return False
    missing = [f for f in ISSUED_FIELDS if f not in record]
    if missing:
        raise LedgerError(f"forecast record missing fields: {missing}")
    records.append({**record, "observed_mm": None, "observed_rain": None, "scored_at": None})
    return True


def score(record: dict, observed_mm: float, threshold_mm: float, scored_at: str) -> bool:
    """Fill in the outcome. Returns False if it was already scored.

    Mutates only the outcome fields; anything else would be rewriting history.
    """
    if record.get("observed_rain") is not None:
        return False
    record["observed_mm"] = round(observed_mm, 2)
    record["observed_rain"] = bool(observed_mm >= threshold_mm)
    record["scored_at"] = scored_at
    return True


def verified(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("observed_rain") is not None]


def pending(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("observed_rain") is None]
