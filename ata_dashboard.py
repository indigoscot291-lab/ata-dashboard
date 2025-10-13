import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")

# --- SESSION STATE ---
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = "Never"

# --- CONSTANTS ---
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

# --- HELPER FUNCTIONS ---
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
    ["ATA Standings Dashboard", "1st Degree Black Belt Women 50-59", "Rings Lookup"]
)

# --- PAGE 1: STANDINGS DASHBOARD ---
if page_choice == "ATA Standings Dashboard":
    st.title("ATA Standings Dashboard")
    st.write("Your original dashboard code goes here (unchanged).")

# --- PAGE 2: 50-59 WOMEN PAGE ---
elif page_choice == "1st Degree Black Belt Women 50-59":
    st.title("1st Degree Black Belt Women 50-59")
    st.write("Your original second page code goes here (unchanged).")

# --- PAGE 3: RINGS LOOKUP ---
elif page_choice == "Rings Lookup":
    st.title("Rings Lookup")

    # --- LOAD DATA ---
    rings_df = fetch_sheet("https://docs.google.com/spreadsheets/d/1grZSp3fr3lZy4ScG8EqbvFCkNJm_jK3KjNhh2BXJm9A/export?format=csv")
    school_df = fetch_sheet("https://docs.google.com/spreadsheets/d/1wHqNyL4GoCKYuPKE-Asbc_9Yy9YhYu0W1a4cM88Wft0/export?format=csv")

    if rings_df.empty or school_df.empty:
        st.warning("Unable to load one or more Google Sheets.")
    else:
        # --- CLEAN COLUMNS ---
        rings_df.columns = rings_df.columns.str.strip().str.upper()
        school_df.columns = school_df.columns.str.strip()

        # --- SEARCH INPUTS ---
        col1, col2, col3 = st.columns(3)
        with col1:
            name_search = st.text_input("Search by Name (First, Last, or Both)").strip().lower()
        with col2:
            division_search = st.text_input("Search by Division Assigned").strip().lower()
        with col3:
            school_search = st.text_input("Search by School Number (LicenseNumber)").strip()

        filtered_df = rings_df.copy()

        # --- FILTER NAME ---
        if name_search:
            filtered_df = filtered_df[
                filtered_df["FIRST NAME"].str.lower().str.contains(name_search, na=False)
                | filtered_df["LAST NAME"].str.lower().str.contains(name_search, na=False)
                | (filtered_df["FIRST NAME"].str.lower() + " " + filtered_df["LAST NAME"].str.lower()).str.contains(name_search, na=False)
            ]

        # --- FILTER DIVISION ---
        if division_search:
            filtered_df = filtered_df[
                filtered_df["DIVISION ASSIGNED"].str.lower().str.contains(division_search, na=False)
            ]

        # --- FILTER SCHOOL ---
        if school_search:
            school_filtered = school_df[
                school_df["LicenseNumber"].astype(str).str.strip() == school_search
            ]
            if not school_filtered.empty:
                school_filtered["match_name"] = (
                    school_filtered["MemberFirstName"].str.strip().str.lower() + " " +
                    school_filtered["MemberLastName"].str.strip().str.lower()
                )
                rings_df["match_name"] = (
                    rings_df["FIRST NAME"].str.strip().str.lower() + " " +
                    rings_df["LAST NAME"].str.strip().str.lower()
                )
                valid_names = set(school_filtered["match_name"])
                filtered_df = filtered_df[
                    rings_df["match_name"].isin(valid_names)
                ]
            else:
                filtered_df = pd.DataFrame()

        # --- DISPLAY RESULTS ---
        if filtered_df.empty:
            st.warning("No results found.")
        else:
            display_cols = [
                "LAST NAME", "FIRST NAME", "ATA NUMBER", "DIVISION ASSIGNED",
                "TRADITIONAL FORM", "TRADITIONAL SPARRING", "TRADITIONAL WEAPONS",
                "COMBAT WEAPONS", "COMPETITION DAY", "RING NUMBER", "TIME"
            ]
            available_cols = [col for col in display_cols if col in filtered_df.columns]
            st.dataframe(filtered_df[available_cols].reset_index(drop=True), use_container_width=True, hide_index=True)

