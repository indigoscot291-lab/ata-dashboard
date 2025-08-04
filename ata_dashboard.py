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
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Find the main table with 'Name' and 'Pts' headers
    tables = soup.find_all('table')
    table = None
    for t in tables:
        headers = [th.get_text(strip=True) for th in t.find_all('th')]
        if 'Name' in headers and 'Pts' in headers and 'Event' in headers:
            table = t
            break
    if table is None:
        return pd.DataFrame()

    data = []
    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    col_idx = {col: i for i, col in enumerate(headers)}

    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if not cols or len(cols) < len(headers):
            continue
        name = cols[col_idx.get('Name')].get_text(strip=True)
        event = cols[col_idx.get('Event')].get_text(strip=True)
        points_str = cols[col_idx.get('Pts')].get_text(strip=True)
        points = int(points_str) if points_str.isdigit() else 0

        if points > 0:
            data.append({
                "Name": name,
                "Event": event,
                "Points": points,
                "State/Province": state_code,
                "Country": country
            })

    df = pd.DataFrame(data)
    if df.empty:
        return df

    # Rank within each event by points descending
    df['Rank'] = df.groupby('Event')['Points'] \
                   .rank(method='first', ascending=False).astype(int)

    # Reorder columns
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

    # Only show events in fixed order and present in data
    events_in_data = df['Event'].unique()
    events_ordered = [e for e in EVENT_ORDER if e in events_in_data]

    st.write(f"Displaying {len(df)} competitors with points for {region} — separated by event")

    for event in events_ordered:
        st.subheader(event)
        event_df = df[df['Event'] == event].sort_values(by="Rank")
        st.dataframe(event_df, use_container_width=True)


if __name__ == "__main__":
    main()
