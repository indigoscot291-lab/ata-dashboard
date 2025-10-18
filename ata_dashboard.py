import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import io

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

    # Add a dropdown selector
    section_choice = st.selectbox(
        "Select Category:",
        ["Traditional", "Creative & Xtreme", "Judging Assignment"],
        index=0
    )

    import io

    if section_choice == "Traditional":
        # Direct CSV export link from Google Sheet
        RINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1314980945"
        MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"

        # Load Rings sheet
        try:
            rings_df = pd.read_csv(RINGS_CSV_URL)
            st.success("✅ Rings sheet loaded successfully")
        except Exception as e:
            st.error(f"Failed to load Rings sheet: {e}")
            st.stop()

        # Keep original headers for display
        original_columns = list(rings_df.columns)

        # Create processing headers using only the top word (first line of multi-line cells)
        processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]

        # Map processing column names to original columns
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
            st.dataframe(
                results[display_cols].reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
                height=600
            )
        else:
            st.info("No results found. Enter a search term, select a division, or enter a License Number.")


    # --- CREATIVE & XTREME ---
    elif section_choice == "Creative & Xtreme":
        st.subheader("Creative & Xtreme Rings")

        XRINGS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=852123357"
        MEMBERS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1aKKUuMbz71NwRZR-lKdVo52X3sE-XgOJjRyhvlshOdM/export?format=csv"

        # Load Rings sheet
        try:
            rings_df = pd.read_csv(XRINGS_CSV_URL)
            st.success("✅ C/X Rings sheet loaded successfully")
        except Exception as e:
            st.error(f"Failed to load C/X Rings sheet: {e}")
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
            st.dataframe(results.reset_index(drop=True),
                         use_container_width=True,
                         hide_index=True,
                         height=600)
        else:
            st.info("No results found. Enter a search term, select a division, or enter a License Number.")

# --- JUDGING ASSIGNMENTS ---
elif section_choice == "Judging Assignment":
    st.subheader("Judging Assignments")

    # Debug: indicate the block is entered
    st.write("🔹 Entered Judging Assignments section")

    # Direct CSV export link from Google Sheet
    JUDGE_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTJOBNJ49nc8Scigr4QfyQJphqeK-pmEs9oDxNXSAekIECIsdnQF4LpjKzRABCF9g/pub?output=csv&gid=1460144985"
    st.write("Attempting to read CSV from:", JUDGE_CSV_URL)

    # Load Rings sheet
    try:
        rings_df = pd.read_csv(JUDGE_CSV_URL)
        st.success("✅ Judges sheet loaded successfully")
        st.write("Columns found:", list(rings_df.columns))
    except Exception as e:
        st.error(f"Failed to load Judges sheet: {e}")
        st.stop()

    # Keep original headers for display
    original_columns = list(rings_df.columns)

    # Create processing headers using only the top word (first line of multi-line cells)
    processing_columns = [c.split("\n")[0].strip() for c in rings_df.columns]

    # Map processing column names to original columns
    col_map = dict(zip(processing_columns, original_columns))

    # --- SEARCH OPTIONS ---
    search_type = st.radio("Search by:", ["Name", "ATA Number"])
    results = pd.DataFrame(columns=rings_df.columns)

    if search_type == "Name":
        name_query = st.text_input("Enter full or partial name (Last, First, or both):").strip().lower()
        st.write("Name search query:", name_query)
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
        atanums_col = col_map.get("ATA#")
        if atanums_col:
            atanums = sorted(rings_df[atanums_col].dropna().astype(str).unique())
            sel_ata = st.selectbox("Select ATA Number (or leave blank):", [""] + atanums)
            st.write("Selected ATA Number:", sel_ata)
            if sel_ata:
                results = rings_df[rings_df[atanums_col].astype(str) == sel_ata].copy()

    # Display results
    st.subheader(f"Search Results ({len(results)})")
    if not results.empty:
        st.dataframe(results.reset_index(drop=True),
                     use_container_width=True,
                     hide_index=True,
                     height=600)
    else:
        st.info("No results found. Enter a search term or select an ATA Number.")
