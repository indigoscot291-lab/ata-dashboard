import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from typing import List, Optional

# --- Page config ---
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")

# --- Constants / Config ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

GROUPS = {
    "1st Degree Black Belt Women 50-59": {
        "code": "W01D",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
        # this is the export CSV link used previously
        "sheet_url": "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"
    },
    "2nd/3rd Degree Black Belt Women 40-49": {
        "code": "W23C",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv"
    }
}

# Full names -> (country, code)
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

# --- Helpers / Fetching ---
@st.cache_data(ttl=3600)
def fetch_html(url: str) -> Optional[str]:
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.text
    except Exception:
        return None
    return None

@st.cache_data(ttl=3600)
def fetch_sheet_csv(url: str) -> pd.DataFrame:
    try:
        return pd.read_csv(url)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_district_df() -> pd.DataFrame:
    return fetch_sheet_csv(DISTRICT_SHEET_URL)

def _normalize_region_token(token: str) -> Optional[str]:
    """Given a token from the district sheet (either full name or 2-letter code),
    return the canonical REGION name (matching REGION_CODES keys) or None."""
    t = token.strip()
    if not t:
        return None
    # If it's exactly a 2-letter code, map back to full name
    if re.fullmatch(r"[A-Za-z]{2}", t):
        abbr = t.upper()
        for name, (country, code) in REGION_CODES.items():
            if code.upper() == abbr:
                return name
    # Try direct match (case-insensitive) to a region name
    for name in REGION_CODES.keys():
        if name.lower() == t.lower():
            return name
    # Otherwise return the token as-is if it matches one of the region keys partially
    # (user's district sheet might use slight variants - prefer exact matches only)
    return None

def parse_standings(html: str):
    soup = BeautifulSoup(html, "html.parser")
    data = {ev: [] for ev in EVENT_NAMES}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        evt_span = header.find("span", class_="text-primary text-uppercase")
        if not evt_span:
            continue
        ev_name = evt_span.get_text(strip=True)
        if ev_name not in EVENT_NAMES:
            continue
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) != 4:
                continue
            rank_s, name, pts_s, loc = cols
            if not all([rank_s, name, pts_s, loc]):
                continue
            try:
                pts = int(pts_s)
            except Exception:
                continue
            if pts <= 0:
                continue
            try:
                rank_i = int(rank_s)
            except Exception:
                rank_i = None
            data[ev_name].append({
                "Rank": rank_i if rank_i is not None else 0,
                "Name": name.strip(),
                "Points": pts,
                "Location": loc.strip()
            })
    return data

def gather_data_for_regions(group_key: str, regions: Optional[List[str]] = None):
    """
    If regions is None -> fetch ALL regions (iterate REGION_CODES).
    If regions is a list -> fetch only those regions present in REGION_CODES (skip unknown).
    If regions contains "International" then world entries will be filtered to non-US/CA suffixes.
    Always include world standings at the start to allow international fill-ins.
    Returns (combined_dict, has_any_bool)
    """
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # always fetch world standings first (for international/internationals)
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # If regions is None -> treat as All (fetch every state)
    if regions is None:
        regions_to_fetch = list(REGION_CODES.keys())
    else:
        regions_to_fetch = list(regions)  # copy

    # If selected includes "All" string (legacy), treat as None
    if regions_to_fetch and len(regions_to_fetch) == 1 and regions_to_fetch[0] == "All":
        regions_to_fetch = list(REGION_CODES.keys())

    any_found = False
    # Fetch state pages for each region in the list that matches REGION_CODES
    for reg in regions_to_fetch:
        if reg == "International":
            # We'll handle international filtering after data are collected
            continue
        if reg not in REGION_CODES:
            # skip unknown region tokens
            continue
        country, code = REGION_CODES[reg]
        url = group["state_url_template"].format(country, code, group["code"])
        html = fetch_html(url)
        if not html:
            continue
        state_data = parse_standings(html)
        for ev, entries in state_data.items():
            combined[ev].extend(entries)
        if any(len(lst) > 0 for lst in state_data.values()):
            any_found = True

    # If regions included International as sole or included, filter combined entries to those without ", XX"
    if regions is not None and "International" in regions and (len(regions) == 1):
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                # location not ending with ", XX" (two uppercase letters) considered international
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        any_found = any(len(lst) > 0 for lst in intl.values())
        combined = intl

    return combined, any_found

