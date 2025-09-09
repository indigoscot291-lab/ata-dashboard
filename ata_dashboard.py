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
    t = str(token).strip()
    if not t:
        return None
    if re.fullmatch(r"[A-Za-z]{2}", t):
        abbr = t.upper()
        for name, (country, code) in REGION_CODES.items():
            if code.upper() == abbr:
                return name
    for name in REGION_CODES.keys():
        if name.lower() == t.lower():
            return name
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
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    if regions is None:
        regions_to_fetch = list(REGION_CODES.keys())
    else:
        regions_to_fetch = list(regions)

    if regions_to_fetch and len(regions_to_fetch) == 1 and regions_to_fetch[0] == "All":
        regions_to_fetch = list(REGION_CODES.keys())

    any_found = False
    for reg in regions_to_fetch:
        if reg == "International":
            continue
        if reg not in REGION_CODES:
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

    if regions is not None and "International" in regions and (len(regions) == 1):
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    intl[ev].append(e)
        any_found = any(len(lst) > 0 for lst in intl.values())
        combined = intl

    return combined, any_found

def dedupe_and_rank(event_data: dict):
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        uniq = []
        for e in entries:
            key = (e["Name"].lower().strip(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
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

# ---- utility: sanitize key/label ----
def safe_str_for_key(s: str, maxlen: int = 80) -> str:
    s2 = str(s)
    # replace runs of non-alnum with underscore
    s2 = re.sub(r'[^0-9A-Za-z]+', '_', s2).strip('_')
    if len(s2) > maxlen:
        s2 = s2[:maxlen]
    return s2 or "empty"

# --- UI ---
st.title("ATA Standings Dashboard")

is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

group_choice = st.selectbox("Select group:", list(GROUPS.keys()))

sheet_df = fetch_sheet_csv(GROUPS[group_choice]["sheet_url"])

district_df = fetch_district_df()
districts_list = [""] + sorted(district_df['District'].dropna().unique().tolist()) if not district_df.empty else [""]

district_choice = st.selectbox("Select District (optional):", districts_list)

if district_choice:
    raw_entries = district_df.loc[district_df['District'] == district_choice, 'States and Provinces'].dropna().tolist()
    tokens = []
    for chunk in raw_entries:
        parts = re.split(r'[,\;]\s*', str(chunk))
        for p in parts:
            normalized = _normalize_region_token(p)
            if normalized:
                tokens.append(normalized)
    seen = set()
    district_regions = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            district_regions.append(t)
    region_options = [""] + district_regions
else:
    region_options = REGIONS

region_choice = st.selectbox("Select region:", region_options)

name_filter = st.text_input("Search competitor name (optional):").strip().lower()

go = st.button("Go")

if go:
    # build selected regions list
    if district_choice:
        if region_choice and region_choice != "":
            selected_regions = [region_choice]
        else:
            selected_regions = district_regions[:]  # all in district
    else:
        if region_choice == "All":
            selected_regions = None
        elif region_choice == "International":
            selected_regions = ["International"]
        elif region_choice == "" or region_choice is None:
            selected_regions = None
        else:
            selected_regions = [region_choice]

    with st.spinner("Loading standings..."):
        raw_combined, has_any = gather_data_for_regions(group_choice, selected_regions)
        data = dedupe_and_rank(raw_combined)

    if not has_any:
        if district_choice:
            st.warning(f"No 50-59 results found for the selected district/regions.")
        else:
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

                for i, row in enumerate(rows):
                    # sanitize label and key
                    label = str(row.get("Name", "")).strip()
                    key = f"exp_mobile_{safe_str_for_key(ev)}_{i}_{safe_str_for_key(label)}_{safe_str_for_key(row.get('Location',''))}"
                    try:
                        with st.expander(label, key=key):
                            if not sheet_df.empty and ev in sheet_df.columns:
                                comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == label.lower().strip()
                                comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                                if not comp_data.empty:
                                    st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                                else:
                                    st.write("No tournament data for this event.")
                            else:
                                st.write("No tournament data available.")
                    except Exception as e:
                        st.error(f"Error opening expander for {label}: {e}")
                        # fallback: show the content without an expander
                        if not sheet_df.empty and ev in sheet_df.columns:
                            comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == label.lower().strip()
                            comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")

            else:
                cols_header = st.columns([1,5,3,2])
                cols_header[0].write("Rank")
                cols_header[1].write("Name")
                cols_header[2].write("Location")
                cols_header[3].write("Points")

                for i, row in enumerate(rows):
                    cols = st.columns([1,5,3,2])
                    cols[0].write(row["Rank"])
                    label = str(row.get("Name", "")).strip()
                    key = f"exp_{safe_str_for_key(ev)}_{i}_{safe_str_for_key(label)}_{safe_str_for_key(row.get('Location',''))}"
                    try:
                        with cols[1].expander(label, key=key):
                            if not sheet_df.empty and ev in sheet_df.columns:
                                comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == label.lower().strip()
                                comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                                if not comp_data.empty:
                                    st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                                else:
                                    st.write("No tournament data for this event.")
                            else:
                                st.write("No tournament data available.")
                    except Exception as e:
                        st.error(f"Error opening expander for {label}: {e}")
                        if not sheet_df.empty and ev in sheet_df.columns:
                            comp_mask = sheet_df['Name'].astype(str).str.lower().str.strip() == label.lower().strip()
                            comp_data = sheet_df.loc[comp_mask & (sheet_df[ev] > 0), ["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.reset_index(drop=True), use_container_width=True, hide_index=True)
                            else:
                                st.write("No tournament data for this event.")
                    cols[2].write(row["Location"])
                    cols[3].write(row["Points"])
