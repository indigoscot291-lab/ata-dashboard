import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Event keyword mapping
EVENT_KEYWORDS = {
    "Forms": "Forms",
    "Weapons": "Weapons",
    "Combat": "Combat Weapons",
    "Sparring": "Sparring",
    "Creative Forms": "Creative Forms",
    "Creative Weapons": "Creative Weapons",
    "X-Treme Forms": "X-Treme Forms",
    "X-Treme Weapons": "X-Treme Weapons",
}

# US states + Canadian provinces
REGIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"
]

# Detect event name from nearby text
def get_event_name_from_text(text):
    for keyword, event in EVENT_KEYWORDS.items():
        if keyword.lower() in text.lower():
            return event
    return None

# Scrape data for one state
@st.cache_data(show_spinner=False)
def scrape_state_data(state_code, division_code="W01D", country="US"):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={division_code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        st.warning(f"Error fetching data for {state_code}: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    data = []

    # Find event headers and matching tables
    for li in soup.find_all("li"):
        li_text = li.get_text(strip=True)
        event_name = get_event_name_from_text(li_text)
        if not event_name:
            continue

        table = li.find_next("table")
        if not table:
            continue

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        col_idx = {key: i for i, key in enumerate(headers)}

        if "Name" not in col_idx or "Pts" not in col_idx:
            continue

        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < len(headers):
                continue

            name = cols[col_idx["Name"]].get_text(strip=True)
            pts_text = cols[col_idx["Pts"]].get_text(strip=True).replace(",", "")
            try:
                points = float(pts_text)
            except ValueError:
                continue

            if points > 0:
                data.append({
                    "Name": name,
                    "Event": event_name,
                    "Points": points,
                    "State/Province": state_code,
                    "Country": country
                })

    df = pd.DataFrame(data)
    if not df.empty:
        df['Rank'] = df.groupby('Event')['Points'].rank(method='first', ascending=False).astype(int)
        df = df[['Rank', 'Name', 'Points', 'State/Province', 'Country', 'Event']]

    return df

# Streamlit UI
st.title("ATA Martial Arts Standings (Women 50–59, 1st Degree)")

selected_state = st.selectbox("Select a State or Province", REGIONS)
selected_event = st.selectbox("Select an Event (or view all)", ["All"] + list(EVENT_KEYWORDS.values()))
name_filter = st.text_input("Filter by Competitor Name (optional)").lower()

df = scrape_state_data(selected_state)

if df.empty:
    st.info("No results found for this region.")
else:
    if name_filter:
        df = df[df["Name"].str.lower().str.contains(name_filter)]

    if selected_event != "All":
        df = df[df["Event"] == selected_event]

    # Display each event in its own table
    for event in df["Event"].unique():
        event_df = df[df["Event"] == event].sort_values("Rank")
        st.subheader(f"{event}")
        st.dataframe(event_df.reset_index(drop=True), use_container_width=True)
