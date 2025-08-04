import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_state_standings(state_code, event_code):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country=US&state={state_code}&code={event_code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()  # Raise error for bad HTTP status
    except requests.RequestException as e:
        print(f"Skipping {state_code}: Request failed ({e})")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table')
    if not table:
        print(f"Skipping {state_code}: No standings table found.")
        return pd.DataFrame()

    headers = [th.get_text(strip=True) for th in table.find_all('th')]
    rows = []
    for tr in table.find_all('tr')[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all('td')]
        if cols:
            rows.append(cols)

    if not rows:
        print(f"Skipping {state_code}: Standings table is empty.")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=headers)
    df['State'] = state_code
    return df

def main():
    # List of states to scrape
    states = [
        'WA', 'CA', 'NY', 'TX', 'FL', 'IL', 'PA', 'OH', 'MI', 'GA',
        # add more states as needed
    ]
    event_code = 'W01D'  # Change to your event code

    all_dfs = []
    skipped_states = []

    for state in states:
        print(f"Scraping state: {state}")
        df_state = scrape_state_standings(state, event_code)
        if df_state.empty:
            skipped_states.append(state)
        else:
            all_dfs.append(df_state)

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        print(f"\nScraped data from {len(states) - len(skipped_states)} states successfully.")
        print(f"Skipped states (no data or errors): {', '.join(skipped_states)}")
        combined_df.to_csv('ata_women_1st_degree_50_59_all_states.csv', index=False)
        print(f"\nSample data:\n{combined_df.head()}")
    else:
        print("No data scraped from any state.")

if __name__ == "__main__":
    main()
