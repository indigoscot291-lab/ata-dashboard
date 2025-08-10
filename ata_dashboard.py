import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from functools import lru_cache

EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    "Alabama": ("US", "AL"), "Alaska": ("US", "AK"), "Arizona": ("US", "AZ"),
    # ... (other US states and Canadian provinces, as before)
    "Ontario": ("CA", "ON"), "Quebec": ("CA", "QC"), "Saskatchewan": ("CA", "SK")
}

REGIONS = ["All"] + list(REGION_CODES.keys())

STATE_URL = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D"
WORLD_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

@st.cache_data(show_spinner=False)
def fetch_html(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except:
        pass
    return None

def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    evt_data = {}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        ev_tag = header.find("span", class_="text-primary text-uppercase")
        if not ev_tag:
            continue
        ev_name = ev_tag.get_text(strip=True)
        if ev_name not in EVENT_NAMES:
            continue

        rows = []
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) == 4 and all(cols):
                place, name, pts, loc = cols
                try:
                    pts_int = int(pts)
                except:
                    continue
                if pts_int > 0:
                    rows.append({"Rank": int(place), "Name": name.title(), "Points": pts_int, "Location": loc})
        if rows:
            evt_data.setdefault(ev_name, []).extend(rows)
    return evt_data

def gather_data(selected_region):
    combined = {e: [] for e in EVENT_NAMES}

    # Add world data (filter locations without 2-letter code)
    world_html = fetch_html(WORLD_URL)
    if world_html:
        world = parse_html(world_html)
        # Keep only non-US/CA duplicates at end
        for ev, entries in world.items():
            for e in entries:
                if not re.search(r",\s*([A-Z]{2})$", e["Location"]):
                    combined[ev].append(e)

    # Add state/province data
    regions = REGION_CODES.keys() if selected_region == "All" else [selected_region]
    for reg in regions:
        country, code = REGION_CODES[reg]
        url = STATE_URL.format(country, code)
        html = fetch_html(url)
        if not html:
            continue
        region_data = parse_html(html)
        for ev, entries in region_data.items():
            combined[ev].extend(entries)

    return combined

def dedupe_and_rank(data):
    result = {}
    for ev, entries in data.items():
        seen = set()
        uniq = []
        for e in entries:
            key = (e["Name"], e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        uniq.sort(key=lambda x: x["Points"], reverse=True)
        for i, row in enumerate(uniq, start=1):
            row["Rank"] = i
        result[ev] = uniq
    return result

# -- Streamlit UI --
st.title("ATA W01D Standings (Including World-only Competitors)")

sel = st.selectbox("Region", REGIONS)
go = st.button("Go")

if go:
    raw = gather_data(sel)
    data = dedupe_and_rank(raw)
    found_any = False
    for ev in EVENT_NAMES:
        rows = data.get(ev, [])
        if rows:
            found_any = True
            df = pd.DataFrame(rows)[["Rank", "Name", "Points", "Location"]]
            st.subheader(ev)
            st.dataframe(df, use_container_width=True)
    if not found_any:
        st.warning("No standings found for your selection.")

Else= st.info("Select region and press Go to view standings.")
