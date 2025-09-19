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

DISTRICT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"
district_df = pd.read_csv(DISTRICT_SHEET_URL)

# Build abbreviation <-> name lookups
ABBR_TO_NAME = {vals[1].upper(): name for name, vals in REGION_CODES.items()}
NAME_TO_ABBR = {name.lower(): vals[1].upper() for name, vals in REGION_CODES.items()}

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
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors='coerce').fillna(0)
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

def normalize_region_token(token: str):
    """Return canonical region name given a token (abbr or full name); None if unknown."""
    if not token:
        return None
    t = str(token).strip()
    # exact full-name match (case-insensitive)
    for name in REGION_CODES.keys():
        if t.lower() == name.lower():
            return name
    # abbreviation match
    up = t.upper()
    if up in ABBR_TO_NAME:
        return ABBR_TO_NAME[up]
    # try Title-case fallback
    tc = t.title()
    if tc in REGION_CODES:
        return tc
    return None

def location_is_in_region(location: str, region_name: str):
    """Return True if a given Location string (from site) corresponds to the region_name."""
    if not location or not region_name:
        return False
    loc = location.strip()
    # check for trailing ", XX" two-letter code
    m = re.search(r',\s*([A-Za-z]{2})$', loc)
    if m:
        code = m.group(1).upper()
        region_abbr = REGION_CODES.get(region_name, (None, None))[1]
        if region_abbr and code == region_abbr.upper():
            return True
    # check if full region name appears
    if region_name.lower() in loc.lower():
        return True
    # check if abbreviation appears anywhere (e.g. "SUWANEE, GA")
    region_abbr = REGION_CODES.get(region_name, (None, None))[1]
    if region_abbr and region_abbr.upper() in loc.upper():
        return True
    return False

def gather_data(group_key: str, region_choice: str, district_choice: str):
    """
    Fetch only the pages needed depending on selections:
      - If region_choice == "International": return only international (world) entries.
      - If region_choice is a specific region: fetch that region only.
      - Else if district_choice provided: fetch all regions in district.
      - Else if region_choice == "All" or empty: fetch all regions; also include international world entries.
    """
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Special case: International only
    if region_choice == "International":
        world_html = fetch_html(group["world_url"])
        if world_html:
            world_data = parse_standings(world_html)
            # keep only entries without trailing 2-letter code (international)
            intl = {ev: [] for ev in EVENT_NAMES}
            for ev, entries in world_data.items():
                for e in entries:
                    if not re.search(r',\s*[A-Z]{2}$', e["Location"]):
                        intl[ev].append(e)
            return intl, any(len(lst) > 0 for lst in intl.values())
        return combined, False

    # Determine target regions (canonical names)
    target_regions = []

    # If a specific region selected (non-empty and not "All")
    if region_choice and region_choice not in ["All", ""]:
        norm = normalize_region_token(region_choice)
        if norm:
            target_regions = [norm]
        else:
            # fallback: if it's in REGION_CODES keys as-is
            if region_choice in REGION_CODES:
                target_regions = [region_choice]
            else:
                target_regions = []

    # Else if district selected and region blank -> use district's states
    elif district_choice:
        raw_list = district_df.loc[district_df['District'] == district_choice, 'States and Provinces'].iloc[0]
        tokens = [s.strip() for s in raw_list.split(',')]
        canonical = []
        for tok in tokens:
            norm = normalize_region_token(tok)
            if norm:
                canonical.append(norm)
        target_regions = canonical

    # Else region_choice == "All" or empty -> fetch everything
    else:
        target_regions = list(REGION_CODES.keys())

    # Fetch only target region pages
    for region in target_regions:
        if region not in REGION_CODES:
            continue
        country, state_code = REGION_CODES[region]
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if not html:
            continue
        state_data = parse_standings(html)
        for ev, entries in state_data.items():
            combined[ev].extend(entries)

    # If user asked for All (or left region blank and no district specified), include world-only internationals
    if (region_choice == "All" or (not region_choice and not district_choice)):
        world_html = fetch_html(group["world_url"])
        if world_html:
            world_data = parse_standings(world_html)
            for ev, entries in world_data.items():
                for e in entries:
                    # add only if location is international (no trailing ", XX")
                    if not re.search(r',\s*[A-Z]{2}$', e["Location"]):
                        combined[ev].append(e)

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
        # sort by points desc then name
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

