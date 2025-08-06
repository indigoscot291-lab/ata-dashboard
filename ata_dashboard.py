import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Event keyword mapping (used to identify which <li> corresponds to which event)
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

# US states + Canadian provinces
REGIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"
]

DIVISION_CODE = "W01D"  # Women 1st Degree, 50-59

# canonical event display order
EVENT_ORDER = [
    "Forms",
    "Weapons",
    "Combat Weapons",
    "Sparring",
    "Creative Forms",
    "Creative Weapons",
    "X-Treme Forms",
    "X-Treme Weapons",
]

def get_event_name_from_text(text: str):
    """Return canonical event name if any keyword matches header text (case-insensitive)."""
    for keyword, event in EVENT_KEYWORDS.items():
        if keyword.lower() in text.lower():
            return event
    return None

@st.cache_data(ttl=600, show_spinner=False)
def scrape_state_data(state_code: str, division_code: str = DIVISION_CODE, country: str = "US") -> pd.DataFrame:
    """
    Scrape the state standings page for the given division code.
    Looks for <li> elements that contain event keywords and grabs the next <table>.
    Returns rows with Name, Event, Points, State/Province, Country, and Rank.
    """
    url = f"https://atamartialarts.com/events/tournament-standings/state-standings/?country={country}&state={state_code}&code={division_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        # Return empty DataFrame on any request problem
        st.warning(f"Error fetching data for {state_code}: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows_data = []

    # Find all list items and attempt to identify event names, then parse the following table
    for li in soup.find_all("li"):
        li_text = li.get_text(strip=True)
        event_name = get_event_name_from_text(li_text)
        if not event_name:
            continue

        # Get the next table after this li
        table = li.find_next("table")
        if not table:
            continue

        # Read column headers from the table
        th_texts = [th.get_text(strip=True) for th in table.find_all("th")]
        col_idx = {name: idx for idx, name in enumerate(th_texts)}

        # Must contain Name and Pts (Pts or Points may vary)
        pts_key = None
        for candidate in ("Pts", "Points", "PTS"):
            if candidate in col_idx:
                pts_key = candidate
                break
        if "Name" not in col_idx or pts_key is None:
            # If required columns not present, skip this table
            continue

        # Parse rows
        tr_rows = table.find_all("tr")[1:]  # skip header row
        for tr in tr_rows:
            tds = tr.find_all("td")
            # ensure enough columns
            if len(tds) <= max(col_idx["Name"], col_idx[pts_key]):
                continue

            name = tds[col_idx["Name"]].get_text(strip=True)
            pts_text = tds[col_idx[pts_key]].get_text(strip=True).replace(",", "").strip()

            # Try parse points (allow integers or floats). If not parseable, skip.
            try:
                # Points may be integer or float; treat as float for safety
                points = float(pts_text)
            except Exception:
                continue

            # Include only competitors who have > 0 points
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

    # Deduplication within a single scrape (rare)
    df = df.drop_duplicates(subset=["Event", "Name"], keep="first").reset_index(drop=True)

    # Rank per event within scrape (will be recalculated after combining)
    df["Rank"] = df.groupby("Event")["Points"].rank(method="min", ascending=False).astype(int)

    # Reorder columns with Rank first
    df = df[["Rank", "Name", "Points", "State/Province", "Country", "Event"]]

    return df

def get_country_for_region(region: str) -> str:
    ca_list = {"AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"}
    return "CA" if region in ca_list else "US"

st.set_page_config(page_title="ATA W01D Standings", layout="wide")
st.title("ATA Standings — Women 50–59, 1st Degree Black Belt (W01D)")

region_options = ["All"] + REGIONS
selected_region = st.selectbox("Select State or Province", region_options)

if selected_region == "All":
    all_dfs = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_regions = len(REGIONS)

    with st.spinner("Loading standings for all regions... this may take a bit..."):
        for i, region in enumerate(REGIONS, start=1):
            country = get_country_for_region(region)
            df_state = scrape_state_data(region, division_code=DIVISION_CODE, country=country)
            if not df_state.empty:
                all_dfs.append(df_state)

            progress_bar.progress(i / total_regions)
            status_text.text(f"Fetched {i} of {total_regions} regions...")

    progress_bar.empty()
    status_text.empty()

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
    else:
        df = pd.DataFrame()

    if df.empty:
        st.info("No results found for any region.")
    else:
        # Remove duplicates globally by Event + Name, keep highest points
        df = df.sort_values(["Event", "Name", "Points"], ascending=[True, True, False])
        df = df.drop_duplicates(subset=["Event", "Name"], keep="first").reset_index(drop=True)

        # Calculate total points per competitor (across all events)
        total_points = df.groupby("Name")["Points"].sum().reset_index()
        total_points = total_points.rename(columns={"Points": "Total Points"})

        # Merge total points back into df
        df = df.merge(total_points, on="Name", how="left")

        # Recalculate Rank per event by descending points
        df["Rank"] = df.groupby("Event")["Points"].rank(method="min", ascending=False).astype(int)

        # Filters
        event_options = ["All"] + sorted(df["Event"].unique())
        selected_event = st.selectbox("Select Event (or All)", event_options)

        name_query = st.text_input("Filter by Competitor Name (optional)").strip().lower()

        display_df = df.copy()
        if selected_event != "All":
            display_df = display_df[display_df["Event"] == selected_event]

        if name_query:
            display_df = display_df[display_df["Name"].str.lower().str.contains(name_query)]

        if display_df.empty:
            st.info("No competitors match the selected filters.")
        else:
            st.write(f"Showing {len(display_df)} competitor rows from all regions")

            events_present = [e for e in EVENT_ORDER if e in display_df["Event"].unique()]
            if not events_present:
                events_present = sorted(display_df["Event"].unique())

            for event in events_present:
                st.subheader(event)
                ev_df = display_df[display_df["Event"] == event].copy()

                # Sort by descending points, then ascending name
                ev_df = ev_df.sort_values(["Points", "Name"], ascending=[False, True]).reset_index(drop=True)

                # Recalculate Rank to match sorting
                ev_df["Rank"] = ev_df["Points"].rank(method="min", ascending=False).astype(int)

                display_cols = ["Rank", "Name", "Points", "Total Points", "State/Province", "Country"]

                st.dataframe(ev_df[display_cols], use_container_width=True)

else:
    country = get_country_for_region(selected_region)
    with st.spinner(f"Loading standings for {selected_region}..."):
        df = scrape_state_data(selected_region, division_code=DIVISION_CODE, country=country)

    if df.empty:
        st.info("No results found for this selection (or no competitors with points).")
    else:
        event_options = ["All"] + sorted(df["Event"].unique())
        selected_event = st.selectbox("Select Event (or All)", event_options)

        name_query = st.text_input("Filter by Competitor Name (optional)").strip().lower()

        display_df = df.copy()
        if selected_event != "All":
            display_df = display_df[display_df["Event"] == selected_event]

        if name_query:
            display_df = display_df[display_df["Name"].str.lower().str.contains(name_query)]

        if display_df.empty:
            st.info("No competitors match the selected filters.")
        else:
            events_present = [e for e in EVENT_ORDER if e in display_df["Event"].unique()]
            if not events_present:
                events_present = sorted(display_df["Event"].unique())

            st.write(f"Showing {len(display_df)} competitor rows for {selected_region}")

            for event in events_present:
                st.subheader(event)
                ev_df = display_df[display_df["Event"] == event].copy()

                # Sort by descending points, then ascending name
                ev_df = ev_df.sort_values(["Points", "Name"], ascending=[False, True]).reset_index(drop=True)

                ev_df["Rank"] = ev_df["Points"].rank(method="min", ascending=False).astype(int)

                display_cols = ["Rank", "Name", "Points", "State/Province", "Country"]

                st.dataframe(ev_df[display_cols], use_container_width=True)
