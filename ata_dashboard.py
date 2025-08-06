import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

DIVISION_CODE = "W01D"
COUNTRY_CODES = {"US": "United States", "CA": "Canada"}

US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY"
]

CAN_PROVINCES = [
    "AB","BC","MB","NB","NL","NS","ON","PE","QC","SK","NT","NU","YT"
]

REGIONS = [("US", st) for st in US_STATES] + [("CA", pr) for pr in CAN_PROVINCES]

def scrape_region_standings(country_code, state_code):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country_code}&state={state_code}&code={DIVISION_CODE}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return pd.DataFrame(), [f"Failed to fetch {country_code}-{state_code} (status {resp.status_code})"]

    soup = BeautifulSoup(resp.text, "html.parser")
    debug_logs = []
    results = []

    for ul in soup.find_all("ul", class_="tournament-header"):
        li_span = ul.find("li").find("span", class_="text-primary text-uppercase")
        if not li_span:
            continue
        event_name = li_span.get_text(strip=True)
        debug_logs.append(f"[{country_code}-{state_code}] Found event: {event_name}")

        next_div = ul.find_next_sibling("div", class_="table-responsive")
        if not next_div:
            debug_logs.append(f"[{country_code}-{state_code}] No table container for event {event_name}")
            continue

        table = next_div.find("table")
        if not table:
            debug_logs.append(f"[{country_code}-{state_code}] No table found inside div for event {event_name}")
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
                    "Country": COUNTRY_CODES.get(country_code, country_code),
                    "Region": state_code,
                    "Event": event_name,
                    "Place": place,
                    "Name": name,
                    "Points": points_val,
                    "Location": location,
                })
                debug_logs.append(f" - Competitor: {name}, Points: {points_val}")

    df = pd.DataFrame(results)
    return df, debug_logs

st.title("ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

region_options = ["All"] + [f"{country_code}-{code}" for country_code, code in REGIONS]
selected_region = st.selectbox("Select State/Province (or All):", region_options)

if st.button("Fetch Standings"):
    if selected_region == "All":
        all_dfs = []
        all_logs = []
        progress = st.progress(0)
        total = len(REGIONS)
        for i, (country_code, state_code) in enumerate(REGIONS, 1):
            st.write(f"Fetching {country_code}-{state_code}...")
            df_region, logs = scrape_region_standings(country_code, state_code)
            all_dfs.append(df_region)
            all_logs.extend(logs)
            progress.progress(i / total)
        combined_df = pd.concat(all_dfs, ignore_index=True)
        df = combined_df
        logs = all_logs

        st.subheader("Debug Logs")
        for log in logs:
            st.text(log)

        if df.empty:
            st.info("No competitors with points found.")
        else:
            st.subheader("All Competitors Combined by Event")

            # Show per-event tables, sorted by points, include Country and Region columns
            for event in sorted(df["Event"].unique()):
                st.markdown(f"### {event}")
                event_df = df[df["Event"] == event].sort_values(by="Points", ascending=False).reset_index(drop=True)
                event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
                display_cols = ["Rank", "Country", "Region", "Place", "Name", "Points", "Location"]
                st.dataframe(event_df[display_cols])

    else:
        country_code, state_code = selected_region.split("-")
        df, logs = scrape_region_standings(country_code, state_code)

        st.subheader("Debug Logs")
        for log in logs:
            st.text(log)

        if df.empty:
            st.info("No competitors with points found.")
        else:
            st.subheader("Competitor Standings")

            # Show events grouped, only for single region (no Country/Region columns)
            for event in sorted(df["Event"].unique()):
                st.markdown(f"### {event}")
                event_df = df[df["Event"] == event].sort_values(by="Points", ascending=False).reset_index(drop=True)
                event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
                display_cols = ["Rank", "Place", "Name", "Points", "Location"]
                st.dataframe(event_df[display_cols])
