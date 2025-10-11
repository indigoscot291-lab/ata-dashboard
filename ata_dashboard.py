import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# =========================================
# PAGE CONFIG
# =========================================
st.set_page_config(page_title="ATA Tournament Dashboard", layout="wide")

# =========================================
# GLOBALS
# =========================================
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGION_CODES = {
    "Alabama": ("US", "AL"), "Alaska": ("US", "AK"), "Arizona": ("US", "AZ"),
    "Arkansas": ("US", "AR"), "California": ("US", "CA"), "Colorado": ("US", "CO"),
    "Connecticut": ("US", "CT"), "Delaware": ("US", "DE"), "Florida": ("US", "FL"),
    "Georgia": ("US", "GA"), "Hawaii": ("US", "HI"), "Idaho": ("US", "ID"),
    "Illinois": ("US", "IL"), "Indiana": ("US", "IN"), "Iowa": ("US", "IA"),
    "Kansas": ("US", "KS"), "Kentucky": ("US", "KY"), "Louisiana": ("US", "LA"),
    "Maine": ("US", "ME"), "Maryland": ("US", "MD"), "Massachusetts": ("US", "MA"),
    "Michigan": ("US", "MI"), "Minnesota": ("US", "MN"), "Mississippi": ("US", "MS"),
    "Missouri": ("US", "MO"), "Montana": ("US", "MT"), "Nebraska": ("US", "NE"),
    "Nevada": ("US", "NV"), "New Hampshire": ("US", "NH"), "New Jersey": ("US", "NJ"),
    "New Mexico": ("US", "NM"), "New York": ("US", "NY"), "North Carolina": ("US", "NC"),
    "North Dakota": ("US", "ND"), "Ohio": ("US", "OH"), "Oklahoma": ("US", "OK"),
    "Oregon": ("US", "OR"), "Pennsylvania": ("US", "PA"), "Rhode Island": ("US", "RI"),
    "South Carolina": ("US", "SC"), "South Dakota": ("US", "SD"), "Tennessee": ("US", "TN"),
    "Texas": ("US", "TX"), "Utah": ("US", "UT"), "Vermont": ("US", "VT"),
    "Virginia": ("US", "VA"), "Washington": ("US", "WA"), "West Virginia": ("US", "WV"),
    "Wisconsin": ("US", "WI"), "Wyoming": ("US", "WY")
}

DISTRICT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1SJqPP3N7n4yyM8_heKe7Amv7u8mZw-T5RKN4OmBOi4I/export?format=csv"
RINGS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1grZSp3fr3lZy4ScG8EqbvFCkNJm_jK3KjNhh2BXJm9A/export?format=csv"

# =========================================
# CACHE FUNCTIONS
# =========================================
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
def load_csv(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception:
        return pd.DataFrame()

# =========================================
# PARSE STANDINGS
# =========================================
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
            if len(cols) == 4:
                rank_s, name, pts_s, loc = cols
                try:
                    pts = int(pts_s)
                except:
                    continue
                data[ev_name].append({"Rank": int(rank_s), "Name": name, "Points": pts, "Location": loc})
    return data

def rank_within(df, column="Points"):
    df = df.sort_values(by=column, ascending=False).copy()
    df["Rank"] = df[column].rank(method="min", ascending=False).astype(int)
    return df

# =========================================
# MAIN NAV
# =========================================
page_choice = st.selectbox(
    "Select a page:",
    [
        "ATA Standings Dashboard",
        "1st Degree Black Belt Women 50-59",
        "National & District Tournament Rings"
    ]
)

# =========================================
# PAGE 1: ATA Standings Dashboard
# =========================================
if page_choice == "ATA Standings Dashboard":
    st.title("ATA Standings Dashboard")
    st.caption("World, Regional, and District Standings")

    code = "W01D"
    world_url = f"https://atamartialarts.com/events/tournament-standings/worlds-standings/?code={code}"
    html = fetch_html(world_url)
    if html:
        data = parse_standings(html)
        for event, rows in data.items():
            st.subheader(f"{event} – World Standings")
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.error("Unable to fetch world standings.")

# =========================================
# PAGE 2: 1st Degree Black Belt Women 50-59
# =========================================
elif page_choice == "1st Degree Black Belt Women 50-59":
    st.title("1st Degree Black Belt Women 50-59 Standings")

    region_choice = st.selectbox("Select Region or State:", ["World"] + list(REGION_CODES.keys()))
    district_df = load_csv(DISTRICT_SHEET_URL)

    if region_choice == "World":
        url = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"
        html = fetch_html(url)
        if html:
            data = parse_standings(html)
            for event, rows in data.items():
                df = pd.DataFrame(rows)
                st.subheader(f"{event} — World Rank")
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error("Unable to load world standings.")
    else:
        country, state_code = REGION_CODES[region_choice]
        url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code=W01D"
        html = fetch_html(url)
        if html:
            data = parse_standings(html)
            for event, rows in data.items():
                df = pd.DataFrame(rows)
                df = rank_within(df)
                st.subheader(f"{event} — {region_choice} Rank")
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error(f"Unable to load data for {region_choice}.")

# =========================================
# PAGE 3: NATIONAL & DISTRICT TOURNAMENT RINGS
# =========================================
elif page_choice == "National & District Tournament Rings":
    st.title("🏅 National & District Tournament Rings")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.success("Ring data refreshed successfully!")

    df_rings = load_csv(RINGS_SHEET_URL)
    if df_rings.empty:
        st.error("Unable to load data from the rings Google Sheet.")
    else:
        search_type = st.radio("Search by:", ["Name", "Division Assigned"])

        if search_type == "Name":
            last_name = st.text_input("Enter Last Name (or part):").strip().lower()
            first_name = st.text_input("Enter First Name (optional):").strip().lower()
            if st.button("Search"):
                results = df_rings[
                    df_rings["Last Name"].str.lower().str.contains(last_name, na=False)
                ]
                if first_name:
                    results = results[
                        results["First Name"].str.lower().str.contains(first_name, na=False)
                    ]
                if results.empty:
                    st.warning("No matches found.")
                else:
                    cols = [
                        "Last Name", "First Name", "ATA Number", "Division Assigned",
                        "Traditional Forms", "Traditional Weapons", "Combat Weapons",
                        "Traditional Sparring", "Competition Day", "Ring Number", "Time"
                    ]
                    cols = [c for c in cols if c in results.columns]
                    st.dataframe(results[cols], use_container_width=True, hide_index=True)

        elif search_type == "Division Assigned":
            divisions = sorted(df_rings["Division Assigned"].dropna().unique())
            division_choice = st.selectbox("Select Division:", [""] + divisions)
            if st.button("Search"):
                if division_choice:
                    results = df_rings[df_rings["Division Assigned"] == division_choice]
                    if results.empty:
                        st.warning("No competitors found for that division.")
                    else:
                        cols = [
                            "Last Name", "First Name", "ATA Number", "Division Assigned",
                            "Traditional Forms", "Traditional Weapons", "Combat Weapons",
                            "Traditional Sparring", "Competition Day", "Ring Number", "Time"
                        ]
                        cols = [c for c in cols if c in results.columns]
                        st.dataframe(results[cols], use_container_width=True, hide_index=True)
                else:
                    st.info("Please select a division first.")
