
import os
import pandas as pd
import streamlit as st
import altair as alt
from ors_client import ORSClient
from emissions import EmissionModel
from utils import parse_latlon, is_valid_coord

st.set_page_config(page_title="Fleet Emission Tracker", layout="wide")

# HEADER
st.markdown(
    """
    <style>
    .kpi {background: #121826; padding:16px; border-radius: 12px; border:1px solid #2a2f3a;}
    .panel {background:#0b0f19; padding:16px; border-radius:12px; border:1px solid #1f2330;}
    .titleband {background: linear-gradient(90deg,#6a00ff 0%,#ff0080 50%,#00c2ff 100%);
                color:white; padding:22px; border-radius:12px; font-size:20px; font-weight:700;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="titleband">Fleet Emission Tracker</div>', unsafe_allow_html=True)

# SIDEBAR
scope = st.sidebar.selectbox("Emission scope (WTW)", ["WTW"], index=0)
profile = st.sidebar.selectbox("ORS profile", ["driving-car", "driving-hgv"], index=0)
country_bias = st.sidebar.text_input("Geocode country bias (ISO)", value="IN")
city_hint = st.sidebar.text_input("City/Region hint (optional)", value="")

# DATA INPUT
st.subheader("Upload Fleet Activity CSV")
_data_help = "Expected columns: Type of Asset (FROM), Type of vehicle, Location (TO), Type of fuel"
file = st.file_uploader(_data_help, type=["csv"])
if not file:
    st.info("Please upload your CSV to proceed.")
    st.stop()

df = pd.read_csv(file)
required = ["Type of Asset", "Type of vehicle", "Location", "Type of fuel"]
missing_cols = [c for c in required if c not in df.columns]
if missing_cols:
    st.error(f"Missing required column(s): {', '.join(missing_cols)}")
    st.stop()

# ORS CLIENT
api_key = st.secrets.get("ORS_API_KEY", os.getenv("ORS_API_KEY"))
if not api_key:
    st.error("Missing ORS_API_KEY. Add it in Streamlit Cloud Secrets.")
    st.stop()
client = ORSClient(api_key=api_key)

# Auto city hint detection

def auto_city_hint(a: str, b: str) -> str:
    s = f"{a} {b}".lower()
    for ct in ["bengaluru", "bangalore", "kolkata", "mumbai", "delhi", "hyderabad", "chennai", "pune"]:
        if ct in s:
            return ct
    return city_hint.strip()

# PROCESS
model = EmissionModel(scope=scope)
rows = []
for idx, row in df.iterrows():
    from_txt = str(row["Type of Asset"]).strip()
    to_txt   = str(row["Location"]).strip()

    hint = auto_city_hint(from_txt, to_txt) or None

    start = parse_latlon(from_txt) or client.geocode_best(from_txt, boundary_country=country_bias, city_hint=hint)
    end   = parse_latlon(to_txt)   or client.geocode_best(to_txt,   boundary_country=country_bias, city_hint=hint)

    if not (start and end and is_valid_coord(start) and is_valid_coord(end)):
        rows.append({
            "From (Asset)": from_txt,
            "To (Location)": to_txt,
            "Type of vehicle": str(row.get("Type of vehicle", "")),
            "Type of fuel": str(row.get("Type of fuel", "")),
            "short_route_km": None,
            "long_route_km": None,
            "emissions_WTW_short_kg": None,
            "emissions_WTW_long_kg": None,
            "error": "Geocoding failed"
        })
        continue

    try:
        resp = client.directions(start, end, profile=profile)
        short_km, long_km = client.pick_short_long_distances(resp)
    except Exception as e:
        rows.append({
            "From (Asset)": from_txt,
            "To (Location)": to_txt,
            "Type of vehicle": str(row.get("Type of vehicle", "")),
            "Type of fuel": str(row.get("Type of fuel", "")),
            "short_route_km": None,
            "long_route_km": None,
            "emissions_WTW_short_kg": None,
            "emissions_WTW_long_kg": None,
            "error": f"Routing failed: {e}"
        })
        continue

    vtype = str(row["Type of vehicle"]).strip()
    fuel  = str(row["Type of fuel"]).strip()

    emis_short = model.emissions(short_km, vtype, fuel)
    emis_long  = model.emissions(long_km,  vtype, fuel)

    rows.append({
        "From (Asset)": from_txt,
        "To (Location)": to_txt,
        "Type of vehicle": vtype,
        "Type of fuel": fuel,
        "short_route_km": short_km,
        "long_route_km": long_km,
        "emissions_WTW_short_kg": emis_short,
        "emissions_WTW_long_kg": emis_long,
        "ors_profile": profile
    })

res = pd.DataFrame(rows)

# Ensure columns exist
for col in ["short_route_km", "long_route_km", "emissions_WTW_short_kg", "emissions_WTW_long_kg"]:
    if col not in res.columns:
        res[col] = None

# Helpers

def safe_sum(col_name: str) -> float:
    if col_name not in res.columns:
        return 0.0
    return float(pd.to_numeric(res[col_name], errors='coerce').fillna(0).sum())

def safe_count_nonnull(col_name: str) -> int:
    if col_name not in res.columns:
        return 0
    return int(res[col_name].notna().sum())

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="kpi">Total Trips<br><h3>'+str(safe_count_nonnull('short_route_km'))+'</h3></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="kpi">Total Short Distance (km)<br><h3>'+f"{safe_sum('short_route_km'):.2f}"+'</h3></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="kpi">Total Long Distance (km)<br><h3>'+f"{safe_sum('long_route_km'):.2f}"+'</h3></div>', unsafe_allow_html=True)
with col4:
    total_emis = safe_sum('emissions_WTW_short_kg') + safe_sum('emissions_WTW_long_kg')
    st.markdown('<div class="kpi">Total Emissions (kg CO2e)<br><h3>'+f"{total_emis:.2f}"+'</h3></div>', unsafe_allow_html=True)

st.divider()

# Panels
left, right = st.columns(2)
with left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Top by Distance (Short route)")
    if res['short_route_km'].notna().any():
        top_dist = res.dropna(subset=['short_route_km']).nlargest(10, 'short_route_km')
        st.table(top_dist[['From (Asset)','To (Location)','Type of vehicle','Type of fuel','short_route_km']])
    else:
        st.info("No distances available yet.")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("Top by Emissions (Short route)")
    e_col = 'emissions_WTW_short_kg'
    if res[e_col].notna().any():
        top_emis = res.dropna(subset=[e_col]).nlargest(10, e_col)
        st.table(top_emis[['From (Asset)','To (Location)','Type of vehicle','Type of fuel',e_col]])
    else:
        st.info("No emissions available yet.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
st.subheader("Results Table")
st.dataframe(res, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# Charts
if res['short_route_km'].notna().any():
    chart1 = alt.Chart(res.dropna(subset=['short_route_km'])).mark_bar().encode(
        x=alt.X('To (Location)', sort='-y', title='Destination'),
        y=alt.Y('short_route_km', title='Short route (km)'),
        color='Type of vehicle',
        tooltip=['From (Asset)','To (Location)','short_route_km','Type of vehicle','Type of fuel']
    )
    st.altair_chart(chart1, use_container_width=True)

if res['emissions_WTW_short_kg'].notna().any():
    chart2 = alt.Chart(res.dropna(subset=['emissions_WTW_short_kg'])).mark_bar().encode(
        x=alt.X('Type of vehicle'),
        y=alt.Y('emissions_WTW_short_kg', title='WTW emissions (kg CO2e)'),
        color='Type of fuel',
        tooltip=['From (Asset)','To (Location)','Type of vehicle','Type of fuel','emissions_WTW_short_kg']
    )
    st.altair_chart(chart2, use_container_width=True)

# Export
st.download_button("Download results (CSV)", data=res.to_csv(index=False), file_name="results.csv", mime="text/csv")

# Footnotes
st.caption("ORS Geocoding & Directions; distances in meters (converted to km). Coordinates order [lon,lat]. Alternative routes derived via GET preferences if POST fails.")
