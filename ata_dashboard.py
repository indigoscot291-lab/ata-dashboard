import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

DIVISION_CODE = "W01D"
STATE_CODE = "FL"
COUNTRY_CODE = "US"

def scrape_florida_standings():
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={COUNTRY_CODE}&state={STATE_CODE}&code={DIVISION_CODE}"
    st.write(f"Fetching URL: {url}")
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Failed to fetch page: status code {resp.status_code}")
        return pd.DataFrame(), []

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.find("div", class_="tab-content")
    if not content_div:
        st.error("Could not find main standings container (div.tab-content).")
        return pd.DataFrame(), []

    all_results = []
    debug_logs = []

    for li in content_div.find_all("li"):
        span = li.find("span", class_="text-primary text-uppercase")
        if span:
            event_name = span.get_text(strip=True)
            debug_logs.append(f"\nFound event: '{event_name}'")

            # Find the next table sibling after this li
            table = None
            for sibling in li.next_siblings:
                if hasattr(sibling, "name") and sibling.name == "table":
                    table = sibling
                    break

            if not table:
                debug_logs.append(f"No table found after event '{event_name}'")
                continue

            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            debug_logs.append(f"Table headers: {headers}")

            if "Name" not in headers or not any(k in headers for k in ("Pts", "Points", "PTS")):
                debug_logs.append(f"Table for event '{event_name}' missing required columns.")
                continue

            idx = {h: i for i, h in enumerate(headers)}
            pts_key = next((k for k in ("Pts", "Points", "PTS") if k in idx), None)

            for tr in table.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) <= max(idx["Name"], idx[pts_key]):
                    continue
                name = tds[idx["Name"]].get_text(strip=True)
                raw_points = tds[idx[pts_key]].get_text(strip=True)
                m = re.search(r"[\d,.]+", raw_points)
                if m:
                    points = float(m.group(0).replace(",", ""))
                    if points > 0:
                        all_results.append({
                            "Event": event_name,
                            "Name": name,
                            "Points": points
                        })
                        debug_logs.append(f" - Competitor: {name}, Points: {points}")
                else:
                    debug_logs.append(f"Could not parse points for competitor '{name}' in event '{event_name}': '{raw_points}'")

    if not all_results:
        st.info("No competitors with points found.")
        return pd.DataFrame(), debug_logs

    df = pd.DataFrame(all_results)
    return df, debug_logs

st.title("Florida ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

if st.button("Fetch Florida Standings"):
    df, logs = scrape_florida_standings()

    st.subheader("Debug Logs")
    for log in logs:
        st.text(log)

    if not df.empty:
        st.subheader("Competitor Standings")
        for event in sorted(df["Event"].unique(), key=lambda e: e):
            st.markdown(f"### {event}")
            event_df = df[df["Event"] == event].sort_values(by="Points", ascending=False).reset_index(drop=True)
            event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
            st.dataframe(event_df[["Rank", "Name", "Points"]])
