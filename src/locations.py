"""The five Veneto locations, and why these five.

They are not a random selection: together they span a real rainfall gradient
across a small region, from the Prealpine foothills to the lagoon. If the
pipeline is sound, the fitted coefficients should differ between them in ways a
forecaster would recognise — and if they do not, that is a finding worth
reporting rather than hiding.

    Bassano del Grappa   foothills, wettest, orographic uplift    ~1300 mm/yr
    Conegliano           Prosecco hills, still Prealpine          ~1250 mm/yr
    Vicenza              plain, but close to the foothills        ~1100 mm/yr
    Padova               continental Po plain, drier              ~ 850 mm/yr
    Venezia              lagoon, maritime, mildest                ~ 800 mm/yr

Annual figures are indicative, taken from regional climatology; the measured
values come out of the pipeline itself and are reported in reports/REPORT.md.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    lat: float
    lon: float
    note: str


LOCATIONS: dict[str, Location] = {
    loc.key: loc
    for loc in (
        Location("bassano", "Bassano del Grappa", 45.766, 11.734,
                 "Prealpine foothills — the wettest of the five, orographic uplift"),
        Location("conegliano", "Conegliano", 45.888, 12.297,
                 "Prosecco DOCG hills — the location the model was first built for"),
        Location("vicenza", "Vicenza", 45.546, 11.547,
                 "Plain, but close enough to the foothills to feel them"),
        Location("padova", "Padova", 45.407, 11.876,
                 "Continental Po plain — drier, wider temperature range"),
        Location("venezia", "Venezia", 45.438, 12.327,
                 "Lagoon and coast — maritime, the mildest of the five"),
    )
}

DEFAULT_ORDER = ["bassano", "conegliano", "vicenza", "padova", "venezia"]


def get(key: str) -> Location:
    try:
        return LOCATIONS[key]
    except KeyError:
        known = ", ".join(sorted(LOCATIONS))
        raise SystemExit(f"unknown location {key!r} — known locations: {known}")


def all_locations() -> list[Location]:
    """Ordered along the rainfall gradient, wettest first."""
    return [LOCATIONS[k] for k in DEFAULT_ORDER]
