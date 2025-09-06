import streamlit as st
import pandas as pd
import requests

st.title("ATA W01D & W23C Standings")

# Ask if mobile or desktop
is_mobile = st.radio("Are you on a mobile device?", ["No", "Yes"]) == "Yes"

# Group selection
group = st.selectbox(
    "Select Group",
    ["1st Degree Black Belt 50-59", "2nd/3rd Degree Black Belt Women 40-49"]
)

# Region selection
region = st.selectbox(
    "Select Region",
    ["World", "State/Province"]
)

# Name search
search_name = st.text_input("Search by Competitor Name (optional)").strip().lower()

# URLs for both groups
urls = {
    "1st Degree Black Belt 50-59": {
        "world": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W01D",
        "state": "https://atamartialarts.com/events/tournament-standings/state-standings/?country=US&state=ga&code=W01D",
        "sheet": "https://docs.google.com/spreadsheets/d/1fZlnlXvYB6sGk92l8xQdVNhhlQ1WtYl9lMyRj4i77hc/export?format=csv"
    },
    "2nd/3rd Degree Black Belt Women 40-49": {
        "world": "https://atamartialarts.com/events/tournament-standings/worlds-standings/?code=W23C",
        "state": "https://atamartialarts.com/events/tournament-standings/state-standings/?country=US&state=ga&code=W23C",
        "sheet": "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv"
    }
}

# Select correct URLs
urls_group = urls[group]
url = urls_group["world"] if region == "World" else urls_group["state"]

# Load competitor data from ATA
tables = pd.read_html(url)
df = tables[0]

# Load points breakdown from Google Sheet
sheet_df = pd.read_csv(urls_group["sheet"])
events = [col for col in sheet_df.columns if col not in ["Name", "Location", "Type", "Total"]]

# Add Total column if missing
if "Total" not in sheet_df.columns:
    sheet_df["Total"] = sheet_df[events].sum(axis=1)

# Merge by name ignoring case
df["Name_lower"] = df["Name"].str.lower()
sheet_df["Name_lower"] = sheet_df["Name"].str.lower()
df = df.merge(sheet_df, on="Name_lower", how="left", suffixes=("", "_sheet"))

# Rank handling with ties
df["Rank"] = df["Points"].rank(method="min", ascending=False).astype(int)

# Apply search filter
if search_name:
    df = df[df["Name"].str.lower().str.contains(search_name)]

# Display differently for mobile vs desktop
if is_mobile:
    # MOBILE VERSION
    st.subheader(f"{group} - {region}")
    for ev in events:
        st.markdown(f"### {ev}")
        ev_df = df[["Rank", "Name", "Location", ev]].dropna()
        ev_df = ev_df.rename(columns={ev: "Points"})
        st.table(ev_df[["Rank", "Name", "Location", "Points"]])

        # Show breakdown per competitor
        for _, row in ev_df.iterrows():
            comp_data = sheet_df[
                (sheet_df["Name"].str.lower() == row["Name"].lower()) &
                (sheet_df[ev] > 0)
            ][["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
            if not comp_data.empty:
                st.markdown(f"**{row['Name']} – {ev} Breakdown:**")
                st.table(comp_data.reset_index(drop=True))
else:
    # DESKTOP VERSION
    st.subheader(f"{group} - {region}")
    for ev in events:
        st.markdown(f"### {ev}")
        ev_df = df[["Rank", "Name", "Location", ev]].dropna()
        ev_df = ev_df.rename(columns={ev: "Points"})
        ev_df = ev_df.sort_values("Rank")

        # Display in columns
        for _, row in ev_df.iterrows():
            cols = st.columns([2, 1, 2, 1])
            cols[0].write(row["Rank"])
            cols[1].write(row["Name"])
            cols[2].write(row["Location"])
            cols[3].write(int(row["Points"]))

            # Dropdown for breakdown (no index column, includes Type)
            with cols[1].expander(row["Name"]):
                comp_data = sheet_df[
                    (sheet_df["Name"].str.lower() == row["Name"].lower()) &
                    (sheet_df[ev] > 0)
                ][["Date", "Tournament", ev, "Type"]].rename(columns={ev: "Points"})
                if not comp_data.empty:
                    st.table(comp_data.reset_index(drop=True))
