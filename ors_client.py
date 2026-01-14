
import os
import requests
from typing import Optional, Tuple, Dict

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

    def geocode_best(self, text: str, boundary_country: Optional[str] = None, city_hint: Optional[str] = None) -> Optional[Tuple[float, float]]:
        q = (text or '').strip()
        if not q:
            return None
        # 1) direct search
        params = {"text": q, "size": 1, "layers": "venue,address,street,locality"}
        url_search = f"{ORS_BASE}/geocode/search"
        try:
            r = requests.get(url_search, headers={"Authorization": self.api_key}, params=params, timeout=30)
            if r.status_code == 200 and (r.json().get("features") or []):
                coords = r.json()["features"][0]["geometry"]["coordinates"]
                return float(coords[0]), float(coords[1])
        except Exception as e:
            self._log(f"search failed: {e}")
        # 2) search + country
        if boundary_country:
            params2 = params.copy(); params2["boundary.country"] = boundary_country
            try:
                r2 = requests.get(url_search, headers={"Authorization": self.api_key}, params=params2, timeout=30)
                if r2.status_code == 200 and (r2.json().get("features") or []):
                    coords = r2.json()["features"][0]["geometry"]["coordinates"]
                    return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"search+country failed: {e}")
        # 3) search + city hint
        if city_hint:
            params3 = params.copy(); params3["text"] = f"{q}, {city_hint}"
            if boundary_country:
                params3["boundary.country"] = boundary_country
            try:
                r3 = requests.get(url_search, headers={"Authorization": self.api_key}, params=params3, timeout=30)
                if r3.status_code == 200 and (r3.json().get("features") or []):
                    coords = r3.json()["features"][0]["geometry"]["coordinates"]
                    return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"search+hint failed: {e}")
        # 4) structured
        if city_hint:
            params4 = {"address": q, "locality": city_hint, "size": 1}
            url_struct = f"{ORS_BASE}/geocode/search/structured"
            try:
                r4 = requests.get(url_struct, headers={"Authorization": self.api_key}, params=params4, timeout=30)
                if r4.status_code == 200 and (r4.json().get("features") or []):
                    coords = r4.json()["features"][0]["geometry"]["coordinates"]
                    return float(coords[0]), float(coords[1])
            except Exception as e:
                self._log(f"structured failed: {e}")
        # 5) autocomplete
        params5 = {"text": q, "size": 1}
        if boundary_country:
            params5["boundary.country"] = boundary_country
        url_auto = f"{ORS_BASE}/geocode/autocomplete"
        try:
            r5 = requests.get(url_auto, headers={"Authorization": self.api_key}, params=params5, timeout=30)
            if r5.status_code == 200 and (r5.json().get("features") or []):
                coords = r5.json()["features"][0]["geometry"]["coordinates"]
                return float(coords[0]), float(coords[1])
        except Exception as e:
            self._log(f"autocomplete failed: {e}")
        return None

    def directions(self, start: Tuple[float, float], end: Tuple[float, float], profile: str = "driving-car") -> Dict:
        """POST directions; if 400/other, fallback to GET (recommended & shortest)."""
        url = f"{ORS_BASE}/v2/directions/{profile}"
        body = {"coordinates": [list(start), list(end)], "preference": "recommended", "instructions": False}
        try:
            r = requests.post(url, headers=self.headers, json=body, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._log(f"POST directions failed: {e}. Falling back to GET.")
            # Fallback: GET recommended and shortest
            rec_params = {"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}", "preference": "recommended"}
            sho_params = {"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}", "preference": "shortest"}
            out = {"routes": []}
            try:
                r_rec = requests.get(url, headers={"Authorization": self.api_key, "Accept": "application/json"}, params=rec_params, timeout=60)
                if r_rec.status_code == 200:
                    j = r_rec.json()
                    if j.get("routes"):
                        out["routes"].append(j["routes"][0])
            except Exception as e2:
                self._log(f"GET recommended failed: {e2}")
            try:
                r_sho = requests.get(url, headers={"Authorization": self.api_key, "Accept": "application/json"}, params=sho_params, timeout=60)
                if r_sho.status_code == 200:
                    j2 = r_sho.json()
                    if j2.get("routes"):
                        out["routes"].append(j2["routes"][0])
            except Exception as e3:
                self._log(f"GET shortest failed: {e3}")
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
