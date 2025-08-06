import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

EVENT_KEYWORDS = {
    "Forms": "Forms",
    "Weapons": "Weapons",
    "Combat": "Combat Weapons",
    "Sparring": "Sparring",
    "Creative Forms": "Creative Forms",
    "Creative Weapons": "Creative Weapons",
    "X-Treme Forms": "X-Treme Forms",
    "X-Treme Weapons": "X-Treme Weapons",
}

EVENT_ORDER = list(EVENT_KEYWORDS.values())

REGIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"
]

DIVISION_CODE = "W01D"  # Women 1st Degree, 50-59

def get_event_name_from_text(text):
    for keyword, event in EVENT_KEYWORDS.items():
        if keyword.lower() in text.lower():
            return event
    return None

def get_country_for_region(region: str) -> str:
    ca_list = {"AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"}
    return "CA" if region in ca_list else "US"

@st.cache_data(ttl=600, show_spinner=False)
def scrape_state_data(state_code, division_code=DIVISION_CODE, country="US") -> pd.DataFrame:
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={division_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows_data = []

    for li in soup.find_all("li"):
        for li in soup.find_all("li"):
    li_text = li.get_text(strip=True)
    st.write(f"DEBUG li text: '{li_text}'")
    event_name = get_event_name_from_text(li_text)
    st.write(f" -> matched event: {event_name}")  # shows if keyword detection succeeded
        event_name = get_event_name_from_text(li.get_text(strip=True))
        if not event_name:
            continue

        table = None
        for sibling in li.next_siblings:
            if hasattr(sibling, "name") and sibling.name == "table":
                table = sibling
                break
        if not table:
            continue

        th_texts = [th.get_text(strip=True) for th in table.find_all("th")]
        col_idx = {name: idx for idx, name in enumerate(th_texts)}

        pts_key = next((k for k in ("Pts", "Points", "PTS") if k in col_idx), None)
        if "Name" not in col_idx or pts_key is None:
            continue

        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) <= max(col_idx["Name"], col_idx[pts_key]):
                continue

            name = tds[col_idx["Name"]].get_text(strip=True)
            pts_text = tds[col_idx[pts_key]].get_text(strip=True)

            match = re.search(r"[\d,.]+", pts_text)
            if match:
                try:
                    points = float(match.group(0).replace(",", ""))
                except ValueError:
                    continue
                if points > 0:
                    rows_data.append({
                        "Name": name,
                        "Event": event_name,
                        "Points": points,
                        "State/Province": state_code,
                        "Country": country
                    })

    if not rows_data:
        return pd.DataFrame()

    df = pd.DataFrame(rows_data)
    df = df.drop_duplicates(subset=["Event", "Name"], keep="first").reset_index(drop=True)
    return df

# --- Streamlit App UI ---

st.set_page_config(page_title="ATA W01D Standings", layout="wide")
st.title("ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

st.subheader("Select Filters")

col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
with col1:
    selected_region = st.selectbox("Region", ["All"] + REGIONS)

with col2:
    selected_event = st.selectbox("Event", ["All"] + EVENT_ORDER)

with col3:
    name_query = st.text_input("Competitor Name (optional)").strip().lower()

with col4:
    search = st.button("🔍 Go")

if search:
    if selected_region == "All":
        all_dfs = []
        progress = st.progress(0)
        total = len(REGIONS)

        with st.spinner("Fetching data for all regions..."):
            for i, region in enumerate(REGIONS, 1):
                country = get_country_for_region(region)
                df = scrape_state_data(region, country=country)
                if not df.empty:
                    all_dfs.append(df)
                progress.progress(i / total)

        progress.empty()

        if not all_dfs:
            st.warning("No results found.")
        else:
            df = pd.concat(all_dfs, ignore_index=True)
    else:
        with st.spinner(f"Fetching data for {selected_region}..."):
            country = get_country_for_region(selected_region)
            df = scrape_state_data(selected_region, country=country)

    if df.empty:
        st.info("No competitors found.")
    else:
        df = df.drop_duplicates(subset=["Event", "Name"], keep="first")
        df["Rank"] = df.groupby("Event")["Points"].rank(method="min", ascending=False).astype(int)

        if selected_event != "All":
            df = df[df["Event"] == selected_event]

        if name_query:
            df = df[df["Name"].str.lower().str.contains(name_query)]

        if df.empty:
            st.info("No matching results with the selected filters.")
        else:
            st.success(f"Showing {len(df)} competitors")
            for event in EVENT_ORDER:
                event_df = df[df["Event"] == event]
                if not event_df.empty:
                    event_df = event_df.sort_values("Points", ascending=False).reset_index(drop=True)
                    event_df["Rank"] = event_df["Points"].rank(method="min", ascending=False).astype(int)
                    st.subheader(f"{event}")
                    st.dataframe(event_df[["Rank", "Name", "Points", "State/Province", "Country"]], use_container_width=True)

