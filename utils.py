
import re
from typing import Optional, Tuple

COORD_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")

def parse_latlon(text: str) -> Optional[Tuple[float, float]]:
    m = COORD_RE.match(text.strip())
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if -90 <= a <= 90 and -180 <= b <= 180:
        lat, lon = a, b
        return lon, lat
    else:
        lon, lat = a, b
        return lon, lat

# extra validation

def is_valid_coord(pt: Tuple[float, float]) -> bool:
    try:
        lon, lat = float(pt[0]), float(pt[1])
        return (-180.0 <= lon <= 180.0) and (-90.0 <= lat <= 90.0)
    except Exception:
        return False
