import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- CONFIG ---
EVENT_NAMES = [
    "Forms", "Weapons", "Combat Weapons", "Sparring",
    "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
]

GROUPS = {
    "1st Degree Women 50-59": {
        "world_url": "...?code=W01D",
        "state_url_template": "...?code=W01D",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1tCWIc...export?format=csv"
    },
    "2nd/3rd Degree Women 40-49": {
        "world_url": "...?code=W23C",
        "state_url_template": "...?code=W23C",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv"
    }
}

REGION_CODES = {
    "Alabama": ("US", "AL"), "Alaska": ("US", "AK"), ... # full list
}

REGIONS = ["All"] + list(REGION_CODES.keys()) + ["International"]

# --- FETCH FUNCTIONS ---
@st.cache_data(ttl=3600)
def fetch_html(url):
    try:
        r = requests.get(url, timeout=10)
        return r.text if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_sheet(sheet_url):
    if not sheet_url:
        return pd.DataFrame()
    try:
        df = pd.read_csv(sheet_url)
        for ev in EVENT_NAMES:
            if ev in df.columns:
                df[ev] = pd.to_numeric(df[ev], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

# --- PARSING AND RANKING ---
def parse_standings(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {ev: [] for ev in EVENT_NAMES}
    headers = soup.find_all("ul", class_="tournament-header")
    tables = soup.find_all("table")
    for header, table in zip(headers, tables):
        evt = header.find("span", class_="text-primary text-uppercase")
        if evt and (ev_name := evt.get_text(strip=True)) in EVENT_NAMES:
            rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
            for tr in rows:
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) == 4 and all(cols):
                    _, name, pts, loc = cols
                    try:
                        pts = int(pts)
                        if pts > 0:
                            data[ev_name].append({
                                "Name": name.strip(),
                                "Points": pts,
                                "Location": loc
                            })
                    except:
                        pass
    return data

def gather_data(selected_group, selected_region):
    cfg = GROUPS[selected_group]
    combined = {ev: [] for ev in EVENT_NAMES}

    world_html = fetch_html(cfg["world_url"])
    if world_html:
        wdata = parse_standings(world_html)
        for ev, entries in wdata.items():
            combined[ev].extend(entries)

    if selected_region not in ["All", "International"]:
        country, code = REGION_CODES[selected_region]
        url = cfg["state_url_template"].format(country, code)
        html = fetch_html(url)
        if html:
            sx = parse_standings(html)
            return ({ev: sx.get(ev, []) for ev in EVENT_NAMES},
                    any(len(lst) for lst in sx.values()))
        return ({ev: [] for ev in EVENT_NAMES}, False)
    elif selected_region == "All":
        any_data = False
        for reg in REGION_CODES:
            url = cfg["state_url_template"].format(*REGION_CODES[reg])
            html = fetch_html(url)
            if html:
                sx = parse_standings(html)
                for ev, entries in sx.items():
                    combined[ev].extend(entries)
                any_data |= any(len(lst) for lst in sx.values())
        return combined, any_data
    else:  # International
        intl = {ev: [] for ev in EVENT_NAMES}
        for ev, entries in combined.items():
            intl[ev] = [e for e in entries if not re.search(r",\s*[A-Z]{2}$", e["Location"])]
        return intl, any(intl.values())

def dedupe_and_rank(event_data):
    clean = {}
    for ev, entries in event_data.items():
        seen = set()
        unique = []
        for e in entries:
            key = (e["Name"].lower(), e["Location"], e["Points"])
            if key not in seen:
                seen.add(key)
                unique.append(e)
        unique.sort(key=lambda x: x["Points"], reverse=True)
        rank = 1
        prev_pts = None
        for idx, row in enumerate(unique, start=1):
            row["Rank"] = rank if row["Points"] == prev_pts else idx
            prev_pts = row["Points"]
            rank = row["Rank"]
        clean[ev] = unique
    return clean

# --- UI ---
st.title("ATA Standings Viewer")

is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"
selected_group = st.selectbox("Select Group:", list(GROUPS.keys()))
selection = st.selectbox("Select Region:", REGIONS)
search_query = st.text_input("Search competitor (leave blank for all):").strip().lower()
go = st.button("Go")

if go:
    with st.spinner("Loading..."):
        raw, has_results = gather_data(selected_group, selection)
        data = dedupe_and_rank(raw)
        sheet_df = fetch_sheet(GROUPS[selected_group]["sheet_url"])

    if not has_results:
        st.warning("No standings data found for that selection.")
    else:
        for ev in EVENT_NAMES:
            rows = data[ev]
            if search_query:
                rows = [r for r in rows if search_query in r["Name"].lower()]
            if not rows:
                continue

            st.subheader(ev)

            if not is_mobile:
                # Desktop: table with inline expanders
                cols_h = st.columns([1,4,2,1])
                cols_h[0].write("Rank"); cols_h[1].write("Name")
                cols_h[2].write("Location"); cols_h[3].write("Points")

                for r in rows:
                    c = st.columns([1,4,2,1])
                    c[0].write(r["Rank"])
                    with c[1].expander(r["Name"]):
                        if ev in sheet_df.columns:
                            comp = sheet_df[(sheet_df['Name'].str.lower()==r["Name"].lower())&(sheet_df[ev]>0)]
                            if not comp.empty:
                                st.dataframe(comp[['Date','Tournament','Type',ev]].rename(columns={ev:'Points'}).reset_index(drop=True), use_container_width=True)
                            else:
                                st.write("No points in sheet.")
                        else:
                            st.write("No sheet data.")
                    c[2].write(r["Location"]); c[3].write(r["Points"])
            else:
                # Mobile: simple table + expanders under each event
                df_main = pd.DataFrame(rows)[["Rank","Name","Location","Points"]]
                st.dataframe(df_main.reset_index(drop=True), use_container_width=True)

                if ev in sheet_df.columns:
                    for r in rows:
                        comp = sheet_df[(sheet_df['Name'].str.lower()==r["Name"].lower())&(sheet_df[ev]>0)]
                        if not comp.empty:
                            with st.expander(f"{r['Name']} — Breakdown"):
                                st.dataframe(comp[['Date','Tournament','Type',ev]].rename(columns={ev:'Points'}).reset_index(drop=True), use_container_width=True)
