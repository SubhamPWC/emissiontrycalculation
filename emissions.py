
import streamlit as st
import re
from typing import Optional

DEFAULT_FACTORS_WTW = {
    "Car|Petrol": 0.180,
    "Car|Diesel": 0.164,
    "Van|Diesel": 0.280,
    "Truck|Diesel": 0.650,
    "Bus|Diesel": 0.822,
    "Two-wheeler|Petrol": 0.070,
    "EV|Electricity": 0.050,
    "12-Seater Traveller|Diesel" : 0.390,
    "35-Seater Bus|Diesel" : 0.840,
    "50-Seater Bus|Diesel" : 0.810,
    "Bus|Diesel" : 0.810,
}

VEHICLE_MAP = [
    (r"bus", "Bus"),
    (r"hgv|truck|lorry", "Truck"),
    (r"van", "Van"),
    (r"bike|two|motor", "Two-wheeler"),
    (r"ev|electric", "EV"),
    (r"car|sedan|hatch|suv", "Car"),
]

FUEL_MAP = [
    (r"diesel", "Diesel"),
    (r"petrol|gasoline", "Petrol"),
    (r"cng|lng|lpg", "CNG"),
    (r"electric|ev", "Electricity"),
    (r"hybrid", "Hybrid"),
]

class EmissionModel:
    def __init__(self, scope: str = "WTW"):
        self.scope = scope
        try:
            self.overrides = dict(st.secrets.get("EMISSION_FACTORS_WTW", {}))
        except Exception:
            self.overrides = {}

    @staticmethod
    def normalize_vehicle(v: str) -> str:
        vlow = v.lower()
        for pat, canon in VEHICLE_MAP:
            if re.search(pat, vlow):
                return canon
        return "Car"

    @staticmethod
    def normalize_fuel(f: str) -> str:
        flow = f.lower()
        for pat, canon in FUEL_MAP:
            if re.search(pat, flow):
                return canon
        return "Diesel"

    def factor_wtw(self, vehicle_type: str, fuel_type: str) -> Optional[float]:
        v = self.normalize_vehicle(vehicle_type)
        f = self.normalize_fuel(fuel_type)
        key = f"{v}|{f}"
        if key in self.overrides:
            try:
                return float(self.overrides[key])
            except Exception:
                pass
        return DEFAULT_FACTORS_WTW.get(key)

    def emissions(self, km: Optional[float], vehicle_type: str, fuel_type: str) -> Optional[float]:
        if km is None:
            return None
        f = self.factor_wtw(vehicle_type, fuel_type)
        if f is None:
            return None
        return km * f
