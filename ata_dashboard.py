import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- CONFIG ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

GROUPS = {
    "World Standings": {
        "url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"
    },
    "State Standings": {
        "url": "https://atamartialarts.com/events/tournament-standings/state-standings/",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"
    }
}

# Google sheet with District → Regions mapping
DISTRICT_SHEET = "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"

# --- HELPERS ---
@st.cache_data(ttl=3600)
def fetch_sheet(sheet_url):
    try:
        df = pd.read_csv(sheet_url)
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""

def parse_standings(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    results = {ev: [] for ev in EVENT_NAMES}

    for idx, ev in enumerate(EVENT_NAMES):
        if idx < len(tables):
            df = pd.read_html(str(tables[idx]))[0]
            if "Rank" in df.columns and "Name" in df.columns:
                for _, row in df.iterrows():
                    results[ev].append({
                        "Rank": row.get("Rank", ""),
                        "Name": row.get("Name", ""),
                        "Location": row.get("Location", ""),
                        "Points": row.get("Points", "")
                    })
    return results

def gather_data(group_choice, region_choice, district_choice):
    base_url = GROUPS[group_choice]["url"]
    data = {ev: [] for ev in EVENT_NAMES}
    has_results = False

    if district_choice:
        states_in_district = district_df.loc[
            district_df["District"] == district_choice, "States and Provinces"
        ].iloc[0]
        states_list = [s.strip() for s in states_in_district.split(",")]

        if region_choice == "":
            # blank region → fetch all states in district
            for s in states_list:
                url = f"{base_url}?country=US&state={s.lower()[:2]}&region={s}"
                html = fetch_html(url)
                results = parse_standings(html)
                for ev in EVENT_NAMES:
                    data[ev].extend(results[ev])
                    if results[ev]:
                        has_results = True
        else:
            # specific region selected
            url = f"{base_url}?country=US&state={region_choice.lower()[:2]}&region={region_choice}"
            html = fetch_html(url)
            results = parse_standings(html)
            for ev in EVENT_NAMES:
                data[ev].extend(results[ev])
                if results[ev]:
                    has_results = True
    else:
        if region_choice == "All":
            # gather all regions
            for reg in REGIONS[1:]:
                url = f"{base_url}?country=US&state={reg.lower()[:2]}&region={reg}"
                html = fetch_html(url)
                results = parse_standings(html)
                for ev in EVENT_NAMES:
                    data[ev].extend(results[ev])
                    if results[ev]:
                        has_results = True
        else:
            url = f"{base_url}?country=US&state={region_choice.lower()[:2]}&region={region_choice}"
            html = fetch_html(url)
            results = parse_standings(html)
            for ev in EVENT_NAMES:
                data[ev].extend(results[ev])
                if results[ev]:
                    has_results = True

    return data, has_results

def dedupe_and_rank(data):
    deduped = {}
    for ev, rows in data.items():
        seen = set()
        deduped_rows = []
        for row in rows:
            key = (row["Name"], row["Location"], row["Points"])
            if key not in seen:
                seen.add(key)
                deduped_rows.append(row)
        deduped[ev] = deduped_rows
    return deduped

# --- LOAD DATA ---
district_df = fetch_sheet(DISTRICT_SHEET)

# Extract regions
if "States and Provinces" in district_df.columns:
    all_regions = []
    for v in district_df["States and Provinces"].dropna().unique():
        all_regions.extend([s.strip() for s in v.split(",")])
    REGIONS = ["All"] + sorted(set(all_regions))
else:
    REGIONS = ["All"]

# --- UI ---
st.title("ATA Standings Dashboard")

is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

district_choice = st.selectbox("Select District (optional):", [""] + sorted(district_df['District'].dropna().unique()))
region_options = []

if district_choice:
    states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
    region_options = [s.strip() for s in states_in_district.split(',')]
    region_choice = st.selectbox("Select Region (optional):", [""] + region_options)
else:
    region_choice = st.selectbox("Select Region:", REGIONS)

name_filter = st.text_input("Search competitor name (optional):").strip().lower()

# --- NEW Event filter ---
EVENT_FILTERS = [
    "",
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]
event_filter = st.selectbox("Search by event (optional):", EVENT_FILTERS)

sheet_df = fetch_sheet(GROUPS[group_choice]["sheet_url"])

go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw_data, has_results = gather_data(group_choice, region_choice, district_choice)
        data = dedupe_and_rank(raw_data)

    if not has_results:
        st.warning(f"No standings data found for {region_choice or district_choice}.")
    else:
        for ev in EVENT_NAMES:
            if event_filter and ev != event_filter:
                continue

            rows = data.get(ev, [])
            if name_filter:
                rows = [r for r in rows if name_filter in r["Name"].lower()]
            if not rows:
                continue

            st.subheader(ev)

            if is_mobile:
                main_df = pd.DataFrame(rows)[["Rank", "Name", "Location", "Points"]]
                st.dataframe(main_df.reset_index(drop=True), use_container_width=True, hide_index=True)

                for row in rows:
                    with st.expander(row["Name"]):
                        if not sheet_df.empty and ev in sheet_df.columns:
                            comp_data = sheet_df[
                                (sheet_df['Name'].str.lower().str.strip() == row['Name'].lower().strip()) &
                                (sheet_df[ev] > 0)
                            ][["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")
                        else:
                            st.write("No tournament data available.")
            else:
                cols_header = st.columns([1,5,3,2])
                cols_header[0].write("Rank")
                cols_header[1].write("Name")
                cols_header[2].write("Location")
                cols_header[3].write("Points")

                for row in rows:
                    cols = st.columns([1,5,3,2])
                    cols[0].write(row["Rank"])
                    with cols[1].expander(row["Name"]):
                        if not sheet_df.empty and ev in sheet_df.columns:
                            comp_data = sheet_df[
                                (sheet_df['Name'].str.lower().str.strip() == row['Name"].lower().strip()) &
                                (sheet_df[ev] > 0)
                            ][["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")
                        else:
                            st.write("No tournament data available.")
                    cols[2].write(row["Location"])
                    cols[3].write(row["Points"])
