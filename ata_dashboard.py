import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

@st.cache_data(ttl=600)
def scrape_state_standings(state_code, event_code, country="US"):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={event_code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table')
    if not table:
        return pd.DataFrame()

    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    rows = []
    for tr in table.find_all('tr')[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all('td')]
        if cols:
            rows.append(cols)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=headers)
    df['State/Province'] = state_code
    df['Country'] = country
    return df

@st.cache_data(ttl=600)
def load_all_data(us_states, ca_provinces, event_code):
    all_dfs = []

    for state in us_states:
        df = scrape_state_standings(state, event_code, country="US")
        if not df.empty:
            all_dfs.append(df)

    for province in ca_provinces:
        df = scrape_state_standings(province, event_code, country="CA")
        if not df.empty:
            all_dfs.append(df)

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    else:
        return pd.DataFrame()

def main():
    st.title("ATA Standings: 1st Degree Black Belt Women 50–59")
    st.caption("Live results from all U.S. states and Canadian provinces")

    us_states = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    ]

    ca_provinces = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT']

    event_code = st.text_input("Enter Event Code", value="W01D", help="E.g., W01D = Women 1st Degree 50–59")

    if st.button("Fetch Standings"):
        with st.spinner("Scraping ATA website..."):
            df = load_all_data(us_states, ca_provinces, event_code)

        if df.empty:
            st.error("No results found.")
            return

        st.success(f"✅ {len(df)} competitors found")

        # Filters
        state_filter = st.multiselect("Filter by State/Province", options=sorted(df['State/Province'].unique()), default=sorted(df['State/Province'].unique()))
        search = st.text_input("Search Name, Rank, Division (optional)").strip().lower()

        filtered_df = df[df['State/Province'].isin(state_filter)]

        if search:
            filtered_df = filtered_df[filtered_df.apply(lambda row: search in row.astype(str).str.lower().to_string(), axis=1)]

        st.dataframe(filtered_df, use_container_width=True)

if __name__ == "__main__":
    main()
