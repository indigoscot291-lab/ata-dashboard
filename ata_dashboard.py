import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")

# Session state for refresh timestamp
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = "Never"

# --- Helper Functions ---
@st.cache_data
def fetch_html(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

@st.cache_data
def load_google_sheet(sheet_url):
    return pd.read_csv(sheet_url)

# --- Sidebar Navigation ---
page_choice = st.sidebar.selectbox(
    "Choose a page:",
    [
        "ATA Standings Dashboard",
        "50-59 Women Black Belts",
        "50-59 Women Color Belts",
    ]
)

# --- Page 1: ATA Standings Dashboard ---
if page_choice == "ATA Standings Dashboard":
    st.title("ATA Standings Dashboard")

    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.session_state.last_refresh = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Data refreshed successfully!")

    st.caption(f"Last refreshed: {st.session_state.last_refresh}")

    # Example of loading 40–49 and 50–59 data from Google Sheets
    sheet_40_49 = "https://docs.google.com/spreadsheets/d/your_40_49_sheet/export?format=csv"
    sheet_50_59 = "https://docs.google.com/spreadsheets/d/your_50_59_sheet/export?format=csv"

    try:
        df_40_49 = load_google_sheet(sheet_40_49)
        df_50_59 = load_google_sheet(sheet_50_59)

        st.subheader("40–49 Women Black Belts")
        st.dataframe(df_40_49, use_container_width=True)

        st.subheader("50–59 Women Black Belts")
        st.dataframe(df_50_59, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading Google Sheets: {e}")

# --- Page 2: 50-59 Women Black Belts ---
elif page_choice == "50-59 Women Black Belts":
    st.title("50-59 Women Black Belts")

    sheet_50_59 = "https://docs.google.com/spreadsheets/d/your_50_59_sheet/export?format=csv"

    try:
        df_50_59 = load_google_sheet(sheet_50_59)
        st.dataframe(df_50_59, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")

# --- Page 3: 50-59 Women Color Belts ---
elif page_choice == "50-59 Women Color Belts":
    st.title("50-59 Women Color Belts")

    if st.button("🔄 Refresh Color Belt Data"):
        st.cache_data.clear()
        st.session_state.last_refresh = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success("Color belt data refreshed successfully!")

    st.caption(f"Last refreshed: {st.session_state.last_refresh}")

    url = "https://atamartialarts.com/events/tournament-standings/state-standings/?country=US&state=ga&code=WCOD"

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if table:
            df_color = pd.read_html(str(table))[0]
            st.dataframe(df_color, use_container_width=True)
        else:
            st.warning("No standings table found on the ATA website for this division.")

    except Exception as e:
        st.error(f"Error loading standings: {e}")
