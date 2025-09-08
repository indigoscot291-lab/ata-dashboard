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

# Two groups
GROUPS = {
    "1st Degree Women 50-59": {
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D",
        "state_url": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"
    },
    "2nd/3rd Degree Women 40-49": {
        "world_url": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state_url": "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W23C",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv"
    }
}

# Districts sheet
DISTRICT_SHEET = "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"

# --- FUNCTIONS ---
@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        return None
    return None

@st.cache_data(ttl=3600)
def fetch_sheet(url):
    try:
        df = pd.read_csv(url)
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors="coerce").fillna(0)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_districts():
    try:
        df = pd.read_csv(DISTRICT_SHEET)
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

def gather_data(group_config, region_code):
    combined = {ev: [] for ev in EVENT_NAMES}
    world_html = fetch_html(group_config["world_url"])
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)

    if region_code and region_code != "All":
        url = group_config["state_url"].format("US", region_code)
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev] = entries
            return combined, any(len(lst) > 0 for lst in state_data.values())

    return combined, any(len(lst) > 0 for lst in combined.values())

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
        # Rank with ties
        unique.sort(key=lambda x: x["Points"], reverse=True)
        rank, prev_points, skip = 0, None, 0
        for idx, row in enumerate(unique, start=1):
            if row["Points"] != prev_points:
                rank = idx
            else:
                skip += 1
            row["Rank"] = rank
            prev_points = row["Points"]
        clean[ev] = unique
    return clean

# --- STREAMLIT APP ---
st.title("ATA Tournament Standings")

is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"])

district_df = fetch_districts()
if district_df.empty:
    st.error("Could not load district data.")
else:
    DISTRICTS = ["All"] + sorted(district_df["District"].dropna().unique())

    group_choice = st.selectbox("Select Group:", list(GROUPS.keys()))
    district_choice = st.selectbox("Select District:", DISTRICTS)

    # Filter regions based on district
    if district_choice != "All":
        district_row = district_df[district_df["District"] == district_choice]
        if not district_row.empty:
            allowed_regions = [
                r.strip() for r in district_row.iloc[0]["States and Provinces"].split(",")
            ]
        else:
            allowed_regions = []
    else:
        allowed_regions = sorted(set(sum(
            [str(x).split(",") for x in district_df["States and Provinces"].dropna()],
            []
        )))

    region_choice = st.selectbox("Select Region:", ["All"] + allowed_regions)

    name_search = st.text_input("Search by Name (optional)").strip()

    go = st.button("Go")

    if go:
        with st.spinner("Loading standings..."):
            group_config = GROUPS[group_choice]
            sheet_df = fetch_sheet(group_config["sheet_url"])
            region_code = region_choice if region_choice != "All" else None
            raw, has_results = gather_data(group_config, region_code)
            data = dedupe_and_rank(raw)

        if not has_results:
            st.warning("No standings data found for this selection.")
        else:
            for ev in EVENT_NAMES:
                rows = data.get(ev, [])
                if name_search:
                    rows = [r for r in rows if name_search.lower() in r["Name"].lower()]
                if rows:
                    st.subheader(ev)
                    # Desktop
                    if is_mobile == "No":
                        cols_header = st.columns([1, 4, 2, 1])
                        cols_header[0].write("Rank")
                        cols_header[1].write("Name")
                        cols_header[2].write("Location")
                        cols_header[3].write("Points")
                        for row in rows:
                            cols = st.columns([1, 4, 2, 1])
                            cols[0].write(row["Rank"])
                            with cols[1].expander(row["Name"]):
                                comp_data = sheet_df[
                                    (sheet_df["Name"].str.lower() == row["Name"].lower()) &
                                    (sheet_df[ev] > 0)
                                ][["Date", "Tournament", "Type", ev]].rename(columns={ev: "Points"})
                                if not comp_data.empty:
                                    st.dataframe(
                                        comp_data.reset_index(drop=True),
                                        use_container_width=True
                                    )
                                else:
                                    st.write("No tournament data for this event.")
                            cols[2].write(row["Location"])
                            cols[3].write(row["Points"])
                    # Mobile
                    else:
                        st.table(pd.DataFrame(rows)[["Rank", "Name", "Location", "Points"]])
                        for row in rows:
                            with st.expander(row["Name"]):
                                comp_data = sheet_df[
                                    (sheet_df["Name"].str.lower() == row["Name"].lower()) &
                                    (sheet_df[ev] > 0)
                                ][["Date", "Tournament", "Type", ev]].rename(columns={ev: "Points"})
                                if not comp_data.empty:
                                    st.dataframe(
                                        comp_data.reset_index(drop=True),
                                        use_container_width=True
                                    )
                                else:
                                    st.write("No tournament data for this event.")
