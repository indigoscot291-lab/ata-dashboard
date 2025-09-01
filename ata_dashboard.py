import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# -------------------------------
# CONFIG
# -------------------------------
BASE_URL = "https://atamartialarts.com/events/tournament-standings/"
CODES = {
    "All": None,
    "Worlds": "W01D",
    "AL": "S01D", "FL": "S10D", "GA": "S11D",
    "ON": "C01D", "QC": "C02D"
    # ⚠️ Add all the other state/province codes here
}

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/gviz/tq?tqx=out:csv&gid=0"

# -------------------------------
# HELPERS
# -------------------------------

@st.cache_data
def load_tournament_data():
    return pd.read_csv(GOOGLE_SHEET_URL)

tournament_df = load_tournament_data()

def fetch_standings(code):
    """Fetch and parse standings for a given state/province/world code"""
    if not code:
        return None

    url = f"{BASE_URL}?code={code}"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    # Find all headers with event info
    headers = soup.find_all("ul", class_="tournament-header")
    for header in headers:
        event_name = " | ".join([li.get_text(strip=True) for li in header.find_all("li")])

        # Find the following standings table
        table = header.find_next("table")
        if not table:
            continue

        for row in table.find("tbody").find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if len(cols) >= 4:
                results.append({
                    "Event": event_name,
                    "Rank": cols[0],
                    "Name": cols[1],
                    "Points": int(cols[2]),
                    "Location": cols[3]
                })

    return pd.DataFrame(results)

def is_international(location):
    """Check if location is not just a US/Canadian state abbreviation"""
    match = re.search(r",\s*([A-Z]{2})$", location)
    return match is None

# -------------------------------
# STREAMLIT UI
# -------------------------------
st.title("ATA Tournament Standings")

region = st.selectbox("Select Region", list(CODES.keys()))
go = st.button("Go")

if go:
    all_results = []

    if region == "All":
        for r, code in CODES.items():
            if code:
                df = fetch_standings(code)
                if df is not None and not df.empty:
                    df["Region"] = r
                    all_results.append(df)
    else:
        df = fetch_standings(CODES[region])
        if df is not None and not df.empty:
            df["Region"] = region
            all_results.append(df)

    # Add international competitors from Worlds
    if region in ["All", "Worlds"]:
        world_df = fetch_standings(CODES["Worlds"])
        if world_df is not None and not world_df.empty:
            intl_df = world_df[world_df["Location"].apply(is_international)]
            if not intl_df.empty:
                intl_df["Region"] = "International"
                all_results.append(intl_df)

    if not all_results:
        st.warning(f"There are no 50-59 1st Degree Women for {region}")
    else:
        full_df = pd.concat(all_results, ignore_index=True)

        # Sort by Event then Points descending
        full_df = full_df.sort_values(["Event", "Points"], ascending=[True, False])

        # Re-rank within each event
        full_df["Rank"] = full_df.groupby("Event")["Points"].rank(method="dense", ascending=False).astype(int)

        # Display event by event
        for event, group in full_df.groupby("Event"):
            st.subheader(event)

            # Show standings with clickable names
            for _, row in group.iterrows():
                cols = st.columns([1, 3, 1, 2])
                cols[0].write(row["Ra]()
