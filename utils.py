

import re
from typing import Optional, Tuple

COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")

ALIASES = {
    "katriguppe signal": "Kathriguppe Signal",
    "kathriguppe signal": "Kathriguppe Signal",
    "whitefield bus stop": "Whitefield Bus Stop",
    "yelahanka nes bus stop": "Yelahanka NES Bus Stop",
}

STOP_WORDS = ["bus stop", "busstand", "signal", "circle", "junction"]

def normalize_place_name(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text)).strip()
    low = t.lower()
    if low in ALIASES:
        return ALIASES[low]
    # Normalize 'BUS stop' casing
    t = re.sub(r"BUS\s*stop", "Bus Stop", t, flags=re.I)
    return t


def simplify_query(text: str) -> str:
    t = str(text).lower()
    for sw in STOP_WORDS:
        t = t.replace(sw, "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_latlon(text: str) -> Optional[Tuple[float, float]]:
    m = COORD_RE.match(str(text).strip())
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if -90 <= a <= 90 and -180 <= b <= 180:
        lat, lon = a, b
        return lon, lat
    else:
        lon, lat = a, b
        return lon, lat


def is_valid_coord(pt: Tuple[float, float]) -> bool:
    try:
        lon, lat = float(pt[0]), float(pt[1])
        return (-180.0 <= lon <= 180.0) and (-90.0 <= lat <= 90.0)
    except Exception:
        return False
