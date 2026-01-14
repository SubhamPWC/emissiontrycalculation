
import re
from typing import Optional, Tuple
import math

COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")

# Generic stop words often appended to POIs; removed only for fallback try
STOP_WORDS = ["bus stop", "busstand", "signal", "circle", "junction", "stop", "stand"]

def normalize_place_name(text: str) -> str:
    # Trim extra spaces; standardize casing of 'Bus Stop' generically (no specific names)
    t = re.sub(r"\s+", " ", str(text)).strip()
    t = re.sub(r"BUS\s*STOP", "Bus Stop", t, flags=re.I)
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


def haversine_km(lon1, lat1, lon2, lat2):
    # Compute distance between two lon/lat points in km
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R*c
