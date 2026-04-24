import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import io
import concurrent.futures

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
    },
    "2nd/3rd Degree Black Belt Women 50-59": {
        "code": "W23D",
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23D",
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

# Build district map for District qualifiers
# Build full-name → abbreviation lookup from REGION_CODES
name_to_abbrev = {
    full_name: abbrev
    for full_name, (country, abbrev) in REGION_CODES.items()
}

# Build District → [state_abbrev] mapping from the Google Sheet
DISTRICT_MAP = {}

for _, row in district_df.iterrows():
    district = row["District"]
    states_str = row["States and Provinces"]

    abbrs = []
    for s in str(states_str).split(","):
        s_clean = s.strip()
        abbr = name_to_abbrev.get(s_clean)
        if abbr:
            abbrs.append(abbr)

    DISTRICT_MAP[district] = abbrs


#Defining Matrix for District and World Qualifiers here
MATRIX_SHEET_URL_V2 = (
    "https://docs.google.com/spreadsheets/d/"
    "1I6rKmEwf5YR7knC404v2hKH0ZzPu1Xr_mtQeLRW_ymA/"
    "export?format=csv&gid=0"
)

@st.cache_data(ttl=3600)
def load_matrix_groups_v2():
    try:
        df = pd.read_csv(MATRIX_SHEET_URL_V2)

        groups = {}

        for _, row in df.iterrows():
            div_name = str(row["Age Group"]).strip()
            code = str(row["Code"]).strip()

            # Build URLs using the formats YOU confirmed
            world_url = (
                "https://atamartialarts.com/events/tournament-standings/"
                f"worlds-standings/?code={code}"
            )

            state_url_template = (
                "https://atamartialarts.com/events/tournament-standings/"
                "state-standings/?country={}&state={}&code=" + code
            )

            groups[div_name] = {
                "code": code,
                "world_url": world_url,
                "state_url_template": state_url_template
            }

        return groups

    except Exception:
        return {}

MATRIX_GROUPS = load_matrix_groups_v2()

# New fetch function only for District and World Qualifiers

def fetch_html_v2(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://atamartialarts.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and len(r.text) > 5000:
            return r.text
    except:
        return None
    return None

# New parse for District and Worlds 
def parse_multi_event_standings(html: str):
    soup = BeautifulSoup(html, "html.parser")

    EVENT_MAP = {
        "Forms": "Forms",
        "Weapons": "Weapons",
        "Combat Weapons": "Combat Weapons",
        "Sparring": "Sparring",
        "Creative Forms": "Creative Forms",
        "Creative Weapons": "Creative Weapons",
        "X-Treme Forms": "X-Treme Forms",
        "X-Treme Weapons": "X-Treme Weapons",
    }

    results = {ev: [] for ev in EVENT_MAP.values()}

    # Find all event headers
    headers = soup.find_all("ul", class_="tournament-header")

    for header in headers:
        # Extract event name
        span = header.find("span", class_="text-primary text-uppercase")
        if not span:
            continue

        event_name = span.get_text(strip=True)

        if event_name not in EVENT_MAP:
            continue

        # Find the NEXT table after this header
        table = header.find_next("table")
        if not table:
            continue

        tbody = table.find("tbody")
        if not tbody:
            continue

        rows = []

        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) != 4:
                continue

            place_s, name, pts_s, loc = cols

            try:
                pts_val = int(pts_s)
            except:
                continue

            rows.append({
                "Rank": int(place_s),
                "Name": name.strip(),
                "Points": pts_val,
                "Location": loc.strip()
            })

        if rows:
            results[event_name] = rows

    return results

# Function to normalize the town name if it's more than one word
def normalize_town(t: str) -> str:
    if not isinstance(t, str):
        return ""
    return (
        t.lower()
         .replace(",", " ")
         .replace(".", " ")
         .replace("  ", " ")
         .strip()
    )


import requests
from bs4 import BeautifulSoup
import unicodedata
import pandas as pd
import streamlit as st

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

    # Province name → abbreviation
    PROVINCE_NAME_TO_ABBREV = {
        "Alberta": "AB",
        "British Columbia": "BC",
        "Manitoba": "MB",
        "New Brunswick": "NB",
        "Newfoundland and Labrador": "NL",
        "Nova Scotia": "NS",
        "Ontario": "ON",
        "Prince Edward Island": "PE",
        "Quebec": "QC",
        "Saskatchewan": "SK",
    }

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
            if len(cols) != 4:
                continue

            rank_s, name, pts_s, loc = cols

            try:
                pts_val = int(pts_s)
            except:
                continue

            if pts_val <= 0:
                continue

            # --- FIX: Proper location parsing for Canada ---
            loc = loc.strip()
            loc_norm = loc.replace(", ", ",").replace(" ,", ",")

            if "," in loc_norm:
                town, region_part = loc_norm.split(",", 1)
            else:
                parts = loc_norm.split()
                if len(parts) > 1:
                    town = " ".join(parts[:-1])
                    region_part = parts[-1]
                else:
                    town = loc_norm
                    region_part = ""

            town = town.strip()
            region_part = region_part.strip()

            # Convert province names → abbreviations
            if region_part.title() in PROVINCE_NAME_TO_ABBREV:
                state_abbrev = PROVINCE_NAME_TO_ABBREV[region_part.title()]
            else:
                state_abbrev = region_part.replace(".", "").strip().upper()

            data[ev_name].append({
                "Rank": int(rank_s),
                "Name": name.strip(),
                "Points": pts_val,
                "Town": town,
                "State": state_abbrev,
                "Location": loc.strip()
            })

    return data


def gather_data(group_key: str, region_choice: str, district_choice: str):
    group = GROUPS[group_key]
    combined = {ev: [] for ev in EVENT_NAMES}

    # Determine which regions to fetch
    regions_to_fetch = []
    if district_choice:
        states_in_district = district_df.loc[
            district_df['District'] == district_choice,
            'States and Provinces'
        ].iloc[0]
        regions_to_fetch = [s.strip() for s in states_in_district.split(',')]

        # If user selected a specific region, override
        if region_choice:
            regions_to_fetch = [region_choice]

    else:
        if region_choice not in ["All", "International"]:
            regions_to_fetch = [region_choice]
        elif region_choice == "All":
            regions_to_fetch = list(REGION_CODES.keys())
        elif region_choice == "International":
            regions_to_fetch = []

    # WORLD DATA
    world_html = fetch_html(group["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    # STATE / PROVINCE DATA
    for region in regions_to_fetch:

        # --- FIX 1: Convert abbreviations (BC, ON, QC) → full province name ---
        if region not in REGION_CODES:
            for full_name, (country_tmp, abbrev_tmp) in REGION_CODES.items():
                if region.upper() == abbrev_tmp.upper():
                    region = full_name
                    break

        # If still not valid, skip
        if region not in REGION_CODES:
            continue

        country, state_code = REGION_CODES[region]

        # --- FIX 2 & 3: Correct Canadian URL format ---
        if country == "CA":
            # Lowercase province code
            state_code_for_url = state_code.lower()

            # Full province name for region=
            region_param = region.replace(" ", "+")

            url = (
                f"{group['state_url_template'].format(country, state_code_for_url, group['code'])}"
                f"&region={region_param}"
            )
        else:
            # US states use normal URL
            url = group["state_url_template"].format(country, state_code, group["code"])    
        # DEBUG
        #st.write("DEBUG URL:", url)
        
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)
        st.write("DEBUG: about to fetch", url)
        #html = None
        #try:
         #   html = fetch_html(url)
          #  st.write("DEBUG: fetch_html returned", "None" if html is None else f"len={len(html)}")
        #except Exception as e:
         #   st.write("DEBUG: fetch_html ERROR:", repr(e))

        #if html:
         #   try:
          #      state_data = parse_standings(html)
           #     total_rows = sum(len(v) for v in state_data.values())
            #    st.write("DEBUG: parse_standings events:", list(state_data.keys()))
             #   st.write("DEBUG: parse_standings total rows:", total_rows)
                # 🔴 THIS is what was effectively removed before
              #  for ev, entries in state_data.items():
               #     combined[ev].extend(entries)
            #except Exception as e:
             #   st.write("DEBUG: parse_standings ERROR:", repr(e))

    # INTERNATIONAL FILTER
    if region_choice == "International":
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            for e in entries:
                # Keep entries that do NOT end with ", XX"
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


@st.cache_data(ttl=3600)
def load_all_title_tabs(sheet_id: str, tabs: dict):
    all_tabs = {}

    for title, gid in tabs.items():
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        try:
            df = pd.read_csv(csv_url)
            all_tabs[title] = df
        except Exception as e:
            print(f"Failed to load sheet {title} (gid={gid}): {e}")

    return all_tabs

SHEET_ID = "1drOQVqj11RGyw1Xda__hVY1zHI8bfH_Hs25pGn-yiCc"

TITLE_TABS = {
    "23-24 GA State Title 50-59 Color Belt": 1450148970,
    "24-25 GA State Title 50-59 Color Belt": 0,
    "24-25 FL State Title 50-59 Color Belt": 1239264195,
    "24-25 SE District Title 50-59 Color Belt": 632203910,
    "23-24 SE District Title 50-59 Color Belt": 1408227945,
    "24-25 SE District Title 50-59 1st Degree Black Belt": 1588231489,
    "24-25 World Title 50-59 1st Degree Black Belt": 250495899
}

all_titles = load_all_title_tabs(SHEET_ID, TITLE_TABS)
tab_names = list(all_titles.keys()) 


# --- PAGE SELECTION ---
page_choice = st.selectbox(
    "Select a page:",
    [
        "ATA Standings Dashboard",
        "1st Degree Black Belt Women 50-59",
        "National & District Rings",
        "Historical Titles",
        "State Champions, District & World Qualifiers (All Divisions)"
        "Team Sparring"
#        "Competitor Search"
    ]
)

# --- PAGE 1: Standings Dashboard ---
if page_choice == "ATA Standings Dashboard":
    st.title("ATA Standings Dashboard")

    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.session_state.last_refresh = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Data refreshed successfully!")
    st.caption(f"Last refreshed: {st.session_state.last_refresh}")

    is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"
    group_choice = st.selectbox("Select group:", list(GROUPS.keys()))
    district_choice = st.selectbox("Select District (optional):", [""] + sorted(district_df['District'].unique()))
    region_options = []
    if district_choice:
        states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
        region_options = [s.strip() for s in states_in_district.split(',')]
        region_choice = st.selectbox("Select Region (optional):", [""] + region_options)
    else:
        region_choice = st.selectbox("Select Region:", REGIONS)
    event_choice = st.selectbox("Select Event (optional):", [""] + EVENT_NAMES)
    name_filter = st.text_input("Search competitor name (optional):").strip().lower()

    sheet_df = pd.DataFrame()
    if GROUPS[group_choice]["sheet_url"]:
        sheet_df = fetch_sheet(GROUPS[group_choice]["sheet_url"])

    go = st.button("Go")

    if go:
        with st.spinner("Loading standings..."):
            raw_data, has_results = gather_data(group_choice, region_choice, district_choice)
            data = dedupe_and_rank(raw_data)

        if not has_results:
            st.warning(f"No standings data found for {region_choice or district_choice}.")
        else:
            for ev in EVENT_NAMES:
                if event_choice and ev != event_choice:
                    continue
                rows = data.get(ev, [])

                # enforce region/district membership
                if district_choice:
                    if region_choice:
                        if region_choice in REGION_CODES:
                            _, abbrev = REGION_CODES[region_choice]
                            rows = [r for r in rows if r["Location"].endswith(f", {abbrev}")]
                    else:
                        states_in_district = district_df.loc[district_df['District']==district_choice, 'States and Provinces'].iloc[0]
                        region_list = [s.strip() for s in states_in_district.split(',')]
                        abbrevs = [REGION_CODES[r][1] for r in region_list if r in REGION_CODES]
                        rows = [r for r in rows if any(r["Location"].endswith(f", {abbr}") for abbr in abbrevs)]
                else:
                    if region_choice and region_choice != "All":
                        if region_choice in REGION_CODES:
                            _, abbrev = REGION_CODES[region_choice]
                            rows = [r for r in rows if r["Location"].endswith(f", {abbrev}")]

                if name_filter:
                    rows = [r for r in rows if name_filter in r["Name"].lower()]

                if not rows:
                    continue

                # --- NEW RANK CALCULATION BY REGION/DISTRICT ---
                if district_choice:
                    rank_label = f"{district_choice} Rank"
                elif region_choice and region_choice not in ["All", "International", ""]:
                    rank_label = f"{region_choice} Rank"
                else:
                    rank_label = "World Rank"

                sorted_rows = sorted(rows, key=lambda x: (-x["Points"], x["Name"]))
                prev_points = None
                prev_rank = None
                current_pos = 1
                for r in sorted_rows:
                    if prev_points is None or r["Points"] != prev_points:
                        rank_to_assign = current_pos
                        r["Rank"] = rank_to_assign
                        prev_rank = rank_to_assign
                    else:
                        r["Rank"] = prev_rank
                    prev_points = r["Points"]
                    current_pos += 1

                st.subheader(f"{ev} — {rank_label}")

                if is_mobile:
                    main_df = pd.DataFrame(sorted_rows)[["Rank", "Name", "Location", "Points"]]
                    st.dataframe(main_df.reset_index(drop=True), use_container_width=True, hide_index=True)
                    for row in sorted_rows:
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
                    cols_header = st.columns([1, 5, 3, 2])
                    cols_header[0].write("Rank")
                    cols_header[1].write("Name")
                    cols_header[2].write("Location")
                    cols_header[3].write("Points")
                    for row in sorted_rows:
                        cols = st.columns([1, 5, 3, 2])
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

# --- PAGE 2: 50-59 Women ---
elif page_choice == "1st Degree Black Belt Women 50-59":
    st.title("1st Degree Black Belt Women 50-59")

    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.session_state.last_refresh = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Data refreshed successfully!")
    st.caption(f"Last refreshed: {st.session_state.last_refresh}")

    is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

    group_key = "1st Degree Black Belt Women 50-59"
    combined, _ = gather_data(group_key, "All", "")

    rows = {}
    for ev, entries in combined.items():
        for e in entries:
            name = e["Name"]
            location = e["Location"]
            if (name, location) not in rows:
                rows[(name, location)] = {ev2: "" for ev2 in EVENT_NAMES}
            rows[(name, location)][ev] = "X"

    df = pd.DataFrame([{"Name": k[0], "Location": k[1], **v} for k, v in rows.items()])

    if "Location" in df.columns:
        loc_split = df["Location"].str.split(",", n=1, expand=True)
        if loc_split.shape[1] == 2:
            df["Town"] = loc_split[0].str.strip()
            df["State"] = loc_split[1].str.strip()
        else:
            df["Town"] = df["Location"]
            df["State"] = ""

    cols = ["State", "Name", "Location"] + EVENT_NAMES
    df = df[cols]
    df = df.sort_values(by=["State", "Name"])

    if is_mobile:
        st.dataframe(df[["State", "Name"] + EVENT_NAMES].reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.dataframe(df.reset_index(drop=True), use_container_width=True, hide_index=True)

    counts_df = pd.DataFrame({
        "Event": EVENT_NAMES,
        "Competitors with Points": [df[ev].eq("X").sum() for ev in EVENT_NAMES]
    })

    st.subheader("Competitor Counts by Event")
    st.dataframe(counts_df.reset_index(drop=True), use_container_width=True, hide_index=True)

# --- PAGE 3: National & District Rings ---
elif page_choice == "National & District Rings":
    st.title("National & District Tournament Rings")

    # New dropdown for event selection
    event_choice = st.selectbox(
        "Select Event:",
        ["Fall Nationals 2025", "Spring Nationals 2026", "Districts 2026", "Super 20 2026"],
        index=0
    )

    if event_choice == "Fall Nationals 2025":
        # Dropdown selector
        section_choice = st.selectbox(
            "Select Category:",
            ["Traditional", "Creative & Xtreme", "Judging Assignment"],
            index=0
        )

        # --- TRADITIONAL ---
        if section_choice == "Traditional":
            # This was ATA RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1314980945"
            RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/19RYwkLfzdwg8r105flePpgRbbf5RvHM3JZohS1bKBDY/gviz/tq?tqx=out:csv&gid=253724932"
            MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"
            
            # Load Rings sheet
            try:
                rings_df = pd.read_csv(RINGS_CSV_URL)
                st.success("✅ Rings sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Rings sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            # Load Members sheet
            try:
                members_df = pd.read_csv(MEMBERS_SHEET_URL, dtype=str)
                st.success("✅ Members sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Members sheet: {e}")
                st.stop()

            # --- SEARCH OPTIONS ---
            search_type = st.radio("Search by:", ["Name", "Division Assigned", "Member License Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name (Last, First, or both):").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "Division Assigned":
                div_col = col_map.get("TRADITIONAL RING IDENTIFIER")
                if div_col:
                    divisions = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select Division Assigned (or leave blank):", [""] + divisions)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            else:  # Member License Number
                lic_query = st.text_input("Enter License Number:").strip()
                if lic_query:
                    members_filtered = members_df[members_df['LicenseNumber'].astype(str) == lic_query]
                    if not members_filtered.empty:
                        members_filtered['FullName'] = (
                            members_filtered['MemberFirstName'].str.strip() + " " +
                            members_filtered['MemberLastName'].str.strip()
                        ).str.lower()
                        ln_col = col_map.get("LAST NAME")
                        fn_col = col_map.get("FIRST NAME")
                        if ln_col and fn_col:
                            rings_fullname = (
                                rings_df[fn_col].astype(str).str.strip() + " " +
                                rings_df[ln_col].astype(str).str.strip()
                            ).str.lower()
                            mask = rings_fullname.isin(members_filtered['FullName'])
                            results = rings_df.loc[mask].copy()

            # Columns to display (hide ONE STEPS)
            display_cols = [c for c in original_columns if "ONE STEPS" not in c]

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results[display_cols].reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term, select a division, or enter a License Number.")


        # --- CREATIVE & XTREME ---
        elif section_choice == "Creative & Xtreme":
            st.subheader("Creative & Xtreme Rings")

            #This was ATA XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=852123357"
            XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/1SPoBVRM27TvqDc1SlegCdi5K5mY6kjTSPDTnp0qgAHQ/gviz/tq?tqx=out:csv&gid=1329644400"
            MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"

            try:
                rings_df = pd.read_csv(XRINGS_CSV_URL)
                st.success("✅ C/X Rings sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load C/X Rings sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            try:
                members_df = pd.read_csv(MEMBERS_SHEET_URL, dtype=str)
                st.success("✅ Members sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Members sheet: {e}")
                st.stop()

            search_type = st.radio("Search by:", ["Name", "Division Assigned", "Member License Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name (Last, First, or both):").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "Division Assigned":
                div_col = col_map.get("C/X RING IDENTIFIER")
                if div_col:
                    divisions = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select Division Assigned (or leave blank):", [""] + divisions)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            else:  # Member License Number
                lic_query = st.text_input("Enter License Number:").strip()
                if lic_query:
                    members_filtered = members_df[members_df['LicenseNumber'].astype(str) == lic_query]
                    if not members_filtered.empty:
                        members_filtered['FullName'] = (
                            members_filtered['MemberFirstName'].str.strip() + " " +
                            members_filtered['MemberLastName'].str.strip()
                        ).str.lower()
                        ln_col = col_map.get("LAST NAME")
                        fn_col = col_map.get("FIRST NAME")
                        if ln_col and fn_col:
                            rings_fullname = (
                                rings_df[fn_col].astype(str).str.strip() + " " +
                                rings_df[ln_col].astype(str).str.strip()
                            ).str.lower()
                            mask = rings_fullname.isin(members_filtered['FullName'])
                            results = rings_df.loc[mask].copy()

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results.reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term, select a division, or enter a License Number.")


        # --- JUDGING ASSIGNMENTS ---
        elif section_choice == "Judging Assignment":
            st.subheader("Judging Assignments")
            st.write("✅ Entered Judging Assignments block")  # Debug

            #This was ATA JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1460144985"
            JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/1dwiw1x6Lh081__L5pt5RSJMuBXmDxmcnRpYClLBcBVI/gviz/tq?tqx=out:csv&gid=993945995"
            
            try:
                rings_df = pd.read_csv(JUDGE_CSV_URL)
                st.success("✅ Judges sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Judges sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            search_type = st.radio("Search by:", ["Name", "ATA Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name:").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "ATA Number":
                div_col = col_map.get("ATA#")
                if div_col:
                    atanums = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select ATA Number (or leave blank):", [""] + atanums)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results.reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term or select an ATA Number.")

    elif event_choice == "Spring Nationals 2026":
        # Dropdown selector
        section_choice = st.selectbox(
            "Select Category:",
            ["Traditional", "Creative & Xtreme", "Judging Assignment"],
            index=0
        )

        # --- TRADITIONAL ---
        if section_choice == "Traditional":
            # This was ATA RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1314980945"
            #RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/19RYwkLfzdwg8r105flePpgRbbf5RvHM3JZohS1bKBDY/gviz/tq?tqx=out:csv&gid=253724932"
            RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTTFrARvkMq0WeTbARoOZq-iFeOUgMFya-PEMMVcNsXcIUtjoNmGnzfQ7YJIf7FHw/pub?output=csv"
            MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"
            
            # Load Rings sheet
            try:
                rings_df = pd.read_csv(RINGS_CSV_URL)
                st.success("✅ Rings sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Rings sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            # Load Members sheet
            try:
                members_df = pd.read_csv(MEMBERS_SHEET_URL, dtype=str)
                st.success("✅ Members sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Members sheet: {e}")
                st.stop()

            # --- SEARCH OPTIONS ---
            search_type = st.radio("Search by:", ["Name", "Division Assigned", "Member License Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name (Last, First, or both):").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "Division Assigned":
                div_col = col_map.get("DIVISION")
                if div_col:
                    divisions = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select Division Assigned (or leave blank):", [""] + divisions)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            else:  # Member License Number
                lic_query = st.text_input("Enter License Number:").strip()
                if lic_query:
                    members_filtered = members_df[members_df['LicenseNumber'].astype(str) == lic_query]
                    if not members_filtered.empty:
                        members_filtered['FullName'] = (
                            members_filtered['MemberFirstName'].str.strip() + " " +
                            members_filtered['MemberLastName'].str.strip()
                        ).str.lower()
                        ln_col = col_map.get("LAST NAME")
                        fn_col = col_map.get("FIRST NAME")
                        if ln_col and fn_col:
                            rings_fullname = (
                                rings_df[fn_col].astype(str).str.strip() + " " +
                                rings_df[ln_col].astype(str).str.strip()
                            ).str.lower()
                            mask = rings_fullname.isin(members_filtered['FullName'])
                            results = rings_df.loc[mask].copy()

            # Columns to display (hide ONE STEPS)
            display_cols = [c for c in original_columns if "ONE STEPS" not in c]

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results[display_cols].reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term, select a division, or enter a License Number.")


        # --- CREATIVE & XTREME ---
        elif section_choice == "Creative & Xtreme":
            st.subheader("Creative & Xtreme Rings")

            #This was ATA XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=852123357"
            #XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/1SPoBVRM27TvqDc1SlegCdi5K5mY6kjTSPDTnp0qgAHQ/gviz/tq?tqx=out:csv&gid=1329644400"
            XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR67mrU9boyeIE_8UZc3ZWgjDPSZeq-rcIaMfj222DEiLh75UbxwpNQ9uY7RuvOtA/pub?output=csv"
            MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"

            try:
                rings_df = pd.read_csv(XRINGS_CSV_URL)
                st.success("✅ C/X Rings sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load C/X Rings sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            try:
                members_df = pd.read_csv(MEMBERS_SHEET_URL, dtype=str)
                st.success("✅ Members sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Members sheet: {e}")
                st.stop()

            search_type = st.radio("Search by:", ["Name", "Division Assigned", "Member License Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name (Last, First, or both):").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "Division Assigned":
                div_col = col_map.get("DIVISION")
                if div_col:
                    divisions = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select Division Assigned (or leave blank):", [""] + divisions)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            else:  # Member License Number
                lic_query = st.text_input("Enter License Number:").strip()
                if lic_query:
                    members_filtered = members_df[members_df['LicenseNumber'].astype(str) == lic_query]
                    if not members_filtered.empty:
                        members_filtered['FullName'] = (
                            members_filtered['MemberFirstName'].str.strip() + " " +
                            members_filtered['MemberLastName'].str.strip()
                        ).str.lower()
                        ln_col = col_map.get("LAST NAME")
                        fn_col = col_map.get("FIRST NAME")
                        if ln_col and fn_col:
                            rings_fullname = (
                                rings_df[fn_col].astype(str).str.strip() + " " +
                                rings_df[ln_col].astype(str).str.strip()
                            ).str.lower()
                            mask = rings_fullname.isin(members_filtered['FullName'])
                            results = rings_df.loc[mask].copy()

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results.reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term, select a division, or enter a License Number.")


        # --- JUDGING ASSIGNMENTS ---
        elif section_choice == "Judging Assignment":
            st.subheader("Judging Assignments")
            st.write("✅ Entered Judging Assignments block")  # Debug

            #This was ATA JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1460144985"
            #JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/1dwiw1x6Lh081__L5pt5RSJMuBXmDxmcnRpYClLBcBVI/gviz/tq?tqx=out:csv&gid=993945995"
            JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTMNQlDIvId4c_mTWnNldw3XjrjV4Pv0Cf0R3zKkbObBdzvKQqL7leerwIMUpTmHw/pub?output=csv"
            try:
                rings_df = pd.read_csv(JUDGE_CSV_URL)
                st.success("✅ Judges sheet loaded successfully")
            except Exception as e:
                st.error(f"Failed to load Judges sheet: {e}")
                st.stop()

            original_columns = list(rings_df.columns)
            processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]
            col_map = dict(zip(processing_columns, original_columns))

            search_type = st.radio("Search by:", ["Name", "ATA Number"])
            results = pd.DataFrame(columns=rings_df.columns)

            if search_type == "Name":
                name_query = st.text_input("Enter full or partial name:").strip().lower()
                if name_query:
                    ln_col = col_map.get("LAST NAME")
                    fn_col = col_map.get("FIRST NAME")
                    if ln_col and fn_col:
                        mask = (
                            rings_df[ln_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | rings_df[fn_col].astype(str).str.lower().str.contains(name_query, na=False)
                            | (rings_df[ln_col].astype(str).str.lower() + " " + rings_df[fn_col].astype(str).str.lower()).str.contains(name_query, na=False)
                        )
                        results = rings_df.loc[mask].copy()

            elif search_type == "ATA Number":
                div_col = col_map.get("ATA#")
                if div_col:
                    atanums = sorted(rings_df[div_col].dropna().astype(str).unique())
                    sel_div = st.selectbox("Select ATA Number (or leave blank):", [""] + atanums)
                    if sel_div:
                        results = rings_df[rings_df[div_col].astype(str) == sel_div].copy()

            st.subheader(f"Search Results ({len(results)})")
            if not results.empty:
                st.dataframe(results.reset_index(drop=True), use_container_width=True, hide_index=True, height=600)
            else:
                st.info("No results found. Enter a search term or select an ATA Number.")
    else:
        st.info(f"🕓 {event_choice} — Coming soon...")
elif page_choice == "Historical Titles":
    st.title("Historical Titles Dashboard")

    # --- Search Mode Selector ---
    search_mode = st.selectbox(
        "Choose Search Mode:",
        ["Search by Title", "Search by Competitor"]
    )

    # -----------------------------
    # 1. SEARCH BY TITLE (original)
    # -----------------------------
    if search_mode == "Search by Title":

        tab_names = list(all_titles.keys())

        selected_tab = st.selectbox(
            "Select Title Sheet:",
            tab_names
        )

        df = all_titles[selected_tab]

        st.subheader(f"Viewing: {selected_tab}")
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ---------------------------------------
    # 2. SEARCH BY COMPETITOR (row-accurate)
    # ---------------------------------------
    else:
        st.subheader("Search Competitor Across All Titles")

        search_name = st.text_input("Enter competitor name")

        if search_name:
            results = []

            # All possible placement columns where names may appear
            placement_cols = [
                "World Champion",
                "Second",
                "Third",
                "District Champion",
                "State Champion"
            ]

            for sheet_name, title_df in all_titles.items():

                # Only search columns that exist in this sheet
                existing_cols = [c for c in placement_cols if c in title_df.columns]
                if not existing_cols:
                    continue

                # Build mask: competitor appears in ANY placement column (row-wise)
                mask = False
                for col in existing_cols:
                    mask = mask | title_df[col].astype(str).str.contains(
                        search_name, case=False, na=False
                    )

                matches = title_df[mask].copy()
                if matches.empty:
                    continue

                # --- Extract Year + Title from sheet name ---
                parts = sheet_name.split(" ", 1)

                if len(parts) == 2:
                    year_raw, title_raw = parts
                else:
                    year_raw = sheet_name
                    title_raw = ""

                # Convert "23-24" → "2023–2024"
                if "-" in year_raw and len(year_raw) == 5:
                    start, end = year_raw.split("-")
                    year = f"20{start}–20{end}"
                else:
                    year = year_raw

                matches["Year"] = year
                matches["Title"] = title_raw

                # --- Per-row Result: which column has this competitor in THIS row? ---
                def get_result(row):
                    for col in existing_cols:
                        val = str(row[col])
                        if search_name.lower() in val.lower():
                            return col
                    return ""

                matches["Result"] = matches.apply(get_result, axis=1)

                # Drop any rows where we somehow didn't find a result
                matches = matches[matches["Result"] != ""]

                if matches.empty:
                    continue

                # Event column (if present)
                if "Event" not in matches.columns:
                    matches["Event"] = ""

                # Keep only the useful columns
                matches = matches[["Year", "Title", "Event", "Result"]]

                results.append(matches)

            if results:
                combined = pd.concat(results, ignore_index=True)

                st.success(f"Found {len(combined)} results for '{search_name}'")
                st.dataframe(combined, use_container_width=True, hide_index=True)
            else:
                st.warning("No results found for that competitor.")
# --- PAGE: State Champions, District & World Qualifiers (All Divisions) ---
if page_choice == "State Champions, District & World Qualifiers (All Divisions)":
    st.title("State Champions, District & World Qualifiers — All Divisions")

    if not MATRIX_GROUPS:
        st.error("No divisions loaded from the Matrix spreadsheet.")
        st.stop()

    # --- REPORT TYPE SELECTOR ---
    report_type = st.radio(
        "Select Report Type:",
        [
            "District / World Qualifiers (Top 10)",
            "State Champions (Rank 1 + ties)",
            "District-wide Qualifiers (Top 10 in District)",
        ],
        key="report_type_all_divisions"
    )

    # --- MODE 1 & 2: STATE-BASED ---
    if report_type in [
        "District / World Qualifiers (Top 10)",
        "State Champions (Rank 1 + ties)",
    ]:
        state_choice = st.selectbox(
            "Select State:",
            sorted(REGION_CODES.keys()),
            key="state_choice_all_divisions"
        )

        st.write("### Town Filter (Optional)")
        town_text = st.text_input(
            "Type a town name:",
            key="town_text_all_divisions"
        )

        if report_type == "District / World Qualifiers (Top 10)":
            qualifier_type = st.radio(
                "Select Qualifier Type:",
                ["District Qualifiers (Top 10 State)", "World Qualifiers (Top 10 World)"],
                key="qualifier_type_all_divisions"
            )
        else:
            qualifier_type = "State Champions"

        go = st.button("Go", key="go_button_all_divisions")

    # --- MODE 3: DISTRICT-WIDE ---
    else:
        district_choice = st.selectbox(
            "Select District:",
            sorted(DISTRICT_MAP.keys()),
            key="district_choice_all_divisions"
        )

        division_choice = st.selectbox(
            "Select Division:",
            sorted(MATRIX_GROUPS.keys()),
            key="division_choice_all_divisions"
        )

        town_text = ""  # no town filter in this mode
        qualifier_type = "District-wide"
        go = st.button("Go", key="go_button_all_divisions")

    # --- WHEN GO IS CLICKED ---
    if go:
        st.info("Pulling ATA standings for all Matrix divisions…")

        results = []

        # Reverse lookup: abbrev → (country, state_name)
        abbrev_to_country = {
            abbrev: (country, state_name)
            for state_name, (country, abbrev) in REGION_CODES.items()
        }

        # --- PROVINCE NAME → ABBREV MAP ---
        PROVINCE_NAME_TO_ABBREV = {
            "Alberta": "AB",
            "British Columbia": "BC",
            "Manitoba": "MB",
            "New Brunswick": "NB",
            "Newfoundland and Labrador": "NL",
            "Nova Scotia": "NS",
            "Ontario": "ON",
            "Prince Edward Island": "PE",
            "Quebec": "QC",
            "Saskatchewan": "SK",
        }

        # --- MODE 1 & 2: STATE-BASED ---
        if report_type in [
            "District / World Qualifiers (Top 10)",
            "State Champions (Rank 1 + ties)",
        ]:
            country, state_abbrev = REGION_CODES[state_choice]
            state_full_name = state_choice  # needed for Canada region=

            for div_name, div_info in MATRIX_GROUPS.items():
                code = div_info["code"]

                # URL selection
                if report_type == "District / World Qualifiers (Top 10)" and "World" in qualifier_type:
                    url = div_info["world_url"]
                else:
                    # --- CANADA URL FIX ---
                    if country == "CA":
                        state_code_for_url = state_abbrev.lower()
                        region_param = state_full_name.replace(" ", "+")
                        url = (
                            f"{div_info['state_url_template'].format(country, state_code_for_url, code)}"
                            f"&region={region_param}"
                        )
                    else:
                        url = div_info["state_url_template"].format(country, state_abbrev, code)

                html = fetch_html_v2(url)
                if not isinstance(html, str) or not html.strip():
                    st.warning(f"Skipping {div_name} — invalid HTML returned for URL: {url}")
                    continue

                parsed = parse_multi_event_standings(html)
                ranked = dedupe_and_rank(parsed)

                for event_name, entries in ranked.items():
                    for e in entries:

                        # --- LOCATION PARSING ---
                        loc = e["Location"].strip()
                        loc_norm = loc.replace(", ", ",").replace(" ,", ",")

                        if "," in loc_norm:
                            town, region_part = loc_norm.split(",", 1)
                        else:
                            parts = loc_norm.split()
                            if len(parts) > 1:
                                town = " ".join(parts[:-1])
                                region_part = parts[-1]
                            else:
                                town = loc_norm
                                region_part = ""

                        town = town.strip()
                        region_part = region_part.strip()

                        # Province name → abbreviation
                        if region_part.title() in PROVINCE_NAME_TO_ABBREV:
                            st_abbrev2 = PROVINCE_NAME_TO_ABBREV[region_part.title()]
                        else:
                            st_abbrev2 = region_part.replace(".", "").strip().upper()

                        # --- DISTRICT FILTER (correct) ---
                        if "District" in qualifier_type:
                            allowed_states = DISTRICT_MAP.get(state_choice, [])
                            if st_abbrev2 not in allowed_states:
                                continue

                        # Town filter
                        if town_text:
                            if normalize_town(town_text) not in normalize_town(town):
                                continue

                        # Top 10 filter
                        if report_type == "District / World Qualifiers (Top 10)":
                            if e["Rank"] > 10:
                                continue

                        results.append({
                            "Name": e["Name"],
                            "Town": town,
                            "State": st_abbrev2,
                            "Event": event_name,
                            "Rank": e["Rank"],
                            "Points": e["Points"],
                            "Division": div_name,
                            "Code": code,
                        })

            # --- STATE CHAMPIONS FILTER ---
            if report_type == "State Champions (Rank 1 + ties)" and results:
                min_rank_by_event = {}
                for r in results:
                    ev = r["Event"]
                    rnk = r["Rank"]
                    if ev not in min_rank_by_event or rnk < min_rank_by_event[ev]:
                        min_rank_by_event[ev] = rnk

                results = [
                    r for r in results
                    if r["Rank"] == min_rank_by_event.get(r["Event"], r["Rank"])
                ]

        # --- MODE 3: DISTRICT-WIDE ---
        else:
            div_name = division_choice
            div_info = MATRIX_GROUPS[div_name]
            code = div_info["code"]

            for state_abbrev in DISTRICT_MAP.get(district_choice, []):
                if state_abbrev not in abbrev_to_country:
                    continue
                country, state_full_name = abbrev_to_country[state_abbrev]

                # --- CANADA URL FIX ---
                if country == "CA":
                    state_code_for_url = state_abbrev.lower()
                    region_param = state_full_name.replace(" ", "+")
                    url = (
                        f"{div_info['state_url_template'].format(country, state_code_for_url, code)}"
                        f"&region={region_param}"
                    )
                else:
                    url = div_info["state_url_template"].format(country, state_abbrev, code)

                html = fetch_html_v2(url)
                if not isinstance(html, str) or not html.strip():
                    st.warning(f"Skipping {div_name} / {state_abbrev} — invalid HTML returned for URL: {url}")
                    continue

                parsed = parse_multi_event_standings(html)
                ranked = dedupe_and_rank(parsed)

                for event_name, entries in ranked.items():
                    for e in entries:

                        # --- LOCATION PARSING ---
                        loc = e["Location"].strip()
                        loc_norm = loc.replace(", ", ",").replace(" ,", ",")

                        if "," in loc_norm:
                            town, region_part = loc_norm.split(",", 1)
                        else:
                            parts = loc_norm.split()
                            if len(parts) > 1:
                                town = " ".join(parts[:-1])
                                region_part = parts[-1]
                            else:
                                town = loc_norm
                                region_part = ""

                        town = town.strip()
                        region_part = region_part.strip()

                        # Province name → abbreviation
                        if region_part.title() in PROVINCE_NAME_TO_ABBREV:
                            st_abbrev2 = PROVINCE_NAME_TO_ABBREV[region_part.title()]
                        else:
                            st_abbrev2 = region_part.replace(".", "").strip().upper()

                        # --- DISTRICT FILTER ---
                        allowed_states = DISTRICT_MAP.get(district_choice, [])
                        if st_abbrev2 not in allowed_states:
                            continue

                        if e["Rank"] > 10:
                            continue

                        results.append({
                            "Name": e["Name"],
                            "Town": town,
                            "State": st_abbrev2,
                            "Event": event_name,
                            "Rank": e["Rank"],
                            "Points": e["Points"],
                            "Division": div_name,
                            "Code": code,
                        })

        # --- NO RESULTS ---
        if not results:
            st.session_state.pop("qual_df_all_divisions", None)
            st.warning("No qualifiers found for the selected filters.")
        else:
            # --- COLLATE RESULTS ---
            collated = {}

            for row in results:
                key = (row["Name"], row["Town"], row["State"], row["Division"])
                if key not in collated:
                    collated[key] = {
                        "Name": row["Name"],
                        "Town": row["Town"],
                        "State": row["State"],
                        "Division": row["Division"],
                        "Events": [],
                    }
                collated[key]["Events"].append(row["Event"])

            EVENT_ORDER = {
                "Forms": 1,
                "Weapons": 2,
                "Combat Weapons": 3,
                "Sparring": 4,
                "Creative Forms": 5,
                "Creative Weapons": 6,
                "X-Treme Forms": 7,
                "X-Treme Weapons": 8,
            }

            final_rows = []
            total_events = 0

            for data in collated.values():
                events = sorted(data["Events"], key=lambda e: EVENT_ORDER.get(e, 999))
                data["Events"] = "<br>".join(events)
                total_events += len(events)
                final_rows.append(data)

            df = pd.DataFrame(final_rows)

            # --- SORT BY LAST NAME ---
            def extract_last_name(full):
                parts = full.replace(",", "").split()
                if len(parts) == 0:
                    return ""
                suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
                if parts[-1].lower() in suffixes and len(parts) > 1:
                    return parts[-2]
                return parts[-1]

            df["LastName"] = df["Name"].apply(extract_last_name)
            df = df.sort_values(["LastName", "Name"]).reset_index(drop=True)
            df = df.drop(columns=["LastName"])

            # --- SUMMARY ROW ---
            if report_type in [
                "District / World Qualifiers (Top 10)",
                "State Champions (Rank 1 + ties)",
            ] and town_text:
                summary_row = {
                    "Name": f"Number of qualifiers: {len(df)}",
                    "Town": "",
                    "State": "",
                    "Division": "",
                    "Events": f"Number of events: {total_events}",
                }
                df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

            # --- REMOVE TOWN/STATE IF FILTERED ---
            if report_type in [
                "District / World Qualifiers (Top 10)",
                "State Champions (Rank 1 + ties)",
            ] and town_text:
                df = df.drop(columns=["Town", "State"])

            st.session_state["qual_df_all_divisions"] = df
            st.session_state["qual_report_type"] = report_type

    # --- DISPLAY + EXPORT ---
    if "qual_df_all_divisions" in st.session_state:
        df = st.session_state["qual_df_all_divisions"]
        report_type = st.session_state.get("qual_report_type", "")

        if report_type == "State Champions (Rank 1 + ties)":
            st.success(f"Found {len(df)} state champions.")
        elif report_type == "District-wide Qualifiers (Top 10 in District)":
            st.success(f"Found {len(df)} district-wide qualifiers.")
        else:
            st.success(f"Found {len(df)} qualifiers.")

        display_df = df.copy()

        html_table = """
<style>
table, th, td {
    text-align: left !important;
}
</style>
""" + display_df.to_html(index=False, escape=False)

        st.markdown(html_table, unsafe_allow_html=True)

        export_df = df.copy()
        export_df["Events"] = export_df["Events"].astype(str).str.replace("<br>", ", ")

        csv = export_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="qualifiers.csv",
            mime="text/csv"
        )
elif page_choice == "Team Sparring":
    st.title("Team Sparring")

    event_choice = st.selectbox(
        "Select Team Event:",
        ["Team Sparring"],  # you can add Team Combat later
    )

    div_choice = st.selectbox(
        "Select Division:",
        list(TEAM_SPAR_RING_PDFS.keys())
    )

    if st.button("Load Team Standings"):
        url = TEAM_SPAR_RING_PDFS[div_choice]
        with st.spinner("Loading team standings from PDF..."):
            df = load_team_pdf(url)

        if df.empty:
            st.warning("No table data found in this PDF (or parsing needs tuning).")
        else:
            # basic tidy display
            display_cols = []
            for c in ["Rank", "Team", "Location", "Points"]:
                if c in df.columns:
                    display_cols.append(c)
            if not display_cols:
                display_cols = df.columns

            st.dataframe(
                df[display_cols].reset_index(drop=True),
                use_container_width=True,
                hide_index=True
            )
        
