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

# Regions list: All + every state/province + International
REGIONS = ["All"] + list(REGION_CODES.keys()) + ["International"]

# --- HELPERS ---
@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None

@st.cache_data(ttl=3600)
def fetch_sheet(url):
    try:
        df = pd.read_csv(url)
        # ensure numeric event cols exist and are numeric
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors="coerce").fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

def parse_standings(html):
    """Parse the ATA standings HTML and return dict[event] = list of entries"""
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

def gather_data(group_key, selected_region):
    """
    Returns combined standings dict by event for the selected group and region.
    group_key is the string key from GROUPS.
    """
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Always try to fetch world standings first (useful for International fill-ins)
    world_html = fetch_html(group["world_url"])
    if world_html:
        wdata = parse_standings(world_html)
        for ev, entries in wdata.items():
            combined[ev].extend(entries)

    # If a specific state/province selected
    if selected_region not in ["All", "International"]:
        if selected_region not in REGION_CODES:
            return combined, False
        country, state_code = REGION_CODES[selected_region]
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            # For a single-state selection we want only that state's lists (not world merged)
            for ev, entries in state_data.items():
                combined[ev] = entries
            return combined, any(len(lst) > 0 for lst in state_data.values())
        else:
            return combined, False

    # If "All", iterate through all states/provinces and append
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

    # If International: filter combined (world + any appended) for entries whose location
    # does not end with a two-letter state/province code (i.e., international)
    if selected_region == "International":
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                # if location doesn't match ", XX" (two-letter code) treat as international
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        has_any = any(len(lst) > 0 for lst in intl.values())
        return intl, has_any

    return combined, False

def dedupe_and_rank(event_data):
    """Dedupe (by Name+Location+Points) and assign ranks with ties (ties get same rank; next rank skips)."""
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        uniq = []
        for e in entries:
            key = (e["Name"].lower(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        # sort desc by Points, then Name for deterministic
        uniq.sort(key=lambda x: (-x["Points"], x["Name"]))
        # assign ranks with ties (1,2,2,4)
        processed = 0
        prev_points = None
        prev_rank = None
        for item in uniq:
            if prev_points is None or item["Points"] != prev_points:
                rank = processed + 1
                item["Rank"] = rank
                prev_rank = rank
            else:
                item["Rank"] = prev_rank
            prev_points = item["Points"]
            processed += 1
        clean[ev] = uniq
    return clean


# --- STREAMLIT UI ---
st.title("ATA Standings Dashboard (states/provinces → All / International included)")

group_choice = st.selectbox("Select group:", list(GROUPS.keys()))
# put region selector with All + states/provinces + International
region_choice = st.selectbox("Select region:", REGIONS)

# name search (optional) — placed under region as requested
name_filter = st.text_input("Search competitor name (optional)").strip().lower()

# load sheet for the chosen group (if available)
sheet_df = fetch_sheet(GROUPS[group_choice]["sheet_url"])

go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw_data, has = gather_data(group_choice, region_choice)
        data = dedupe_and_rank(raw_data)

    if not has:
        st.warning(f"No standings found for {region_choice}.")
    else:
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            # apply search filter if provided
            if name_filter:
                rows = [r for r in rows if name_filter in r["Name"].lower()]
            if not rows:
                continue

            st.subheader(ev)
            # table header
            cols_header = st.columns([1,4,2,1])
            cols_header[0].write("Rank")
            cols_header[1].write("Name")
            cols_header[2].write("Location")
            cols_header[3].write("Points")

            # rows
            for row in rows:
                cols = st.columns([1,4,2,1])
                cols[0].write(row["Rank"])
                # Name expander (only name shown on header)
                with cols[1].expander(row["Name"]):
                    # select breakdown from sheet_df (case-insensitive match), include Type and only positive points for that event
                    if not sheet_df.empty and ev in sheet_df.columns:
                        comp_data = sheet_df[
                            (sheet_df['Name'].str.lower() == row['Name'].lower()) &
                            (sheet_df[ev] > 0)
                        ][["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                        if not comp_data.empty:
                            # convert to records and use st.table so no index column appears
                            st.table(comp_data.reset_index(drop=True).to_dict("records"))
                        else:
                            st.write("No tournament data for this event.")
                    else:
                        st.write("No tournament data available (sheet missing or event column absent).")
                cols[2].write(row["Location"])
                cols[3].write(row["Points"])
