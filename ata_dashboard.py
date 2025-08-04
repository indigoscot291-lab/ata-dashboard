import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Division code for 1st Degree Women, Age 50–59
DIVISION_CODE = "W01D"

# US states and Canadian provinces
US_STATES = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS',
    'KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY',
    'NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'
]
CA_PROVINCES = ['AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT']

# Grab standings from a single state/province page
@st.cache_data(ttl=3600)
def scrape_state_page(state_code, country="US"):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={DIVISION_CODE}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table')
    if not table:
        return pd.DataFrame()

    data = []
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    col_idx = {col: i for i, col in enumerate(headers)}

    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if not cols or len(cols) < 4:
            continue

        # Extract data
        name = cols[col_idx.get('Name', 0)].get_text(strip=True)
        rank = cols[col_idx.get('Rank', 1)].get_text(strip=True)
        event = cols[col_idx.get('Event', 2)].get_text(strip=True)
        points = cols[col_idx.get('Pts', 3)].get_text(strip=True)

        data.append({
            "Name": name,
            "Rank": rank,
            "Event": event,
            "Points": int(points) if points.isdigit() else 0,
            "State/Province": state_code,
            "Country": country
        })

    return pd.DataFrame(data)

# Load all pages
@st.cache_data(ttl=3600)
def load_all_data():
    all_data = []

    for state in US_STATES:
        df = scrape_state_page(state, "US")
        if not df.empty:
            all_data.append(df)

    for province in CA_PROVINCES:
        df = scrape_state_page(province, "CA")
        if not df.empty:
            all_data.append(df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

# Streamlit UI
def main():
    st.set_page_config(page_title="ATA Standings: W01D", layout="wide")
    st.title("ATA Standings – Women 50–59, 1st Degree Black Belt")
    st.caption("Showing all 8 events from every state and Canadian province")

    if st.button("Fetch Latest Results"):
        with st.spinner("Loading standings from ATA website..."):
            df = load_all_data()

        if df.empty:
            st.error("No results found.")
            return

        # Filters
        states = sorted(df['State/Province'].unique())
        events = sorted(df['Event'].unique())

        selected_states = st.multiselect("Filter by State/Province", states, default=states)
        selected_events = st.multiselect("Filter by Event", events, default=events)
        search_query = st.text_input("Search by Name").strip().lower()

        filtered_df = df[
            df['State/Province'].isin(selected_states) &
            df['Event'].isin(selected_events)
        ]

        if search_query:
            filtered_df = filtered_df[filtered_df['Name'].str.lower().str.contains(search_query)]

        st.write(f"Displaying {len(filtered_df)} results")
        st.dataframe(filtered_df.sort_values(by="Points", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
