import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

DIVISION_CODE = "W01D"
STATE_CODE = "FL"
COUNTRY_CODE = "US"

def scrape_florida_standings():
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={COUNTRY_CODE}&state={STATE_CODE}&code={DIVISION_CODE}"
    st.write(f"Fetching URL: {url}")
    resp = requests.get(url)
    if resp.status_code != 200:
        st.error(f"Failed to fetch page: status code {resp.status_code}")
        return pd.DataFrame(), ["Failed to fetch page"]

    soup = BeautifulSoup(resp.text, "html.parser")
    debug_logs = []
    results = []

    for ul in soup.find_all("ul", class_="tournament-header"):
        li_span = ul.find("li").find("span", class_="text-primary text-uppercase")
        if not li_span:
            continue
        event_name = li_span.get_text(strip=True)
        debug_logs.append(f"Found event: {event_name}")

        next_div = ul.find_next_sibling("div", class_="table-responsive")
        if not next_div:
            debug_logs.append(f"No table container found for event {event_name}")
            continue

        table = next_div.find("table")
        if not table:
            debug_logs.append(f"No table found inside div for event {event_name}")
            continue

        for tr in table.tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            place = tds[0].get_text(strip=True)
            name = tds[1].get_text(strip=True)
            points = tds[2].get_text(strip=True)
            location = tds[3].get_text(strip=True)
            try:
                points_val = float(points.replace(",", ""))
            except:
                points_val = 0

            if points_val > 0:
                results.append({
                    "Event": event_name,
                    "Place": place,
                    "Name": name,
                    "Points": points_val,
                    "Location": location,
                })
                debug_logs.append(f" - Competitor: {name}, Points: {points_val}")

    df = pd.DataFrame(results)
    return df, debug_logs

st.title("Florida ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

if st.button("Fetch Florida Standings"):
    df, logs = scrape_florida_standings()

    st.subheader("Debug Logs")
    for log in logs:
        st.text(log)

    if df.empty:
        st.info("No competitors with points found.")
    else:
        st.subheader("Competitor Standings")
        for event in sorted(df["Event"].unique()):
            st.markdown(f"### {event}")
            event_df = df[df["Event"] == event].sort_values(by="Points", ascending=False).reset_index(drop=True)
            event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
            st.dataframe(event_df[["Rank", "Place", "Name", "Points", "Location"]])
