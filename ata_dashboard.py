import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime

@st.cache_data(ttl=600)
def fetch_standings():
    url = "https://atamartialarts.com/events/tournament-standings/worlds-standings"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')

    if not table:
        return pd.DataFrame()

    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    rows = []
    for row in table.find_all('tr')[1:]:
        cols = [td.get_text(strip=True) for td in row.find_all('td')]
        if cols:
            rows.append(cols)

    return pd.DataFrame(rows, columns=headers)

# Static or future: Tournament info (customize or make dynamic later)
tournament_info = {
    "name": "ATA Worlds 2025",
    "location": "Phoenix, AZ",
    "date": "July 12–15, 2025"
}

# Streamlit app
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")
st.title("🏆 ATA Worlds Standings Dashboard")
st.caption("Live results pulled from ATA Martial Arts")

# Show tournament info
st.subheader("📅 Tournament Information")
st.markdown(f"""
**Name:** {tournament_info['name']}  
**Location:** {tournament_info['location']}  
**Date:** {tournament_info['date']}
""")

# Pull data
with st.spinner("Fetching latest standings..."):
    df = fetch_standings()

if df.empty:
    st.error("Could not load standings.")
else:
    # Optional filters
    col1, col2 = st.columns(2)
    with col1:
        div_filter = st.text_input("🔍 Filter by Division")
    with col2:
        rank_filter = st.text_input("🥋 Filter by Rank/Name")

    filtered = df.copy()
    if div_filter:
        filtered = filtered[filtered.apply(lambda row: div_filter.lower() in row.astype(str).str.lower().to_string(), axis=1)]
    if rank_filter:
        filtered = filtered[filtered.apply(lambda row: rank_filter.lower() in row.astype(str).str.lower().to_string(), axis=1)]

    st.dataframe(filtered, use_container_width=True)

    st.caption(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.button("🔁 Refresh", on_click=fetch_standings.clear)


