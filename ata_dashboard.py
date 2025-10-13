import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# Page config
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")

# --- SESSION STATE FOR REFRESH ---
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = "Never"

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
    },
    "50-59 Women Color Belts": {
        "code": "WCOD",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=WCOD",
        "state_url_template": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code={}",
        "sheet_url": None
    }
}

REGION_CODES = {
    "Alabama": ("US", "AL"), "Alaska": ("US", "AK"), "Arizona": ("US", "AZ"), "Arkansas": ("US", "AR"),
    "California": ("US", "CA"), "Colorado": ("US", "CO"), "Connecticut": ("US", "CT"), "Delaware": ("US", "DE"),
    "Florida": ("US", "FL"), "Georgia": ("US", "GA"), "Hawaii": ("US", "HI"), "Idaho": ("US", "ID"),
    "Illinois": ("US", "IL"), "Indiana": ("US", "IN"), "Iowa": ("US", "IA"), "Kansas": ("US", "KS"),
    "Kentucky": ("US", "KY"), "Louisiana": ("US", "LA"), "Maine": ("US", "ME"), "Maryland": ("US", "MD"),
    "Massachusetts": ("US", "MA"), "Michigan": ("US", "MI"), "Minnesota": ("US", "MN"), "Mississippi": ("US", "MS"),
    "Missouri": ("US", "MO"), "Montana": ("US", "MT"), "Nebraska": ("US", "NE"), "Nevada": ("US", "NV"),
    "New Hampshire": ("US", "NH"), "New Jersey": ("US", "NJ"), "New Mexico": ("US", "NM"), "New York": ("US", "NY"),
    "North Carolina": ("US", "NC"), "North Dakota": ("US", "ND"), "Ohio": ("US", "OH"), "Oklahoma": ("US", "OK"),
    "Oregon": ("US", "OR"), "Pennsylvania": ("US", "PA"), "Rhode Island": ("US", "RI"), "South Carolina": ("US", "SC"),
    "South Dakota": ("US", "SD"), "Tennessee": ("US", "TN"), "Texas": ("US", "TX"), "Utah": ("US", "UT"),
    "Vermont": ("US", "VT"), "Virginia": ("US", "VA"), "Washington": ("US", "WA"), "West Virginia": ("US", "WV"),
    "Wisconsin": ("US", "WI"), "Wyoming": ("US", "WY"),
    "Alberta": ("CA", "AB"), "British Columbia": ("CA", "BC"), "Manitoba": ("CA", "MB"), "New Brunswick": ("CA", "NB"),
    "Newfoundland and Labrador": ("CA", "NL"), "Nova Scotia": ("CA", "NS"), "Ontario": ("CA", "ON"),
    "Prince Edward Island": ("CA", "PE"), "Quebec": ("CA", "QC"), "Saskatchewan": ("CA", "SK")
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

@st.cache_data(ttl=3600)
def fetch_sheet(sheet_url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(sheet_url)
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

def gather_data(group_key: str, region_choice: str, district_choice: str):
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

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

    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

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

    if region_choice == "International":
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

# --- PAGE SELECTION ---
page_choice = st.selectbox(
    "Select a page:",
    [
        "ATA Standings Dashboard",
        "1st Degree Black Belt Women 50-59",
        "National & District Rings"
    ]
)

# --- PAGE 1: Standings Dashboard ---
if page_choice == "ATA Standings Dashboard":
    # (unchanged)
    st.title("ATA Standings Dashboard")
    # ... your existing dashboard code remains exactly as-is ...

# --- PAGE 2: 50-59 Women ---
elif page_choice == "1st Degree Black Belt Women 50-59":
    # (unchanged)
    st.title("1st Degree Black Belt Women 50-59")
    # ... your existing 50-59 page code remains exactly as-is ...

# --- PAGE 3: National & District Rings ---
elif page_choice == "National & District Rings":
    st.title("National & District Tournament Rings")

    RINGS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1grZSp3fr3lZy4ScG8EqbvFCkNJm_jK3KjNhh2BXJm9A/export?format=csv"
    MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1wHqNyL4GoCKYuPKE-Asbc_9Yy9YhYu0W1a4cM88Wft0/export?format=csv"

    # Load Rings sheet
    try:
        rings_df = pd.read_csv(RINGS_SHEET_URL)
    except Exception as e:
        st.error(f"Failed to load Rings sheet: {e}")
        st.stop()

    # Load Members sheet
    try:
        members_df = pd.read_csv(MEMBERS_SHEET_URL)
    except Exception as e:
        st.error(f"Failed to load Members sheet: {e}")
        st.stop()

    # Normalize columns
    col_map = {col.strip().upper(): col for col in rings_df.columns}
    expected = [
        "LAST NAME", "FIRST NAME", "ATA NUMBER", "DIVISION ASSIGNED",
        "TRADITIONAL FORM", "TRADITIONAL SPARRING", "TRADITIONAL WEAPONS",
        "COMBAT WEAPONS", "COMPETITION DAY", "RING NUMBER", "TIME"
    ]
    display_cols = [col_map[c] for c in expected if c in col_map]

    st.subheader("Filters")

    name_query = st.text_input("Name (partial or full):").strip().lower()
    div_col = col_map.get("DIVISION ASSIGNED")
    divisions = sorted(rings_df[div_col].dropna().astype(str).unique()) if div_col else []
    sel_div = st.selectbox("Division Assigned:", [""] + divisions)
    school_query = st.text_input("School Number:").strip()

    filtered_df = rings_df.copy()

    # --- NAME FILTER ---
    if name_query:
        ln_col = col_map.get("LAST NAME")
        fn_col = col_map.get("FIRST NAME")
        if ln_col and fn_col:
            mask = (
                rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
            )
            filtered_df = filtered_df.loc[mask]

    # --- DIVISION FILTER ---
    if sel_div and div_col:
        filtered_df = filtered_df[filtered_df[div_col].astype(str) == sel_div]

    # --- SCHOOL FILTER ---
    if school_query:
        members_df['LicenseNumber'] = members_df['LicenseNumber'].astype(str).str.strip()
        members_df['FullName'] = (members_df['MemberFirstName'].str.strip() + " " + members_df['MemberLastName'].str.strip()).str.lower()
        member_names = members_df[members_df['LicenseNumber'] == school_query]['FullName'].tolist()
        ln_col = col_map.get("LAST NAME")
        fn_col = col_map.get("FIRST NAME")
        filtered_df['FullName'] = (filtered_df[fn_col].astype(str).str.strip() + " " + filtered_df[ln_col].astype(str).str.strip()).str.lower()
        filtered_df = filtered_df[filtered_df['FullName'].isin(member_names)]
        filtered_df = filtered_df.drop(columns=['FullName'])

    st.subheader(f"Search Results ({len(filtered_df)})")
    if not filtered_df.empty:
        st.dataframe(filtered_df[display_cols].reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.info("No results found. Use a filter or select a division/school.")
