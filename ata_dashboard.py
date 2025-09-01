import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- Tournament Breakdown Sheet Setup ---
SHEET_ID = "1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg"
SHEET_NAME = "Sheet1"
sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
try:
    tourney_df = pd.read_csv(sheet_url)
except Exception:
    tourney_df = pd.DataFrame()

# --- Scraping Constants ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    # US states
    "Florida": ("US", "FL"), "Georgia": ("US", "GA"),
    # ... include all your previously defined states/provinces ...
}

REGIONS = ["All"] + list(REGION_CODES.keys()) + ["International"]

STATE_URL = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={}&state={}&code=W01D"
WORLDS_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

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
    ev_data = {ev: [] for ev in EVENT_NAMES}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        ev_tag = header.find("span", class_="text-primary text-uppercase")
        if not ev_tag:
            continue
        ev = ev_tag.get_text(strip=True)
        if ev not in EVENT_NAMES:
            continue
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) == 4 and all(cols):
                rank, name, pts, loc = cols
                try:
                    pts = int(pts)
                except:
                    continue
                if pts > 0:
                    ev_data[ev].append({
                        "Rank": int(rank),
                        "Name": name.title(),
                        "Points": pts,
                        "Location": loc
                    })
    return ev_data

def gather_data(selection):
    combined = {ev: [] for ev in EVENT_NAMES}

    # Include World standings always
    whtml = fetch_html(WORLDS_URL)
    if whtml:
        wd = parse_standings(whtml)
        for ev, entries in wd.items():
            for e in entries:
                # Only include if no 2-letter US/CA code at end
                if not re.search(r",\s*[A-Z]{2}$", e["Location"]):
                    combined[ev].append(e)

    if selection in REGION_CODES:
        country, code = REGION_CODES[selection]
        url = STATE_URL.format(country, code)
        html = fetch_html(url)
        if html:
            sd = parse_standings(html)
            for ev, entries in sd.items():
                combined[ev].extend(entries)
            has_data = any(sd.values())
            return combined, has_data
        else:
            return combined, False

    if selection == "All":
        has_data = False
        for region in REGION_CODES:
            country, code = REGION_CODES[region]
            url = STATE_URL.format(country, code)
            html = fetch_html(url)
            if html:
                sd = parse_standings(html)
                for ev, entries in sd.items():
                    combined[ev].extend(entries)
                if any(sd.values()):
                    has_data = True
        return combined, has_data

    if selection == "International":
        has_data = any(combined.values())
        return combined, has_data

    return combined, False

def dedupe_and_rank(ev_data):
    cleaned = {}
    for ev, entries in ev_data.items():
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
        cleaned[ev] = uniq
    return cleaned

st.title("ATA W01D Standings (State + Int'l)")

sel = st.selectbox("Select Region:", REGIONS)
if st.button("Go"):
    raw, has = gather_data(sel)
    data = dedupe_and_rank(raw)
    if not has:
        msg = f"There are no 50-59 1st Degree Women for {sel}."
        st.warning(msg)
    else:
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            if rows:
                st.subheader(ev)
                for row in rows:
                    with st.expander(f"{row['Rank']}. {row['Name']} — {row['Points']} pts"):
                        st.write(f"Location: {row['Location']}")
                        if not tourney_df.empty:
                            personal = tourney_df[tourney_df["Name"].str.upper() == row["Name"].upper()]
                            if not personal.empty:
                                st.write(personal[["Tournament", "Points", "Date", "Location"]])
                            else:
                                st.info("No tournament breakdown available.")
else:
    st.info("Select a region or 'International' and click Go.")

