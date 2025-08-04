import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Caches scrape results for performance
@st.cache_data(ttl=600)
def scrape_state_division(state_code, country="US"):
    code = "W01D"  # Division: Women 1st Degree, age 50–59
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={code}"
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
        if cols and len(cols) == len(headers):
            rows.append(cols)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=headers)
    df['State/Province'] = state_code
    df['Country'] = country
    return df

# Combine results from all states and provinces
@st.cache_data(ttl=600)
def load_all_division_data(us_states, ca_provinces):
    all_dfs = []

    for state in us_states:
        df = scrape_state_division(state, "US")
        if not df.empty:
            all_dfs.append(df)

    for province in ca_provinces:
        df = scrape_state_division(province, "CA")
        if not df.empty:
            all_dfs.append(df)

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    else:
        return pd.DataFrame()

# Streamlit UI
def main():
    st.title("ATA World Standings: Women 50–59, 1st Degree Black Belt")
    st.caption("All events • All U.S. states and Canadian provinces")

    us_states = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    ]
    ca_provinces = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT']

    if st.button("Fetch All Results"):
        with st.spinner("Scraping ATA results... please wait..."):
            df = load_all_division_data(us_states, ca_provinces)

        if df.empty:
            st.error("No results found.")
            return

        st.success(f"Loaded {len(df)} results.")

        # Filters
        states = sorted(df['State/Province'].unique())
        divisions = sorted(df['Division'].unique()) if 'Division' in df.columns else []
        events = sorted(df['Event'].unique()) if 'Event' in df.columns else []

        state_filter = st.multiselect("Filter by State/Province", states, default=states)
        event_filter = st.multiselect("Filter by Event (Optional)", events) if 'Event' in df.columns else []
        search = st.text_input("Search by Name or Division").strip().lower()

        filtered_df = df[df['State/Province'].isin(state_filter)]

        if event_filter and 'Event' in df.columns:
            filtered_df = filtered_df[filtered_df['Event'].isin(event_filter)]

        if search:
            filtered_df = filtered_df[filtered_df.apply(lambda row: search in row.astype(str).str.lower().to_string(), axis=1)]

        st.dataframe(filtered_df, use_container_width=True)

if __name__ == "__main__":
    main()
