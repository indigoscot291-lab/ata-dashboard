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
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
    },
    "2nd/3rd Degree Black Belt Women 40-49": {
        "code": "W23C",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
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
    except:
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

def gather_data_dashboard(group_key: str, region_choice: str, district_choice: str):
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Determine regions
    regions_to_fetch = []
    if district_choice:
        states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
        regions_to_fetch = [s.strip() for s in states_in_district.split(',')]
        if region_choice:
            regions_to_fetch = [region_choice]
    else:
        if region_choice not in ["All", "International"]:
            regions_to_fetch = [region_choice]
        elif region_choice == "All":
            regions_to_fetch = list(REGION_CODES.keys())
        elif region_choice == "International":
            regions_to_fetch = []

    # Fetch world data first
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # Fetch state/province data
    for region in regions_to_fetch:
        if region not in REGION_CODES:
            continue
        country, state_code = REGION_CODES[region]
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)

    # International only (from world)
    if region_choice=="International":
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        combined = intl

    has_any = any(len(lst) > 0 for lst in combined.values())
    return combined, has_any

def dedupe_and_rank(event_data: dict):
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

def gather_50_59_table():
    group_key = "1st Degree Black Belt Women 50-59"
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # World data (for international)
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # All US states + Canadian provinces
    for region, (country, state_code) in REGION_CODES.items():
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)

    # Combine into table
    all_competitors = {}
    for ev, entries in combined.items():
        for e in entries:
            key = (e["Name"], e["Location"])
            if key not in all_competitors:
                all_competitors[key] = {ev: "X"}
            else:
                all_competitors[key][ev] = "X"

    # Build DataFrame
    df_rows = []
    for (name, loc), events in all_competitors.items():
        row = {"Name": name, "Location": loc}
        for ev in EVENT_NAMES:
            row[ev] = events.get(ev, "")
        df_rows.append(row)

    df = pd.DataFrame(df_rows)
    # Sort alphabetically by state/province then last name
    df[['Town', 'State']] = df['Location'].str.split(',', 1, expand=True)
    df['LastName'] = df['Name'].str.split(' ').str[-1]
    df.sort_values(by=['State', 'LastName'], inplace=True)
    df.drop(columns=['Town','State','LastName'], inplace=True)
    return df

# --- MAIN APP ---
st.set_page_config(page_title="ATA Dashboard", layout="wide")

page_choice = st.selectbox("Select page:", ["ATA Standings Dashboard", "1st Degree Black Belt Women 50-59"])

# --- Mobile question ---
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

if page_choice == "ATA Standings Dashboard":
    st.title("ATA Standings Dashboard")
    group_choice = st.selectbox("Select group:", list(GROUPS.keys()))
    district_choice = st.selectbox("Select District (optional):", [""] + sorted(district_df['District'].unique()))
    region_options = []
    if district_choice:
        states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
        region_options = [s.strip() for s in states_in_district.split(',')]
        region_choice = st.selectbox("Select Region (optional):", [""] + region_options)
    else:
        region_choice = st.selectbox("Select Region:", REGIONS)
    event_filter = st.selectbox("Select Event (optional):", ["All"] + EVENT_NAMES)
    name_filter = st.text_input("Search competitor name (optional):").strip().lower()

    go = st.button("Go")
    if go:
        with st.spinner("Loading standings..."):
            raw_data, has_results = gather_data_dashboard(group_choice, region_choice, district_choice)
            data = dedupe_and_rank(raw_data)

        if not has_results:
            st.warning(f"No standings data found for {region_choice or district_choice}.")
        else:
            for ev in EVENT_NAMES:
                if event_filter != "All" and ev != event_filter:
                    continue
                rows = data.get(ev, [])
                if name_filter:
                    rows = [r for r in rows if name_filter in r["Name"].lower()]
                if not rows:
                    continue

                st.subheader(ev)

                if is_mobile:
                    main_df = pd.DataFrame(rows)[["Rank","Name","Location","Points"]]
                    st.dataframe(main_df.reset_index(drop=True), use_container_width=True, hide_index=True)
                else:
                    cols_header = st.columns([1,5,3,2])
                    cols_header[0].write("Rank")
                    cols_header[1].write("Name")
                    cols_header[2].write("Location")
                    cols_header[3].write("Points")
                    for row in rows:
                        cols = st.columns([1,5,3,2])
                        cols[0].write(row["Rank"])
                        cols[1].write(row["Name"])
                        cols[2].write(row["Location"])
                        cols[3].write(row["Points"])

else:  # 50-59 table page
    st.title("1st Degree Black Belt Women 50-59")
    st.write("This table shows all competitors with X for events they have points in.")
    df_50_59 = gather_50_59_table()
    st.dataframe(df_50_59, use_container_width=True, hide_index=True)
