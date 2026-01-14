
import os
import requests
from typing import Optional, Tuple, Dict, List

from utils import haversine_km

ORS_BASE = "https://api.openrouteservice.org"

class ORSClient:
    def __init__(self, api_key: Optional[str] = None, debug: bool=False):
        self.api_key = api_key or os.getenv("ORS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing ORS_API_KEY. Set it in Streamlit secrets or environment.")
        self.headers = {"Authorization": self.api_key, "Content-Type": "application/json", "Accept": "application/json"}
        self.debug = debug

    def _log(self, msg: str):
        if self.debug:
            print(msg)

    def _pick_nearest(self, features: List[Dict], focus_pt: Optional[Tuple[float,float]]) -> Optional[Tuple[float,float]]:
        if not features:
            return None
        if not focus_pt:
            coords = features[0]["geometry"]["coordinates"]
            return float(coords[0]), float(coords[1])
        lon0, lat0 = focus_pt
        best = None
        best_d = 1e18
        for f in features:
            c = f.get("geometry", {}).get("coordinates")
            if not c:
                continue
            d = haversine_km(lon0, lat0, float(c[0]), float(c[1]))
            if d < best_d:
                best_d = d
                best = (float(c[0]), float(c[1]))
        return best

    def geocode_best(self, text: str, boundary_country: Optional[str] = None, city_hint: Optional[str] = None, focus_pt: Optional[Tuple[float,float]] = None) -> Optional[Tuple[float, float]]:
        q = (text or '').strip()
        if not q:
            return None
        # Construct base params
        base = {"text": q, "size": 10, "layers": "venue,address,street,locality"}
        if boundary_country:
            base["boundary.country"] = boundary_country
        if focus_pt:
            base["focus.point.lon"], base["focus.point.lat"] = focus_pt[0], focus_pt[1]
            # Tight circle around focus (3km radius); Pelias supports boundary.circle.*
            base["boundary.circle.lon"], base["boundary.circle.lat"] = focus_pt[0], focus_pt[1]
            base["boundary.circle.radius"] = 3000  # meters
        url_search = f"{ORS_BASE}/geocode/search"
        try:
            r = requests.get(url_search, headers={"Authorization": self.api_key}, params=base, timeout=30)
            if r.status_code == 200:
                feats = r.json().get("features") or []
                pick = self._pick_nearest(feats, focus_pt)
                if pick:
                    return pick
        except Exception as e:
            self._log(f"search failed: {e}")

        # Add city hint if provided
        if city_hint:
            p2 = base.copy(); p2["text"] = f"{q}, {city_hint}"
            try:
                r2 = requests.get(url_search, headers={"Authorization": self.api_key}, params=p2, timeout=30)
                if r2.status_code == 200:
                    feats2 = r2.json().get("features") or []
                    pick2 = self._pick_nearest(feats2, focus_pt)
                    if pick2:
                        return pick2
            except Exception as e:
                self._log(f"search+hint failed: {e}")

        # Structured (address + locality)
        if city_hint:
            url_struct = f"{ORS_BASE}/geocode/search/structured"
            p3 = {"address": q, "locality": city_hint, "size": 10}
            if boundary_country:
                p3["boundary.country"] = boundary_country
            if focus_pt:
                p3["focus.point.lon"], p3["focus.point.lat"] = focus_pt[0], focus_pt[1]
                p3["boundary.circle.lon"], p3["boundary.circle.lat"] = focus_pt[0], focus_pt[1]
                p3["boundary.circle.radius"] = 3000
            try:
                r3 = requests.get(url_struct, headers={"Authorization": self.api_key}, params=p3, timeout=30)
                if r3.status_code == 200:
                    feats3 = r3.json().get("features") or []
                    pick3 = self._pick_nearest(feats3, focus_pt)
                    if pick3:
                        return pick3
            except Exception as e:
                self._log(f"structured failed: {e}")

        # Autocomplete
        url_auto = f"{ORS_BASE}/geocode/autocomplete"
        p4 = {"text": q, "size": 10}
        if boundary_country:
            p4["boundary.country"] = boundary_country
        if focus_pt:
            p4["focus.point.lon"], p4["focus.point.lat"] = focus_pt[0], focus_pt[1]
        try:
            r4 = requests.get(url_auto, headers={"Authorization": self.api_key}, params=p4, timeout=30)
            if r4.status_code == 200:
                feats4 = r4.json().get("features") or []
                pick4 = self._pick_nearest(feats4, focus_pt)
                if pick4:
                    return pick4
        except Exception as e:
            self._log(f"autocomplete failed: {e}")

        # Simplified query fallback (remove stop words)
        try:
            from utils import simplify_query
            simp = simplify_query(q)
            if simp and simp != q:
                p5 = base.copy(); p5["text"] = simp
                r5 = requests.get(url_search, headers={"Authorization": self.api_key}, params=p5, timeout=30)
                if r5.status_code == 200:
                    feats5 = r5.json().get("features") or []
                    pick5 = self._pick_nearest(feats5, focus_pt)
                    if pick5:
                        return pick5
        except Exception as e:
            self._log(f"search simplified failed: {e}")

        return None

    def directions(self, start: Tuple[float, float], end: Tuple[float, float], profile: str = "driving-car") -> Dict:
        url = f"{ORS_BASE}/v2/directions/{profile}"
        body = {"coordinates": [list(start), list(end)], "preference": "recommended", "instructions": False}
        try:
            r = requests.post(url, headers=self.headers, json=body, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._log(f"POST directions failed: {e}. Falling back to GET.")
            out = {"routes": []}
            for pref in ("recommended", "shortest"):
                params = {"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}", "preference": pref}
                try:
                    g = requests.get(url, headers={"Authorization": self.api_key, "Accept": "application/json"}, params=params, timeout=60)
                    if g.status_code == 200:
                        j = g.json()
                        if j.get("routes"):
                            out["routes"].append(j["routes"][0])
                except Exception as e2:
                    self._log(f"GET {pref} failed: {e2}")
            return out

    @staticmethod
    def pick_short_long_distances(resp: Dict) -> Tuple[Optional[float], Optional[float]]:
        try:
            distances_m = [route.get("summary", {}).get("distance") for route in resp.get("routes", []) if route.get("summary", {}).get("distance") is not None]
            if not distances_m:
                return None, None
            km = [d/1000.0 for d in distances_m]
            return min(km), max(km)
        except Exception:
            return None, None
