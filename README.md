
# Fleet Emission Tracker — Asset=FROM, Location=TO (solved, single-folder)

This build addresses the 0‑distance / 400 errors by:
- **Robust geocoding**: multi‑step strategy (search → search+country → search+city hint → structured → autocomplete), with **auto city hint detection** (Bengaluru/Delhi/Mumbai/Kolkata/Chennai/Hyderabad/Pune) from text.
- **Strict coordinate validation** before routing to avoid ORS 400.
- **Vehicle/fuel normalization** (handles inputs like “35 Seater BUS”).
- **Safe KPIs/charts** when rows fail.

Upload your CSV at runtime. ORS key from Secrets only.
