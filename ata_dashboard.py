import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- Constants ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    "Georgia": ("US", "GA"), "Florida": ("US", "FL")  # Example; add all as needed
}

REGIONS = ["All"] + list(REGION_CODES.keys()) + ["International"]

STATE_URL_TEMPLATE = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D"
WORLD_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

SHEET_URL = "https://docs.google.com/spreadsheets/d/<YOUR_SHEET_ID>/gviz/tq?tqx=out:csv"

# --- Functions ---
@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

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
                        "Name": name.title(),
                        "Points": pts_val,
                        "Location": loc
                    })
    return data

@st.cache_data(ttl=3600)
def fetch_google_sheet():
    try:
        df = pd.read_csv(SHEET_URL)
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def gather_data(selected):
    combined = {ev: [] for ev in EVENT_NAMES}
    # World standings for international
    world_html = fetch_html(WORLD_URL)
    if world_html:
        world_data = parse_standings(world_html)
        for ev, entries in world_data.items():
            combined[ev].extend(entries)
    # State standings
    if selected not in ["All", "International"]:
        country, code = REGION_CODES[selected]
        url = STATE_URL_TEMPLATE.format(country, code)
        html = fetch_html(url)
        if html:
            state_data = parse_standings(html)
            for ev, entries in state_data.items():
                combined[ev].extend(entries)
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
    if selected == "International":
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

# --- Streamlit UI ---
st.title("ATA W01D Standings with Tournament Popups")

selection = st.selectbox("Select region:", REGIONS)
go = st.button("Go")

sheet_df = fetch_google_sheet()

if go:
    with st.spinner("Loading standings..."):
        raw, has_results = gather_data(selection)
        data = dedupe_and_rank(raw)

    if not has_results:
        st.warning(f"There are no 50‑59 1st Degree Women for {selection}.")
    else:
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            if rows:
                st.subheader(ev)
                # Table headers
                st.write(f"| Rank | Name | Points | Location |")
                st.write(f"| --- | --- | --- | --- |")
                for row in rows:
                    # Lookup tournaments in Google Sheet
                    name_match = sheet_df[sheet_df['Name'].str.lower() == row["Name"].lower()]
                    # Create expander with unique key
                    key_id = f"{row['Name']}-{ev}"
                    if not name_match.empty:
                        with st.expander(row["Name"], expanded=False, key=key_id):
                            st.write(f"**Tournament results for {ev}:**")
                            for _, r in name_match.iterrows():
                                pts = r[ev]
                                if pts > 0:
                                    st.write(f"{r['Date']}: {r['Tournament']} - {pts} pts")
                        # Show table row with clickable expander
                        st.markdown(f"| {row['Rank']} | {row['Name']} | {row['Points']} | {row['Location']} |")
                    else:
                        st.markdown(f"| {row['Rank']} | {row['Name']} | {row['Points']} | {row['Location']} |")
else:
    st.info("Select a region or 'International' and click Go to view standings.")
