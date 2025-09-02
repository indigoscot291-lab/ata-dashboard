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
    "1st Degree Black Belt Women 50-59": "W01D",
    "2/3 Degree Black Belt Women 40-49": "W23C"
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

STATE_URL_TEMPLATE = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}"
WORLD_URL_TEMPLATE = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code={}"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"

# --- FUNCTIONS ---
@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_sheet():
    try:
        df = pd.read_csv(SHEET_URL)
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def parse_standings(html):
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
                rank, name, pts, loc = cols
                try:
                    pts_val = int(pts)
                except:
                    continue
                if pts_val > 0:
                    data[ev_name].append({
                        "Rank": int(rank),
                        "Name": name.strip(),
                        "Points": pts_val,
                        "Location": loc
                    })
    return data

def gather_data(selected_region, group_code):
    combined = {ev: [] for ev in EVENT_NAMES}
    world_html = fetch_html(WORLD_URL_TEMPLATE.format(group_code))
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    if selected_region not in ["All", "International"]:
        country, code = REGION_CODES[selected_region]
        url = STATE_URL_TEMPLATE.format(country, code, group_code)
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev] = entries
            return combined, any(len(lst) > 0 for lst in state_data.values())
        else:
            return combined, False

    elif selected_region == "All":
        any_data = False
        for region in REGION_CODES:
            country, code = REGION_CODES[region]
            url = STATE_URL_TEMPLATE.format(country, code, group_code)
            html = fetch_html(url)
            if html:
                data = parse_standings(html)
                for ev, entries in data.items():
                    combined[ev].extend(entries)
                if any(len(lst) > 0 for lst in data.values()):
                    any_data = True
        return combined, any_data

    elif selected_region == "International":
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        combined = intl
        has_any = any(len(lst) > 0 for lst in combined.values())
        return combined, has_any

    return combined, False

def dedupe_and_rank(event_data):
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        unique = []
        for e in entries:
            key = (e["Name"].lower(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        unique.sort(key=lambda x: x["Points"], reverse=True)
        for idx, row in enumerate(unique, start=1):
            row["Rank"] = idx
        clean[ev] = unique
    return clean

# --- STREAMLIT APP ---
st.title("ATA Standings")

# Step 1: Mobile check
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

# Step 2: Group selection
selected_group = st.selectbox("Select Group:", list(GROUPS.keys()))
group_code = GROUPS[selected_group]

# Step 3: Region selection
selection = st.selectbox("Select region:", REGIONS)

sheet_df = fetch_sheet()
show_sheet = selected_group == "1st Degree Black Belt Women 50-59"

go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw, has_results = gather_data(selection, group_code)
        data = dedupe_and_rank(raw)

    if not has_results:
        st.warning("No standings data found for this selection/group.")
    else:
        if is_mobile:
            # Mobile: main tables first, points underneath
            for ev in EVENT_NAMES:
                rows = data.get(ev, [])
                if rows:
                    st.subheader(ev)
                    df_main = pd.DataFrame(rows)[["Rank","Name","Location","Points"]]
                    st.dataframe(df_main, use_container_width=True)

            if show_sheet and not sheet_df.empty:
                for ev in EVENT_NAMES:
                    st.subheader(f"{ev} - Competitor Points Details")
                    for row in data.get(ev, []):
                        comp_data = sheet_df[
                            (sheet_df['Name'].str.lower() == row['Name'].lower()) &
                            (sheet_df[ev] > 0)
                        ][["Date","Tournament",ev]].rename(columns={ev:"Points"})
                        if not comp_data.empty:
                            st.dataframe(comp_data, use_container_width=True)
        else:
            # Desktop: table with dropdowns
            for ev in EVENT_NAMES:
                rows = data.get(ev, [])
                if rows:
                    st.subheader(ev)
                    cols_header = st.columns([1,4,2,1])
                    cols_header[0].write("Rank")
                    cols_header[1].write("Name")
                    cols_header[2].write("Location")
                    cols_header[3].write("Points")
                    for row in rows:
                        cols = st.columns([1,4,2,1])
                        cols[0].write(row["Rank"])
                        with cols[1].expander(row["Name"]):
                            if show_sheet and not sheet_df.empty:
                                comp_data = sheet_df[
                                    (sheet_df['Name'].str.lower() == row['Name'].lower()) &
                                    (sheet_df[ev] > 0)
                                ][["Date","Tournament",ev]].rename(columns={ev:"Points"})
                                if not comp_data.empty:
                                    st.dataframe(comp_data, use_container_width=True)
                                else:
                                    st.write("No tournament data for this event.")
                            else:
                                st.write("Google Sheet data not available for this group yet.")
                        cols[2].write(row["Location"])
                        cols[3].write(row["Points"])
