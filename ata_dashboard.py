import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# --------------------------
# Config
# --------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv&id=1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg&gid=0"

BASE_URL = "https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state}&code=W01D"
WORLDS_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D"

US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
    "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
    "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

CA_PROVINCES = ["AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"]

ALL_REGIONS = US_STATES + CA_PROVINCES
EVENT_ORDER = ["Forms", "Weapons", "Combat Weapons", "Sparring",
               "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"]

# --------------------------
# Load Google Sheet
# --------------------------
@st.cache_data
def load_tournament_data():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip()
    df["Name"] = df["Name"].str.strip().str.upper()
    return df

tournament_data = load_tournament_data()

# --------------------------
# Scraping Functions
# --------------------------
def parse_event_tables(soup):
    results = []
    for ul in soup.find_all("ul", class_="tournament-header"):
        first_li = ul.find("li")
        if not first_li:
            continue
        span = first_li.find("span")
        if not span:
            continue
        event_name = span.get_text(strip=True)
        if event_name not in EVENT_ORDER:
            continue
        table_div = ul.find_next_sibling("div", class_="table-responsive")
        if not table_div:
            continue
        table = table_div.find("table")
        if not table:
            continue
        for tr in table.select("tbody tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cols) >= 4 and cols[2].isdigit() and int(cols[2]) > 0:
                results.append({
                    "Name": cols[1].strip().upper(),
                    "Points": int(cols[2]),
                    "Location": cols[3].strip(),
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

# --------------------------
# Google Sheet Lookup
# --------------------------
def get_competitor_event_details(name, event):
    lookup_name = name.strip().upper()
    competitor_rows = tournament_data[tournament_data["Name"] == lookup_name]
    if competitor_rows.empty or event not in tournament_data.columns:
        return pd.DataFrame()
    df_event = competitor_rows[["Date", "Tournament", event]].copy()
    df_event = df_event.rename(columns={event: "Points"})
    df_event = df_event[df_event["Points"] > 0]
    return df_event

# --------------------------
# Streamlit UI
# --------------------------
st.title("ATA Standings - Women 50-59 1st Degree Black Belt")

state_options = ["All", "International"] + ALL_REGIONS
selected_state = st.selectbox("Select State/Province or International", state_options)
event_options = ["All"] + EVENT_ORDER
selected_event = st.selectbox("Select Event", event_options)
name_filter = st.text_input("Filter by Name (optional)")
go = st.button("Go")

# Clear previous selection if state/event changed
for key in ["selected_name", "selected_event", "selected_state"]:
    if key in st.session_state:
        st.session_state.pop(key)

if go:
    all_results = []
    regions_to_fetch = []

    if selected_state == "All":
        regions_to_fetch = ALL_REGIONS
        world_rows = fetch_world_data()
    elif selected_state == "International":
        world_rows = fetch_world_data()
    else:
        regions_to_fetch = [selected_state]

    total_regions = len(regions_to_fetch)
    if total_regions > 0:
        st.write("Fetching state/province results...")
        progress_bar = st.progress(0)
        start_time = time.time()
        for i, region in enumerate(regions_to_fetch, start=1):
            rows = fetch_state_data(region)
            if rows:
                all_results.extend(rows)
            # Update progress
            progress = i / total_regions
            progress_bar.progress(progress)
            elapsed = time.time() - start_time
            remaining = (elapsed / i) * (total_regions - i)
            st.write(f"Processed {i}/{total_regions} ({progress*100:.1f}%), estimated time remaining: {remaining:.1f}s")
        # Add international rows for All
        if selected_state == "All":
            existing_names = {r["Name"] for r in all_results}
            intl_rows = [r for r in world_rows if is_international(r["Location"]) and r["Name"] not in existing_names]
            all_results.extend(intl_rows)
    elif selected_state == "International":
        all_results.extend([r for r in world_rows if is_international(r["Location"])])

    # Display results
    if not all_results:
        st.write(f"There are no 50-59 1st Degree Women for {selected_state}")
    else:
        df = pd.DataFrame(all_results)
        df = df[df["Points"] > 0]
        if name_filter:
            df = df[df["Name"].str.contains(name_filter.strip(), case=False)]
        df["Rank"] = df.groupby("Event").cumcount() + 1

        for event in EVENT_ORDER:
            if selected_event != "All" and event != selected_event:
                continue
            event_rows = df[df["Event"] == event]
            if not event_rows.empty:
                st.subheader(event)
                for idx, row in event_rows.iterrows():
                    cols = st.columns([1,3,1,2])
                    cols[0].write(row["Rank"])
                    state_key = selected_state if selected_state != "International" else "INTL"
                    button_key = f"{state_key}-{event}-{row['Name']}-{idx}"
                    if cols[1].button(row["Name"], key=button_key):
                        st.session_state["selected_name"] = row["Name"]
                        st.session_state["selected_event"] = event
                        st.session_state["selected_state"] = state_key
                    cols[2].write(row["Points"])
                    cols[3].write(row["Location"])

# --------------------------
# Popup for competitor
# --------------------------
if "selected_name" in st.session_state and "selected_event" in st.session_state:
    name = st.session_state["selected_name"]
    event = st.session_state["selected_event"]
    st.markdown(f"### 🏆 Tournament details for {name} - {event}")
    details = get_competitor_event_details(name, event)
    if not details.empty:
        st.table(details)
    else:
        st.info("No tournament points for this competitor in this event.")
