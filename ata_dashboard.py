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
    all
