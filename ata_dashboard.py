import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

DIVISION_CODE = "W01D"
STATE_CODE = "FL"
COUNTRY_CODE = "US"

def get_florida_standings():
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={COUNTRY_CODE}&state={STATE_CODE}&code={DIVISION_CODE}"
    print(f"Fetching URL: {url}")
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Failed to fetch page: status code {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.find("div", class_="tab-content")
    if not content_div:
        print("Could not find main standings container (div.tab-content).")
        return None

    all_results = []

    # Loop through all <li> items inside content_div
    for li in content_div.find_all("li"):
        span = li.find("span", class_="text-primary text-uppercase")
        if span:
            event_name = span.get_text(strip=True)
            print(f"\nFound event: '{event_name}'")

            # Find the next table sibling after this li
            table = None
            for sibling in li.next_siblings:
                if hasattr(sibling, "name") and sibling.name == "table":
                    table = sibling
                    break

            if not table:
                print(f"No table found after event '{event_name}'")
                continue

            # Parse the table headers
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            print(f"Table headers: {headers}")

            if "Name" not in headers or not any(k in headers for k in ("Pts", "Points", "PTS")):
                print(f"Table for event '{event_name}' missing required columns.")
                continue

            idx = {h: i for i, h in enumerate(headers)}
            pts_key = next((k for k in ("Pts", "Points", "PTS") if k in idx), None)

            # Parse competitor rows
            for tr in table.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) <= max(idx["Name"], idx[pts_key]):
                    continue
                name = tds[idx["Name"]].get_text(strip=True)
                raw_points = tds[idx[pts_key]].get_text(strip=True)
                # Extract numeric part from points string
                m = re.search(r"[\d,.]+", raw_points)
                if m:
                    points = float(m.group(0).replace(",", ""))
                    if points > 0:
                        all_results.append({
                            "Event": event_name,
                            "Name": name,
                            "Points": points
                        })
                        print(f" - Competitor: {name}, Points: {points}")
                else:
                    print(f"Could not parse points for competitor '{name}' in event '{event_name}': '{raw_points}'")

    if not all_results:
        print("No competitors with points found.")
        return None

    df = pd.DataFrame(all_results)
    return df

if __name__ == "__main__":
    df = get_florida_standings()
    if df is not None:
        print("\nAll extracted standings:")
        print(df)
    else:
        print("No data extracted.")
