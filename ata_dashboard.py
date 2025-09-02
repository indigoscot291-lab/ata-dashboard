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

STATE_URL_TEMPLATE = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D"
WORLD_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

# Google Sheet CSV export
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
                        "Name": name,
                        "Points": pts_val,
                        "Location": loc
                    })
    return data

def gather_data(selected):
    combined = {ev: [] for ev in EVENT_NAMES}

    # Always include world standings for international
    world_html = fetch_html(WORLD_URL)
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    if selected not in ["All", "International"]:
        country, code = REGION_CODES[selected]
        url = STATE_URL_TEMPLATE.format(country, code)
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev] = entries  # only this state
            return combined, any(len(lst) > 0 for lst in state_data.values())
        else:
            return combined, False

    elif selected == "All":
        any_data = False
        for region in REGION_CODES:
            country, code = REGION_CODES[region]
            url = STATE_URL_TEMPLATE.format(country, code)
            html = fetch_html(url)
            if html:
                data = parse_standings(html)
                for ev, entries in data.items():
                    combined[ev].extend(entries)
                if any(len(lst) > 0 for lst in data.values()):
                    any_data = True
        return combined, any_data

    elif selected == "International":
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
            key = (e["Name"], e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        unique.sort(key=lambda x: x["Points"], reverse=True)
        for idx, row in enumerate(unique, start=1):
            row["Rank"] = idx
        clean[ev] = unique
    return clean

# --- STREAMLIT APP ---
st.title("ATA W01D Standings")

sheet_df = fetch_sheet()

selection = st.selectbox("Select region:", REGIONS)
go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw, has_results = gather_data(selection)
        data = dedupe_and_rank(raw)

    if not has_results:
        if selection in REGION_CODES:
            st.warning(f"There are no 50‑59 1st Degree Women for {selection}.")
        elif selection == "International":
            st.warning("There are no 50‑59 1st Degree Women for International.")
        else:
            st.warning("No standings data found for this selection.")
    else:
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            if rows:
                df = pd.DataFrame(rows)[["Rank", "Name", "Points", "Location"]]

                # Prepare clickable names with popup
                display_rows = []
                for _, row in df.iterrows():
                    # Filter Google Sheet for this competitor and this event
                    comp_data = sheet_df[
                        (sheet_df['Name'].str.lower() == row['Name'].lower()) &
                        (sheet_df[ev] > 0)
                    ][["Date","Tournament",ev]].rename(columns={ev:"Points"})

                    if not comp_data.empty:
                        popup_text = "\\n".join(f"{r['Date']} - {r['Tournament']} - {r['Points']} pts" for _, r in comp_data.iterrows())
                    else:
                        popup_text = "No tournament data for this event."

                    name_html = f'<a href="#" onclick="window.alert(\'{popup_text}\');">{row["Name"]}</a>'

                    display_rows.append({
                        "Rank": row["Rank"],
                        "Name": name_html,
                        "Points": row["Points"],
                        "Location": row["Location"]
                    })

                display_df = pd.DataFrame(display_rows)

                st.subheader(ev)
                st.markdown(
                    display_df.to_html(escape=False, index=False),
                    unsafe_allow_html=True
                )
else:
    st.info("Select a region or 'International' and click Go to view standings.")
