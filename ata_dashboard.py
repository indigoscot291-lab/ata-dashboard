import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

DIVISION_CODE = "W01D"

US_STATES = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS',
    'KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY',
    'NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'
]

CA_PROVINCES = ['AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT']

ALL_REGIONS = US_STATES + CA_PROVINCES

@st.cache_data(ttl=600)
def scrape_state_data(state_code, country="US"):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={DIVISION_CODE}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, 'html.parser')

    tables = soup.find_all('table')
    table = None
    for t in tables:
        headers = [th.get_text(strip=True) for th in t.find_all('th')]
        if 'Name' in headers and 'Pts' in headers:
            table = t
            break
    if table is None:
        return pd.DataFrame()

    data = []
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    col_idx = {col: i for i, col in enumerate(headers)}

    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if not cols or len(cols) < 4:
            continue
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


def main():
    st.title("ATA Standings – Women 50–59, 1st Degree Black Belt")

    region = st.selectbox("Select State or Province", options=ALL_REGIONS)
    country = "CA" if region in CA_PROVINCES else "US"

    if st.button("Fetch Results"):
        with st.spinner(f"Fetching results for {region}..."):
            df = scrape_state_data(region, country)

        if df.empty:
            st.warning("No data found for this region.")
            return

        events = sorted(df['Event'].unique())
        selected_event = st.selectbox("Select Event", options=["All Events"] + events)

        if selected_event != "All Events":
            df = df[df['Event'] == selected_event]

        name_filter = st.text_input("Filter by Competitor Name (optional)").strip().lower()
        if name_filter:
            df = df[df['Name'].str.lower().str.contains(name_filter)]

        st.write(f"Displaying {len(df)} results for {region} - {selected_event}")
        st.dataframe(df.sort_values(by="Points", ascending=False), use_container_width=True)


if __name__ == "__main__":
    main()
