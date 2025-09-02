import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- CONFIG ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    "Georgia": ("US", "GA"),
    # Add other states/provinces as needed
}

STATE_URL_TEMPLATE = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D"
WORLD_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"

def normalize_name(name):
    return re.sub(r"\s+", " ", name.strip().lower())

@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_sheet():
    try:
        df = pd.read_csv(SHEET_URL)
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors='coerce').fillna(0)
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
                        "Name": name.title(),
                        "Points": pts_val,
                        "Location": loc
                    })
    return data

def gather_data(selected):
    combined = {ev: [] for ev in EVENT_NAMES}
    # Only GA example here
    if selected in REGION_CODES:
        country, code = REGION_CODES[selected]
        html = fetch_html(STATE_URL_TEMPLATE.format(country, code))
        if html:
            combined = parse_standings(html)
            return combined, any(len(lst) > 0 for lst in combined.values())
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

# --- STREAMLIT APP ---
st.title("ATA W01D Standings")

sheet_df = fetch_sheet()
selection = st.selectbox("Select region:", ["Georgia"])
go = st.button("Go")

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
                # Build table manually
                for row in rows:
                    # Name clickable
                    key = f"{ev}-{row['Name']}"
                    if st.button(row["Name"], key=key):
                        comp_data = sheet_df[
                            (sheet_df['Name'].apply(lambda x: normalize_name(x)) == normalize_name(row['Name'])) &
                            (sheet_df[ev] > 0)
                        ][["Date","Tournament",ev]].rename(columns={ev:"Points"})
                        if not comp_data.empty:
                            st.dataframe(comp_data, use_container_width=True)
                        else:
                            st.write("No tournament data for this event.")
                    st.write(f"Rank: {row['Rank']} | Points: {row['Points']} | Location: {row['Location']}")
