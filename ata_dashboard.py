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
        event = cols[col_idx.get('Event', 2)].get_text(strip=True)
        points_str = cols[col_idx.get('Pts', 3)].get_text(strip=True)
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

    events = sorted(df['Event'].unique())

    st.write(f"Displaying {len(df)} competitors with points for {region} — separated by event")

    for event in events:
        st.subheader(event)
        event_df = df[df['Event'] == event].sort_values(by="Rank")
        st.dataframe(event_df, use_container_width=True)


if __name__ == "__main__":
    main()
