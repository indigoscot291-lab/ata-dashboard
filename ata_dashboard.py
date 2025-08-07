import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

# Map of regions to (country, state/province code)
REGION_CODES = {
    # US States (country=US)
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
    # Canadian Provinces (country=CA)
    "Alberta": ("CA", "AB"), "British Columbia": ("CA", "BC"), "Manitoba": ("CA", "MB"),
    "New Brunswick": ("CA", "NB"), "Newfoundland and Labrador": ("CA", "NL"), "Nova Scotia": ("CA", "NS"),
    "Ontario": ("CA", "ON"), "Prince Edward Island": ("CA", "PE"), "Quebec": ("CA", "QC"),
    "Saskatchewan": ("CA", "SK"),
}

REGIONS = list(REGION_CODES.keys())
REGIONS.insert(0, "All")

def build_url(country_code, state_code):
    return f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country_code}&state={state_code}&code=W01D"

@st.cache_data(show_spinner=False)
def fetch_region_html(country_code, state_code):
    url = build_url(country_code, state_code)
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except:
        pass
    return None

def parse_standings(html):
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
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
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
        country_code, state_code = REGION_CODES[region]
        html = fetch_region_html(country_code, state_code)
        if not html:
            continue
        event_data = parse_standings(html)
        if not event_data:
            continue
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
