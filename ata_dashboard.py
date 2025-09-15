import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- CONFIG ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

GROUPS = {
    "1st Degree Black Belt Women 50-59": {
        "code": "W01D",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}"
    },
    "2nd/3rd Degree Black Belt Women 40-49": {
        "code": "W23C",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}"
    }
}

REGION_CODES = {
    # US states
    "Alabama": ("US", "AL"), "Alaska": ("US", "AK"), "Arizona": ("US", "AZ"),
    "Arkansas": ("US", "AR"), "California": ("US", "CA"), "Colorado": ("US", "CO"),
    "Connecticut": ("US", "CT"), "Delaware": ("US", "DE"), "Florida": ("US", "FL"),
    "Georgia": ("US", "GA"), "Hawaii": ("US", "HI"), "Idaho": ("US", "ID"),
    "Illinois": ("US", "IL"), "Indiana": ("US", "IN"), "Iowa": ("US", "IA"),
    "Kansas": ("US", "KS"), "Kentucky": ("US", "KY"), "Louisiana": ("US", "LA"),
    "Maine": ("US", "ME"), "Maryland": ("US", "MD"), "Massachusetts": ("US", "MA"),
    "Michigan": ("US", "MI"), "Minnesota": ("US", "MN"), "Mississippi": ("US", "MS"),
    "Missouri": ("US", "MO"), "Montana": ("US", "MT"), "Nebraska": ("US", "NE"),
    "Nevada": ("US", "NV"), "New Hampshire": ("US", "NH"), "New Jersey": ("US", "NJ"),
    "New Mexico": ("US", "NM"), "New York": ("US", "NY"), "North Carolina": ("US", "NC"),
    "North Dakota": ("US", "ND"), "Ohio": ("US", "OH"), "Oklahoma": ("US", "OK"),
    "Oregon": ("US", "OR"), "Pennsylvania": ("US", "PA"), "Rhode Island": ("US", "RI"),
    "South Carolina": ("US", "SC"), "South Dakota": ("US", "SD"), "Tennessee": ("US", "TN"),
    "Texas": ("US", "TX"), "Utah": ("US", "UT"), "Vermont": ("US", "VT"),
    "Virginia": ("US", "VA"), "Washington": ("US", "WA"), "West Virginia": ("US", "WV"),
    "Wisconsin": ("US", "WI"), "Wyoming": ("US", "WY"),
    # Canadian provinces
    "Alberta": ("CA", "AB"), "British Columbia": ("CA", "BC"), "Manitoba": ("CA", "MB"),
    "New Brunswick": ("CA", "NB"), "Newfoundland and Labrador": ("CA", "NL"),
    "Nova Scotia": ("CA", "NS"), "Ontario": ("CA", "ON"), "Prince Edward Island": ("CA", "PE"),
    "Quebec": ("CA", "QC"), "Saskatchewan": ("CA", "SK")
}

REGIONS = ["All"] + list(REGION_CODES.keys()) + ["International"]

DISTRICT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"
district_df = pd.read_csv(DISTRICT_SHEET_URL)

# --- HELPERS ---
@st.cache_data(ttl=3600)
def fetch_html(url: str):
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None

def parse_standings(html: str):
    soup = BeautifulSoup(html, "html.parser")
    data = {ev: [] for ev in EVENT_NAMES}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        evt = header.find("span", class_="text-primary text-uppercase")
        if not evt:
            continue
        ev_name = evt.get_text(strip=True)
        if ev_name not in EVENT_NAMES:
            continue
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) == 4 and all(cols):
                rank_s, name, pts_s, loc = cols
                try:
                    pts_val = int(pts_s)
                except:
                    continue
                if pts_val > 0:
                    data[ev_name].append({
                        "Rank": int(rank_s),
                        "Name": name.strip(),
                        "Points": pts_val,
                        "Location": loc.strip()
                    })
    return data

def gather_data_for_group(group_key: str):
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Worlds (International)
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # All states/provinces
    for region_name, (country, state_code) in REGION_CODES.items():
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)

    return combined

# --- UI ---
st.title("ATA Dashboard Options")

page = st.sidebar.selectbox("Select Page:", ["ATA Standings Dashboard", "1st Degree Black Belt Women 50-59"])

if page == "ATA Standings Dashboard":
    # --- Main dashboard page ---
    from datetime import datetime

    # Group selector
    group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

    # District & region selectors
    district_choice = st.selectbox("Select District (optional):", [""] + sorted(district_df['District'].unique()))
    if district_choice:
        states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
        region_options = [s.strip() for s in states_in_district.split(',')]
        region_choice = st.selectbox("Select Region (optional):", [""] + region_options)
    else:
        region_choice = st.selectbox("Select Region:", REGIONS)

    # Optional name search
    name_filter = st.text_input("Search competitor name (optional):").strip().lower()

    # Optional event search
    event_filter = st.selectbox("Filter by event (optional):", ["All"] + EVENT_NAMES)

    go = st.button("Go")

    if go:
        with st.spinner("Loading standings..."):
            raw_data, has_results = gather_data_for_group(group_choice), True
            # Filter by district/region
            if district_choice:
                states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
                states_set = set(s.strip() for s in states_in_district.split(','))
                for ev in raw_data:
                    raw_data[ev] = [c for c in raw_data[ev] if c["Location"].split(",")[0].strip() in states_set]
            elif region_choice and region_choice != "All" and region_choice != "International":
                raw_data = {ev:[c for c in raw_data[ev] if c["Location"].split(",")[0].strip() == region_choice] for ev in EVENT_NAMES}
            elif region_choice == "International":
                raw_data = {ev:[c for c in raw_data[ev] if not re.search(r",\s*[A-Z]{2}$", c["Location"])] for ev in EVENT_NAMES}

            # Filter by event
            if event_filter != "All":
                filtered_data = {event_filter: raw_data[event_filter]}
            else:
                filtered_data = raw_data

            # Sort & display
            for ev, rows in filtered_data.items():
                if name_filter:
                    rows = [r for r in rows if name_filter in r["Name"].lower()]
                if not rows:
                    continue
                st.subheader(ev)
                df_display = pd.DataFrame(rows)[["Rank","Name","Location","Points"]]
                st.dataframe(df_display.reset_index(drop=True), use_container_width=True, hide_index=True)

elif page == "1st Degree Black Belt Women 50-59":
    # --- New page: full table of 1st Degree Women 50-59 ---
    with st.spinner("Loading competitors..."):
        raw_data = gather_data_for_group("1st Degree Black Belt Women 50-59")

        # Combine into one row per competitor
        combined_rows = {}
        for ev, competitors in raw_data.items():
            for c in competitors:
                key = (c["Name"], c["Location"])
                if key not in combined_rows:
                    combined_rows[key] = {"Name": c["Name"], "Location": c["Location"]}
                    for e in EVENT_NAMES:
                        combined_rows[key][e] = ""
                combined_rows[key][ev] = "X"

        df_final = pd.DataFrame(list(combined_rows.values()))

        # Sort alphabetically by state/province then last name
        df_final["State"] = df_final["Location"].apply(lambda x: x.split(",")[0].strip())
        df_final["LastName"] = df_final["Name"].apply(lambda x: x.split()[-1].strip())
        df_final = df_final.sort_values(by=["State","LastName"]).drop(columns=["State","LastName"])

        st.dataframe(df_final.reset_index(drop=True), use_container_width=True)