def dedupe_and_rank(event_data: dict):
    """
    Dedupe entries and compute ranks:
    - If tie on points => same rank for tied competitors; next rank skips appropriately.
      Example: points [50,40,40,30] -> ranks [1,2,2,4]
    """
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        uniq = []
        for e in entries:
            key = (e["Name"].lower().strip(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        # Sort by points desc, name asc for stable order
        uniq.sort(key=lambda x: (-x["Points"], x["Name"]))
        prev_points = None
        prev_rank = None
        current_pos = 1
        for item in uniq:
            if prev_points is None or item["Points"] != prev_points:
                item["Rank"] = current_pos
                prev_rank = current_pos
            else:
                item["Rank"] = prev_rank
            prev_points = item["Points"]
            current_pos += 1
        clean[ev] = uniq
    return clean

# --- UI (unchanged layout behavior) ---
st.title("ATA Standings Dashboard")

# Mobile or not (user choice)
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

# Group selector
group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

# Load tournament breakdown sheet for selected group (may be empty)
sheet_df = fetch_sheet_csv(GROUPS[group_choice]["sheet_url"])

# District sheet loaded & parsed
district_df = fetch_district_df()
districts_list = [""] + sorted(district_df['District'].dropna().unique().tolist()) if not district_df.empty else [""]

# District selector (optional)
district_choice = st.selectbox("Select District (optional):", districts_list)

# Build region options based on district selection (one-per-line)
if district_choice:
    # Collect all comma-separated tokens for that district, flatten, normalize
    raw_entries = district_df.loc[district_df['District'] == district_choice, 'States and Provinces'].dropna().tolist()
    tokens = []
    for chunk in raw_entries:
        # split by comma (and optionally semicolon)
        parts = re.split(r'[,\;]\s*', str(chunk))
        for p in parts:
            normalized = _normalize_region_token(p)
            if normalized:
                tokens.append(normalized)
    # keep unique while preserving order
    seen = set()
    district_regions = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            district_regions.append(t)
    region_options = [""] + district_regions  # blank on top => means "all in this district"
else:
    region_options = REGIONS  # All + each state/province + International

region_choice = st.selectbox("Select region:", region_options)

# Name search (optional)
name_filter = st.text_input("Search competitor name (optional):").strip().lower()

# Go button
go = st.button("Go")

if go:
    # Build selected regions list for gather_data_for_regions
    if district_choice:
        # We created district_regions above (list of canonical region names)
        if region_choice and region_choice != "":
            selected_regions = [region_choice]
        else:
            selected_regions = district_regions[:]  # all states in this district
    else:
        if region_choice == "All":
            selected_regions = None  # None means fetch all
        elif region_choice == "International":
            selected_regions = ["International"]
        elif region_choice == "" or region_choice is None:
            selected_regions = None
        else:
            selected_regions = [region_choice]

    # Fetch data
    with st.spinner("Loading standings..."):
        raw_combined, has_any = gather_data_for_regions(group_choice, selected_regions)
        data = dedupe_and_rank(raw_combined)

    if not has_any:
        # user wants a district name in message if district was selected and region blank
        if district_choice:
            st.warning(f"No 50-59 results found for the selected district/regions.")
        else:
            st.warning("No standings data found for this selection.")
    else:
        # Display per-event tables in specified order
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            # apply name filter if provided (case-insensitive contains)
            if name_filter:
                rows = [r for r in rows if name_filter in r["Name"].lower()]

            if not rows:
                continue

            st.subheader(ev)

            if is_mobile:
                main_df = pd.DataFrame(rows)[["Rank", "Name", "Location", "Points"]]
                st.dataframe(main_df.reset_index(drop=True), use_container_width=True, hide_index=True)

                # Show breakdowns under table: one expander per competitor
                for row in rows:
                    # unique key for expanders to avoid duplicate-key errors
                    key = f"exp_mobile_{ev}_{row['Name']}_{row['Location']}"
                    with st.expander(row["Name"], key=key):
                        if not sheet_df.empty and ev in sheet_df.columns:
                            # match name case-insensitive, stripped
                            comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == row['Name'].lower().strip()
                            comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")
                        else:
                            st.write("No tournament data available.")
            else:
                # desktop header
                cols_header = st.columns([1,5,3,2])
                cols_header[0].write("Rank")
                cols_header[1].write("Name")
                cols_header[2].write("Location")
                cols_header[3].write("Points")

                for i, row in enumerate(rows):
                    cols = st.columns([1,5,3,2])
                    cols[0].write(row["Rank"])
                    # expander key must be unique
                    key = f"exp_{ev}_{i}_{row['Name']}_{row['Location']}"
                    with cols[1].expander(row["Name"], key=key):
                        if not sheet_df.empty and ev in sheet_df.columns:
                            comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == row['Name'].lower().strip()
                            comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")
                        else:
                            st.write("No tournament data available.")
                    cols[2].write(row["Location"])
                    cols[3].write(row["Points"])
