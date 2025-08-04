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

EVENT_ORDER = [
    "Forms",
    "Weapons",
    "Combat Weapons",
    "Sparring",
    "Creative Forms",
    "Creative Weapons",
    "X-Treme Forms",
    "X-Treme Weapons"
]

@st.cache_data(ttl=600)
def scrape_state_data(state_code, country="US"):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={DIVISION_CODE}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Request error: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, 'html.parser')

    data = []

    # Find all event headers (h2 or h3) that match our event names
    event_headers = soup.find_all(['h2', 'h3'])

    for header in event_headers:
        event_name = header.get_text(strip=True)
        if event_name not in EVENT_ORDER:
            continue

        # Find the next table sibling (skip non-table elements)
        next_sibling = header.next_sibling
        while next_sibling and next_sibling.name != 'table':
            next_sibling = next_sibling.next_sibling

        table = next_sibling
        if table is None:
            continue

        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        col_idx = {col: i for i, col in enumerate(headers)}

        if 'Name' not in col_idx or 'Pts' not in col_idx:
            continue

        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) < len(headers):
                continue

            name = cols[col_idx['Name']].get_text(strip=True)
            points_str = cols[col_idx['Pts']].get_text(strip=True)
            points = int(points_str) if points_str.isdigit() else 0

            if points > 0:
                data.append({
                    "Name": name,
                    "Event": event_name,
                    "Points": points,
                    "State/Province": state_code,
                    "Country": country
                })

    df = pd.DataFrame(data)
    if df.empty:
        return df

    df['Rank'] = df.groupby('Event')['Points'] \
                   .rank(method='first', ascending=False).astype(int)

    df = df[['Rank', 'Name', 'Points', 'State/Province', 'Country', 'Event']]

    return df


def main():
    st.title("ATA Standings – Women 50–59, 1st Degree Black Belt")

    region = st.selectbox("Select State or Province", options=ALL_REGIONS)
    country = "CA" if region in CA_PROVINCES else "US"

    df = scrape_state_data(region, country)

    if df.empty:
        st.warning("No data found for this region.")
        return

    name_filter = st.text_input("Filter by Competitor Name (optional)").strip().lower()
    if name_filter:
        df = df[df['Name'].str.lower().str.contains(name_filter)]

    events_in_data = df['Event'].unique()
    events_ordered = [e for e in EVENT_ORDER if e in events_in_data]

    st.write(f"Displaying {len(df)} competitors with points for {region} — separated by event")

    for event in events_ordered:
        st.subheader(event)
        event_df = df[df['Event'] == event].sort_values(by="Rank")
        st.dataframe(event_df, use_container_width=True)


if __name__ == "__main__":
    main()
