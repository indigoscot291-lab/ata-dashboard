import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

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
    results = []
    current_event = None

    for li in soup.find_all("li"):
        li_text = li.get_text(strip=True)
        st.write(f"DEBUG li text: '{li_text}'")  # Debug raw <li> text
        event_name = get_event_name_from_text(li_text)
        st.write(f" -> matched event: {event_name}")  # Debug event match

        if event_name:
            current_event = event_name
            table = None

            # Try to find the table right after this <li>
            sibling = li.find_next_sibling()
            while sibling and not (hasattr(sibling, "name") and sibling.name == "table"):
                sibling = sibling.find_next_sibling()

            if sibling and sibling.name == "table":
                rows = sibling.find_all("tr")[1:]  # Skip header
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

def get_event_name_from_text(text):
    lower = text.lower()
    if "forms" in lower and "creative" not in lower and "x" not in lower:
        return "Forms"
    if "combat weapons" in lower:
        return "Combat Weapons"
    if "weapons" in lower and "creative" not in lower and "combat" not in lower and "x" not in lower:
        return "Weapons"
    if "sparring" in lower and "combat" not in lower:
        return "Sparring"
    if "creative forms" in lower:
        return "Creative Forms"
    if "creative weapons" in lower:
        return "Creative Weapons"
    if "x-treme forms" in lower or "xtreme forms" in lower:
        return "X-Treme Forms"
    if "x-treme weapons" in lower or "xtreme weapons" in lower:
        return "X-Treme Weapons"
    return None

# --- UI for testing ---
st.title("ATA Women's 50-59 World Standings Debug")

selected_state = st.selectbox("Select a state to test", ["WA", "CA", "TX", "NY", "FL"], index=0)
state_name_map = {
    "WA": "Washington",
    "CA": "California",
    "TX": "Texas",
    "NY": "New York",
    "FL": "Florida"
}

if st.button("Scrape Selected State"):
    state_data = scrape_state_data(selected_state, state_name_map[selected_state])
    if state_data:
        df = pd.DataFrame(state_data)
        st.dataframe(df)
    else:
        st.write("No data found.")
