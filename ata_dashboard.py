import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

EVENT_ORDER = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

REGIONS = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
    "AB","BC","MB","NB","NL","NS","ON","PE","QC","SK"
]

DIVISION_CODE = "W01D"  # Women 1st Degree Black Belt 50-59

def get_country_for_region(region: str) -> str:
    ca = {"AB","BC","MB","NB","NL","NS","ON","PE","QC","SK"}
    return "CA" if region in ca else "US"

@st.cache_data(show_spinner=False)
def scrape_state_data(state_code: str, state_name: str) -> pd.DataFrame:
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={get_country_for_region(state_code)}&state={state_code}&code={DIVISION_CODE}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.find("div", class_="tab-content")
    if not content_div:
        return pd.DataFrame()

    rows = []
    current_event = None

    for li in content_div.find_all("li"):
        span = li.find("span", class_="text-primary text-uppercase")
        if span:
            event_name = span.get_text(strip=True)
            if event_name not in EVENT_ORDER:
                continue
            current_event = event_name

            # Find next sibling table after this li
            table = None
            for sibling in li.next_siblings:
                if hasattr(sibling, "name") and sibling.name == "table":
                    table = sibling
                    break
            if not table:
                continue

            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if "Name" not in headers or not any(k in headers for k in ("Pts", "Points", "PTS")):
                continue
            idx = {h: i for i, h in enumerate(headers)}
            pts_key = next((k for k in ("Pts", "Points", "PTS") if k in idx), None)

            for tr in table.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) <= max(idx["Name"], idx[pts_key]):
                    continue
                name = tds[idx["Name"]].get_text(strip=True)
                raw = tds[idx[pts_key]].get_text(strip=True)
                try:
                    points = float(raw.replace(",", ""))
                except:
                    continue
                if points > 0:
                    rows.append({"Name": name, "Event": current_event, "Points": points, "State": state_name})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["Event", "Name"], keep="first").reset_index(drop=True)
    df["Rank"] = df.groupby("Event")["Points"].rank(method="min", ascending=False).astype(int)
    return df

st.set_page_config(page_title="ATA W01D Standings", layout="wide")
st.title("ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

selected_state = st.selectbox("Select State or Province", ["All"] + REGIONS)
selected_event = st.selectbox("Select Event", ["All"] + EVENT_ORDER)
name_filter = st.text_input("Filter by competitor name (optional)").strip().lower()
search_button = st.button("Go")

if search_button:
    states_to_search = REGIONS if selected_state == "All" else [selected_state]
    all_results = []
    with st.spinner("Fetching data..."):
        for state in states_to_search:
            df_state = scrape_state_data(state, state)
            if not df_state.empty:
                all_results.append(df_state)

    if not all_results:
        st.info("No results found for selected criteria.")
    else:
        df = pd.concat(all_results, ignore_index=True)

        if selected_event != "All":
            df = df[df["Event"] == selected_event]
        if name_filter:
            df = df[df["Name"].str.lower().str.contains(name_filter)]

        if df.empty:
            st.info("No matches after filtering.")
        else:
            for event in EVENT_ORDER:
                event_df = df[df["Event"] == event]
                if not event_df.empty:
                    event_df = event_df.sort_values(by=["Points", "Name"], ascending=[False, True])
                    event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
                    st.subheader(event)
                    st.dataframe(event_df[["Rank", "Name", "Points", "State"]], use_container_width=True)
