import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# Page config
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")

# --- CONFIG ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

GROUPS = {
    "1st Degree Black Belt Women 50-59": {
        "code": "W01D",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"
    },
    "2nd/3rd Degree Black Belt Women 40-49": {
        "code": "W23C",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv"
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

@st.cache_data(ttl=3600)
def fetch_sheet(sheet_url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(sheet_url)
        # ensure numeric event cols exist and are numeric
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

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
                except Exception:
                    continue
                if pts_val > 0:
                    data[ev_name].append({
                        "Rank": int(rank_s),
                        "Name": name.strip(),
                        "Points": pts_val,
                        "Location": loc.strip()
                    })
    return data

def gather_data(group_key: str, selected_region: str):
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Fetch world standings first (helps fill international)
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # If a specific state/province selected -> use only that state's page
    if selected_region not in ["All", "International", ""]:
        if selected_region not in REGION_CODES:
            return combined, False
        country, state_code = REGION_CODES[selected_region]
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev] = entries
            return combined, any(len(lst) > 0 for lst in state_data.values())
        else:
            return combined, False

    # If "All", iterate through regions and append
    if selected_region == "All":
        any_data = False
        for region_name, (country, state_code) in REGION_CODES.items():
            url = group["state_url_template"].format(country, state_code, group["code"])
            html = fetch_html(url)
            if not html:
                continue
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)
            if any(len(lst) > 0 for lst in state_data.values()):
                any_data = True
        return combined, any_data

    # If International: keep only entries whose Location doesn't end with ", XX"
    if selected_region == "International":
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        has_any = any(len(lst) > 0 for lst in intl.values())
        return intl, has_any

    # If blank (after district selection), include all in selected list
    if selected_region == "":
        return combined, any(len(lst) > 0 for lst in combined.values())

    return combined, False

def dedupe_and_rank(event_data: dict):
    """Dedupe and assign ranks. Ties get the same rank; next rank skips."""
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        uniq = []
        for e in entries:
            key = (e["Name"].lower(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        uniq.sort(key=lambda x: (-x["Points"], x["Name"]))
        prev_points = None
        prev_rank = None
        current_pos = 1
        for item in uniq:
            if prev_points is None or item["Points"] != prev_points:
                rank_to_assign = current_pos
                item["Rank"] = rank_to_assign
                prev_rank = rank_to_assign
            else:
                item["Rank"] = prev_rank
            prev_points = item["Points"]
            current_pos += 1
        clean[ev] = uniq
    return clean

# --- UI ---
st.title("ATA Standings Dashboard")

# Mobile radio
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

# Group selector
group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

# Load Google Sheet
sheet_df = fetch_sheet(GROUPS[group_choice]["sheet_url"])

# Load district sheet
district_df = pd.read_csv("https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv")
district_map = {}
for _, row in district_df.iterrows():
    district = row['District']
    state = row['States and Provinces']
    if pd.isna(district) or pd.isna(state):
        continue
    district_map.setdefault(district, []).append(state)

# District selector
district_choice = st.selectbox("Select district:", ["All"] + sorted(district_map.keys()))

# Region selector
if district_choice == "All":
    region_options = REGIONS
else:
    region_options = district_map[district_choice]

region_choice = st.selectbox("Select region:", [""] + region_options, index=0)

# Name search
name_filter = st.text_input("Search competitor name (optional):").strip().lower()

# Go button
go = st.button("Go")

if go:
    # Determine regions to process
    if district_choice != "All" and region_choice == "":
        selected_regions = district_map[district_choice]
    else:
        selected_regions = [region_choice]

    with st.spinner("Loading standings..."):
        combined = {ev: [] for ev in EVENT_NAMES}
        has_results = False
        for region in selected_regions:
            raw_data, region_has = gather_data(group_choice, region)
            for ev in EVENT_NAMES:
                combined[ev].extend(raw_data.get(ev, []))
            if region_has:
                has_results = True

        data = dedupe_and_rank(combined)

    if not has_results:
        st.warning("No standings data found for this selection.")
    else:
        for ev in EVENT_NAMES:
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
                                (sheet_df['Name'].str.lower().str.strip() == row['Name'].lower().strip()) &
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
