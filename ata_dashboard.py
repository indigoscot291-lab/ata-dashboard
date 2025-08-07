import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from functools import lru_cache

BASE_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/w01d-"
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    "Alabama": "al", "Alaska": "ak", "Arizona": "az", "Arkansas": "ar", "California": "ca",
    "Colorado": "co", "Connecticut": "ct", "Delaware": "de", "Florida": "fl", "Georgia": "ga",
    "Hawaii": "hi", "Idaho": "id", "Illinois": "il", "Indiana": "in", "Iowa": "ia", "Kansas": "ks",
    "Kentucky": "ky", "Louisiana": "la", "Maine": "me", "Maryland": "md", "Massachusetts": "ma",
    "Michigan": "mi", "Minnesota": "mn", "Mississippi": "ms", "Missouri": "mo", "Montana": "mt",
    "Nebraska": "ne", "Nevada": "nv", "New Hampshire": "nh", "New Jersey": "nj", "New Mexico": "nm",
    "New York": "ny", "North Carolina": "nc", "North Dakota": "nd", "Ohio": "oh", "Oklahoma": "ok",
    "Oregon": "or", "Pennsylvania": "pa", "Rhode Island": "ri", "South Carolina": "sc",
    "South Dakota": "sd", "Tennessee": "tn", "Texas": "tx", "Utah": "ut", "Vermont": "vt",
    "Virginia": "va", "Washington": "wa", "West Virginia": "wv", "Wisconsin": "wi", "Wyoming": "wy",
    "Alberta": "ab", "British Columbia": "bc", "Manitoba": "mb", "New Brunswick": "nb",
    "Newfoundland and Labrador": "nl", "Nova Scotia": "ns", "Ontario": "on", "Prince Edward Island": "pe",
    "Quebec": "qc", "Saskatchewan": "sk"
}

REGIONS = list(REGION_CODES.keys())
REGIONS.insert(0, "All")

@st.cache_data(show_spinner=False)
def fetch_region_html(region_code):
    url = f"{BASE_URL}{region_code}/"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except:
        pass
    return None

def parse_standings(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    event_data = {}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        event_name_tag = header.find("span", class_="text-primary text-uppercase")
        if not event_name_tag:
            continue
        event_name = event_name_tag.get_text(strip=True)
        if event_name not in EVENT_NAMES:
            continue
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) == 4 and all(cols):
                place, name, points, location = cols
                try:
                    points = int(points)
                except:
                    points = 0
                if points > 0:
                    rows.append({
                        "Rank": int(place),
                        "Name": name.title(),
                        "Points": points,
                        "Location": location.title()
                    })
        if rows:
            event_data.setdefault(event_name, []).extend(rows)
    return event_data

def gather_data_for_regions(regions):
    all_event_data = {event: [] for event in EVENT_NAMES}
    for region in regions:
        region_code = REGION_CODES[region]
        html = fetch_region_html(region_code)
        if not html:
            continue
        event_data = parse_standings(html)
        for event, entries in event_data.items():
            all_event_data[event].extend(entries)
    return all_event_data

def dedupe_and_sort(event_data):
    cleaned_data = {}
    for event, entries in event_data.items():
        seen = set()
        unique_entries = []
        for e in entries:
            key = (e["Name"], e["Location"])
            if key not in seen:
                seen.add(key)
                unique_entries.append(e)
        unique_entries.sort(key=lambda x: x["Points"], reverse=True)
        for idx, e in enumerate(unique_entries, 1):
            e["Rank"] = idx
        cleaned_data[event] = unique_entries
    return cleaned_data

st.title("ATA 1st Degree Women 50-59 Standings")
selected_region = st.selectbox("Select State or Province", REGIONS)
go = st.button("Go")

if go:
    if selected_region == "All":
        regions = list(REGION_CODES.keys())
    else:
        regions = [selected_region]

    with st.spinner("Fetching data..."):
        raw_data = gather_data_for_regions(regions)
        data = dedupe_and_sort(raw_data)

    any_data = any(len(lst) > 0 for lst in data.values())
    if not any_data:
        st.warning("No results found for the selected region(s).")
    else:
        for event in EVENT_NAMES:
            entries = data.get(event, [])
            if entries:
                df = pd.DataFrame(entries)[["Rank", "Name", "Points", "Location"]]
                st.subheader(event)
                st.dataframe(df, use_container_width=True)
