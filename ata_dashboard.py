import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="ATA Tournament Standings", layout="wide")

EVENT_KEYWORDS = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

@st.cache_data(show_spinner=False)
def get_states():
    return {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming",
        "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
        "NB": "New Brunswick", "NL": "Newfoundland and Labrador", "NS": "Nova Scotia",
        "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
        "SK": "Saskatchewan", "NT": "Northwest Territories", "NU": "Nunavut", "YT": "Yukon"
    }

@st.cache_data(show_spinner=False)
def get_event_name_from_text(text):
    for keyword in EVENT_KEYWORDS:
        if keyword.lower() in text.lower():
            return keyword
    return None

@st.cache_data(show_spinner=False)
def scrape_state_data(state_code, state_name):
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country=US&state={state_code}&code=W01D"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        st.warning(f"Skipping {state_name} – page not available.")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    content_div = soup.find("div", class_="tab-content")
    if not content_div:
        st.warning(f"No standings section found for {state_name}.")
        return []

    results = []
    current_event = None

    for li in content_div.find_all("li"):
        li_text = li.get_text(strip=True)
        st.write(f"DEBUG li text: '{li_text}'")  # Debug raw <li> text
        event_name = get_event_name_from_text(li_text)
        st.write(f" -> matched event: {event_name}")  # Debug event match

        if event_name:
            current_event = event_name
            sibling = li.find_next_sibling()
            while sibling and sibling.name != "table":
                sibling = sibling.find_next_sibling()

            if sibling and sibling.name == "table":
                rows = sibling.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 3:
                        name = cols[1].get_text(strip=True)
                        points = cols[2].get_text(strip=True)
                        if name and points.isdigit():
                            results.append({
                                "State": state_name,
                                "Event": current_event,
                                "Name": name,
                                "Points": int(points)
                            })
    return results

@st.cache_data(show_spinner=True)
def get_all_data(selected_states):
    all_results = []
    states = get_states()
    for code in selected_states:
        name = states[code]
        data = scrape_state_data(code, name)
        all_results.extend(data)
    return pd.DataFrame(all_results)

# --------------------- UI ------------------------
st.title("ATA Tournament Standings")
st.markdown("Select a state or all, pick events (or all), or search by name. Then hit Go.")

states_dict = get_states()
state_options = ["ALL"] + list(states_dict.keys())
selected_state = st.selectbox("Select a State or Province", state_options)
selected_events = st.multiselect("Select Events", EVENT_KEYWORDS, default=EVENT_KEYWORDS)
search_name = st.text_input("Search Competitor Name (optional)")

run = st.button("Go")

if run:
    selected_state_codes = list(states_dict.keys()) if selected_state == "ALL" else [selected_state]
    with st.spinner("Fetching data..."):
        df = get_all_data(selected_state_codes)

    if not df.empty:
        # Filter by events
        if selected_events:
            df = df[df["Event"].isin(selected_events)]

        # Filter by name
        if search_name:
            df = df[df["Name"].str.contains(search_name, case=False, na=False)]

        # Group by Event and Name
        grouped = df.groupby(["Event", "Name"], as_index=False)["Points"].sum()
        grouped = grouped.sort_values(["Event", "Points"], ascending=[True, False])

        # Add rank within each event
        grouped["Rank"] = grouped.groupby("Event")["Points"].rank(method="dense", ascending=False).astype(int)

        # Reorder columns and show
        grouped = grouped[["Event", "Rank", "Name"]]
        st.dataframe(grouped, use_container_width=True)
    else:
        st.warning("No results found.")
