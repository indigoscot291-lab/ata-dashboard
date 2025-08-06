# app.py
"""
ATA Tournament Standings Scraper & Dashboard

Usage:
    pip install -r requirements.txt
    streamlit run app.py

Default: Fetches ATA Worlds standings and dedupes competitors.
"""

import re
from typing import List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from datetime import datetime

# ---------------------------
# Configuration
# ---------------------------
DEFAULT_URL = "https://atamartialarts.com/events/tournament-standings/worlds-standings"
REQUEST_TIMEOUT = 15  # seconds

# ---------------------------
# Scraper functions
# ---------------------------

def fetch_html(url: str) -> str:
    """Fetch HTML from a URL."""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text

def _clean_event_name(text: str) -> str:
    """Normalize event name."""
    if not text:
        return "Unknown Event"
    return re.sub(r'\s+', ' ', text).strip()

def parse_events_from_html(html: str) -> List[pd.DataFrame]:
    """Extract events and tables from ATA standings page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    events: List[pd.DataFrame] = []

    # Primary: <li> header + next <table>
    for li in soup.find_all("li"):
        event_name = _clean_event_name(li.get_text(separator=" ", strip=True))
        table = li.find_next("table")
        if table:
            try:
                df = pd.read_html(str(table))[0]
            except ValueError:
                continue
            df["Event"] = event_name
            events.append(df)

    # Fallback: all tables + nearest heading
    if not events:
        for table in soup.find_all("table"):
            try:
                df = pd.read_html(str(table))[0]
            except ValueError:
                continue
            heading_tag = table.find_previous(["h1", "h2", "h3", "h4", "p", "div"])
            event_name = _clean_event_name(heading_tag.get_text(" ", strip=True)) if heading_tag else "Unknown Event"
            df["Event"] = event_name
            events.append(df)

    return events

def _detect_score_column(df: pd.DataFrame) -> Optional[str]:
    """Detect numeric score column heuristically."""
    if df is None or df.empty:
        return None
    # Check column names
    name_candidates = [c for c in df.columns if re.search(r'score|points|total|avg|judge', str(c), flags=re.I)]
    if name_candidates:
        return name_candidates[0]
    # Check numeric content
    for col in df.columns:
        coerced = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
        if coerced.notna().mean() >= 0.5:
            return col
    return None

def dedupe_event_df(df: pd.DataFrame, method: str = "first", competitor_col_hint: Optional[str] = None) -> pd.DataFrame:
    """Dedupe competitors within one event."""
    if method == "all":
        return df.copy()
    # Find competitor column
    if competitor_col_hint and competitor_col_hint in df.columns:
        comp_col = competitor_col_hint
    else:
        comp_cols = [c for c in df.columns if re.search(r'competitor|name|athlete', str(c), flags=re.I)]
        if comp_cols:
            comp_col = comp_cols[0]
        else:
            comp_col = df.columns[0]
    df[comp_col] = df[comp_col].astype(str).str.strip()

    if method == "first":
        return df.drop_duplicates(subset=[comp_col], keep="first").reset_index(drop=True)

    # method == "best"
    score_col = _detect_score_column(df)
    if not score_col:
        return df.drop_duplicates(subset=[comp_col], keep="first").reset_index(drop=True)
    numeric_score = pd.to_numeric(df[score_col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
    df["_numeric_score_tmp"] = numeric_score
    idx = df.sort_values("_numeric_score_tmp", ascending=False).groupby(comp_col, sort=False).head(1).index
    return df.loc[idx].drop(columns=["_numeric_score_tmp"]).reset_index(drop=True)

def combine_events(events: List[pd.DataFrame], dedupe_method: str = "first", competitor_col_hint: Optional[str] = None) -> pd.DataFrame:
    """Combine all events after deduping each."""
    processed = [dedupe_event_df(ev, method=dedupe_method, competitor_col_hint=competitor_col_hint) for ev in events]
    combined = pd.concat(processed, ignore_index=True, sort=False)
    if "Event" in combined.columns:
        cols = ["Event"] + [c for c in combined.columns if c != "Event"]
        combined = combined[cols]
    return combined

def fetch_and_process(url: str, dedupe_method: str = "first", competitor_col_hint: Optional[str] = None) -> pd.DataFrame:
    """Pipeline: fetch HTML, parse events, combine."""
    html = fetch_html(url)
    events = parse_events_from_html(html)
    return combine_events(events, dedupe_method, competitor_col_hint)

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="ATA Standings Dashboard", layout="wide")
st.title("ATA Tournament Standings")

st.sidebar.header("Settings")
url = st.sidebar.text_input("Standings URL", value=DEFAULT_URL)
dedupe = st.sidebar.selectbox("Dedupe method", ["first", "best", "all"])
competitor_hint = st.sidebar.text_input("Competitor column name (optional)", value="")
ttl = st.sidebar.number_input("Cache TTL (seconds)", value=300, min_value=30, step=30)
fetch_now = st.sidebar.button("Fetch / Refresh")

@st.cache_data(ttl=ttl)
def load_data(url, dedupe, competitor_hint):
    return fetch_and_process(url, dedupe, competitor_hint if competitor_hint else None)

if ("data" not in st.session_state) or fetch_now:
    try:
        with st.spinner("Fetching data..."):
            st.session_state["data"] = load_data(url, dedupe, competitor_hint)
            st.success(f"Fetched at {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        st.error(f"Error: {e}")

if "data" in st.session_state:
    df = st.session_state["data"]
    if df.empty:
        st.warning("No data found.")
    else:
        st.write(f"**Rows:** {len(df)} | **Columns:** {len(df.columns)}")
        events = ["All Events"] + sorted(df["Event"].dropna().unique().tolist())
        chosen_event = st.selectbox("Filter by Event", events)
        shown = df if chosen_event == "All Events" else df[df["Event"] == chosen_event]
        st.dataframe(shown, use_container_width=True)

        # CSV download
        csv_bytes = shown.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv_bytes, file_name="ata_standings.csv", mime="text/csv")

        # Score column summary
        score_col = _detect_score_column(shown)
        if score_col:
            st.write(f"Detected score column: **{score_col}**")
            numeric = pd.to_numeric(shown[score_col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce')
            if numeric.notna().any():
                top10 = shown.assign(_score=numeric).sort_values("_score", ascending=False).head(10)
                st.subheader("Top 10 by score")
                st.table(top10.drop(columns=["_score"]).reset_index(drop=True))
