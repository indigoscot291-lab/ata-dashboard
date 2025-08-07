import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# --- Constants ---
BASE_URL = "https://atamartialarts.com/events/tournament-standings/W01D/"
REGIONS = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "British-Columbia", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Manitoba", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New-Brunswick", "New-Hampshire",
    "New-Jersey", "New-Mexico", "New-York", "Newfoundland-and-Labrador", "North-Carolina",
    "North-Dakota", "Northwest-Territories", "Nova-Scotia", "Nunavut", "Ohio", "Oklahoma",
    "Ontario", "Oregon", "Pennsylvania", "Prince-Edward-Island", "Quebec", "Rhode-Island",
    "Saskatchewan", "South-Carolina", "South-Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West-Virginia", "Wisconsin", "Wyoming", "Yukon"
]
REGIONS.sort()
REGIONS.insert(0, "All")

# --- Helper Functions ---
@st.cache_data(show_spinner=False)
def fetch_standings(region):
    url = BASE_URL + region.replace(" ", "-")
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        st.warning(f"Could not load data for {region}: {e}")
        return {}

    all_results = {}
    headers = soup.find_all("ul", class_="tournament-header")

    for header in headers:
        event_type_tag = header.find("span", class_="text-primary")
        if not event_type_tag:
            continue
        event_type = event_type_tag.text.strip()
        table = header.find_next("table")
        if not table:
            continue

        rows = table.find_all("tr")[1:]  # skip header row
        data = []
        for row in rows:
            cols = [col.text.strip() for col in row.find_all("td")]
            if len(cols) == 4 and all(cols):  # Avoid blank rows
                place, name, points, location = cols
                data.append({
                    "Place": place,
                    "Name": name,
                    "Points": int(points),
                    "Location": location,
                    "Region": region
                })

        if data:
            if event_type not in all_results:
                all_results[event_type] = []
            all_results[event_type].extend(data)

    return all_results

# --- Streamlit App ---
st.title("ATA Tournament Standings by Region")

selected_region = st.selectbox("Select a state or province", REGIONS)

results_by_event = {}

if selected_region == "All":
    for region in REGIONS[1:]:  # Skip "All"
        region_data = fetch_standings(region)
        for event, competitors in region_data.items():
            if event not in results_by_event:
                results_by_event[event] = []
            results_by_event[event].extend(competitors)
else:
    results_by_event = fetch_standings(selected_region)

if not results_by_event:
    st.info("No standings available for the selected region.")
else:
    for event_name, competitors in sorted(results_by_event.items()):
        if not competitors:
            continue
        df = pd.DataFrame(competitors)
        df = df.sort_values(by="Points", ascending=False).reset_index(drop=True)
        st.subheader(f"{event_name} ({len(df)} competitors)")
        st.dataframe(df, use_container_width=True)