def gather_50_59_table():
    group = GROUPS["1st Degree Black Belt Women 50-59"]
    combined = {ev: [] for ev in EVENT_NAMES}

    # All state pages
    for region, (country, state_code) in REGION_CODES.items():
        url = group["state_url_template"].format(country, state_code, group["code"])
        html = fetch_html(url)
        if not html:
            continue
        state_data = parse_standings(html)
        for ev, entries in state_data.items():
            combined[ev].extend(entries)

    # Add world internationals (entries without trailing 2-letter code)
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            for e in entries:
                if not re.search(r',\s*[A-Z]{2}$', e["Location"]):
                    combined[ev].append(e)

    # Combine into one line per competitor
    all_entries = {}
    for ev, entries in combined.items():
        for e in entries:
            key = (e["Name"], e["Location"])
            if key not in all_entries:
                all_entries[key] = {}
            all_entries[key][ev] = "X"

    rows = []
    for (name, loc), evs in all_entries.items():
        row = {"Name": name, "Location": loc}
        for ev in EVENT_NAMES:
            row[ev] = evs.get(ev, "")
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # safe split location into Town & State
    loc_split = df['Location'].str.split(',', n=1, expand=True)
    df['Town'] = loc_split[0].str.strip()
    df['State'] = loc_split[1].str.strip().fillna('')
    df['LastName'] = df['Name'].str.split().str[-1].str.strip()
    df.sort_values(by=['State', 'LastName'], inplace=True)
    df.drop(columns=['Town', 'LastName'], inplace=True)
    return df

# --- UI ---
st.title("ATA Standings Dashboard")

# Mobile question first
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

# Inputs
group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

district_choice = st.selectbox("Select District (optional):", [""] + sorted(district_df['District'].unique()))
region_options = []
if district_choice:
    raw_list = district_df.loc[district_df['District'] == district_choice, 'States and Provinces'].iloc[0]
    region_options = [s.strip() for s in raw_list.split(',')]
    region_choice = st.selectbox("Select Region (optional):", [""] + region_options)
else:
    region_choice = st.selectbox("Select Region:", REGIONS)

event_choice = st.selectbox("Select Event (optional):", [""] + EVENT_NAMES)
name_filter = st.text_input("Search competitor name (optional):").strip().lower()

# sheet for popups (may be empty)
sheet_df = fetch_sheet(GROUPS[group_choice]["sheet_url"])

# Go
go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw_data, has_results = gather_data(group_choice, region_choice, district_choice)
        data = dedupe_and_rank(raw_data)

    if not has_results:
        st.warning(f"No standings data found for {region_choice or district_choice}.")
    else:
        any_shown = False
        for ev in EVENT_NAMES:
            # event filter
            if event_choice and ev != event_choice:
                continue

            rows = data.get(ev, [])
            # name filter
            if name_filter:
                rows = [r for r in rows if name_filter in r["Name"].lower()]

            if not rows:
                continue

            any_shown = True
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

        if not any_shown:
            st.info("No competitors matched your filters (try clearing Event or Name).")

# 50-59 full table displayed below (same behavior as earlier)
st.markdown("---")
st.subheader("1st Degree Black Belt Women 50-59 (Full Table)")
st.write("One row per competitor; 'X' indicates points in that event. Worlds used for internationals.")
df_50_59 = gather_50_59_table()
if df_50_59.empty:
    st.write("No competitors found.")
else:
    st.dataframe(df_50_59.reset_index(drop=True), use_container_width=True, hide_index=True)
