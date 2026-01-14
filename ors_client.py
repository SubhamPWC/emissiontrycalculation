
import os
import requests
from typing import Optional, Tuple, Dict

ORS_BASE = "https://api.openrouteservice.org"

class ORSClient:
    def __init__(self, api_key: Optional[str] = None, debug: bool=False):
        self.api_key = api_key or os.getenv("ORS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing ORS_API_KEY. Set it in Streamlit secrets or environment.")
        self.headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        self.debug = debug

    def _log(self, msg: str):
        if self.debug:
            print(msg)

    def geocode_best(self, text: str, boundary_country: Optional[str] = None, city_hint: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """Best-effort forward geocode to (lon, lat).
        Strategy: search -> search with country -> search+city hint -> structured -> autocomplete.
        Returns first match or None.
        """
        # Normalize input
        q = (text or '').strip()
        if not q:
            return None

        # 1) /geocode/search (direct)
        params = {"text": q, "size": 1, "layers": "venue,address,street,locality"}
        url_search = f"{ORS_BASE}/geocode/search"
        try:
            r = requests.get(url_search, headers={"Authorization": self.api_key}, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                feats = data.get("features") or []
                if feats:
                    coords = feats[0]["geometry"]["coordinates"]
                    return float(coords[0]), float(coords[1])
        except Exception as e:
            self._log(f"search failed: {e}")

        # 2) /geocode/search with boundary.country
        if boundary_country:
            params2 = params.copy()
            params2["boundary.country"] = boundary_country
            try:
                r2 = requests.get(url_search, headers={"Authorization": self.api_key}, params=params2, timeout=30)
                if r2.status_code == 200:
                    data2 = r2.json()
                    feats2 = data2.get("features") or []
                    if feats2:
                        coords = feats2[0]["geometry"]["coordinates"]
                        return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"search+country failed: {e}")

        # 3) search with appended city hint
        if city_hint:
            params3 = params.copy()
            params3["text"] = f"{q}, {city_hint}"
            if boundary_country:
                params3["boundary.country"] = boundary_country
            try:
                r3 = requests.get(url_search, headers={"Authorization": self.api_key}, params=params3, timeout=30)
                if r3.status_code == 200:
                    data3 = r3.json()
                    feats3 = data3.get("features") or []
                    if feats3:
                        coords = feats3[0]["geometry"]["coordinates"]
                        return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"search+hint failed: {e}")

        # 4) /geocode/search/structured (address + locality)
        if city_hint:
            params4 = {"address": q, "locality": city_hint, "size": 1}
            url_struct = f"{ORS_BASE}/geocode/search/structured"
            try:
                r4 = requests.get(url_struct, headers={"Authorization": self.api_key}, params=params4, timeout=30)
                if r4.status_code == 200:
                    data4 = r4.json()
                    feats4 = data4.get("features") or []
                    if feats4:
                        coords = feats4[0]["geometry"]["coordinates"]
                        return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"structured failed: {e}")

        # 5) /geocode/autocomplete (last resort)
        params5 = {"text": q, "size": 1}
        if boundary_country:
            params5["boundary.country"] = boundary_country
        url_auto = f"{ORS_BASE}/geocode/autocomplete"
        try:
            r5 = requests.get(url_auto, headers={"Authorization": self.api_key}, params=params5, timeout=30)
            if r5.status_code == 200:
                data5 = r5.json()
                feats5 = data5.get("features") or []
                if feats5:
                    coords = feats5[0]["geometry"]["coordinates"]
                    return float(coords[0]), float(coords[1])
        except Exception as e:
            self._log(f"autocomplete failed: {e}")

        return None

    def directions(self, start: Tuple[float, float], end: Tuple[float, float], profile: str = "driving-car", request_alternatives: bool = True) -> Dict:
        body = {
            "coordinates": [list(start), list(end)],
            "preference": "recommended",
            "instructions": False
        }
        if request_alternatives:
            body["alternative_routes"] = {
                "share_factor": 0.6,
                "target_count": 2,
                "min_diff_time": 300
            }
        url = f"{ORS_BASE}/v2/directions/{profile}"
        r = requests.post(url, headers=self.headers, json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def pick_short_long_distances(resp: Dict) -> Tuple[Optional[float], Optional[float]]:
        try:
            distances_m = [route["summary"]["distance"] for route in resp.get("routes", [])]
            if not distances_m:
                return None, None
            km = [d/1000.0 for d in distances_m]
            return min(km), max(km)
        except Exception:
            return None, None
