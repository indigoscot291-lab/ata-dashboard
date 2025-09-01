import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- Google Sheet ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv&id=1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg&gid=0"

@st.cache_data
def load_tournament_data():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip()
    df["Name"] = df["Name"].str.upper().str.strip()
    df["Event"] = df["Event"].str.strip() if "Event" in df.columns else None
    return df

tournament_data = load_tournament_data()

# --- Scraping setup ---
BASE_URL = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state}&code=W01D"
WORLDS_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
    "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
    "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

CA_PROVINCES = ["AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"]

ALL_REGIONS = US_STATES + CA_PROVINCES

EVENT_ORDER = ["Forms", "Weapons", "Combat Weapons", "Sparring",
               "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"]

def parse_event_tables(soup):
    results = []
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table", class_="table")
    for header, table in zip(headers, tables):
        event_name = " | ".join(li.get_text(strip=True) for li in header.find_all("li"))
        for row in table.select("tbody tr"):
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) >= 4:
                results.append({
                    "Rank": int(cols[0]) if cols[0].isdigit() else None,
                    "Name": cols[1],
                    "Points": int(cols[2]) if cols[2].isdigit() else 0,
                    "Location": cols[3],
                    "Event": event_name
                })
    return results

@st.cache_data
def fetch_state_data(state_abbr):
    country = "US" if state_abbr in US_STATES else "CA"
    url = BASE_URL.format(country=country, state=state_abbr)
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        return parse_event_tables(soup)
    except:
        return []

@st.cache_data
def fetch_world_data():
    try:
        r = requests.get(WORLDS_URL)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        return parse_event_tables(soup)
    except:
        return []

def is_international(location):
    return not any(location.endswith(f", {abbr}") for abbr in ALL_REGIONS)

# --- Streamlit UI ---
st.title("ATA Standings - Women 50-59 1st Degree Black Belt")

options = ["All", "International"] + ALL_REGIONS
state_choice = st.selectbox("Select State/Province or International", options)
go = st.button("Go")

if go:
    all_results = []

    if state_choice == "All":
        for region in ALL_REGIONS:
            rows = fetch_state_data(region)
            if rows:
                all_results.extend(rows)
        world_rows = fetch_world_data()
        intl_rows = [r for r in world_rows if is_international(r["Location"])]
        all_results.extend(intl_rows)

    elif state_choice == "International":
        world_rows = fetch_world_data()
        intl_rows = [r for r in world_rows if is_international(r["Location"])]
        all_results.extend(intl_rows)

    else:
        rows = fetch_state_data(state_choice)
        if rows:
            all_results.extend(rows)

    if not all_results:
        st.write(f"There are no 50-59 1st Degree Women for {state_choice}")
    else:
        df = pd.DataFrame(all_results)
        df = df.dropna(subset=["Points"])
        df["Points"] = df["Points"].astype(int)
        df["Rank"] = df.groupby("Event").cumcount() + 1

        # Display events in ATA page order
        for event in EVENT_ORDER:
            event_rows = df[df["Event"].str.contains(event)]
            if not event_rows.empty:
                st.subheader(event)
                for _, row in event_rows.iterrows():
                    cols = st.columns([1,3,1,2])
                    cols[0].write(row["Rank"])
                    if cols[1].button(row["Name"], key=f"{event}-{row['Name']}"):
                        st.session_state["selected_name"] = row["Name"]
                        st.session_state["selected_event"] = event
                    cols[2].write(row["Points"])
                    cols[3].write(row["Location"])

# --- Floating Popup ---
if "selected_name" in st.session_state:
    name = st.session_state["selected_name"]
    selected_event = st.session_state.get("selected_event", None)

    with st.container():
        st.markdown(
            f"""
            <div style="
                position: relative;
                padding: 15px;
                border: 2px solid #4CAF50;
                border-radius: 10px;
                background-color: #f9f9f9;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                max-width: 600px;
                margin-bottom: 20px;
            ">
            <h4>🏆 Tournament details for {name}</h4>
            </div>
            """,
            unsafe_allow_html=True
        )

        details = tournament_data[
            (tournament_data["Name"].str.upper().str.strip() == name.upper().strip())
        ]
        if selected_event and "Event" in details.columns:
            details = details[details["Event"].str.strip() == selected_event]

        if not details.empty:
            st.table(details[["Date", "Tournament", "Points"]])
        else:
            st.info("No tournament details found for this competitor.")
