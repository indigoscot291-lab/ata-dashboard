# --- STREAMLIT APP (mobile-friendly, no index) ---
st.title("ATA W01D Standings")

sheet_df = fetch_sheet()
selection = st.selectbox("Select region:", REGIONS)
go = st.button("Go")

if go:
    with st.spinner("Loading standings..."):
        raw, has_results = gather_data(selection)
        data = dedupe_and_rank(raw)

    if not has_results:
        if selection in REGION_CODES:
            st.warning(f"There are no 50‑59 1st Degree Women for {selection}.")
        elif selection == "International":
            st.warning("There are no 50‑59 1st Degree Women for International.")
        else:
            st.warning("No standings data found for this selection.")
    else:
        for ev in EVENT_NAMES:
            rows = data.get(ev, [])
            if rows:
                st.subheader(ev)
                # Scrollable container for mobile
                with st.container():
                    # Table header
                    cols_header = st.columns([1,4,1,2], gap="small")
                    cols_header[0].write("Rank")
                    cols_header[1].write("Name")
                    cols_header[2].write("Points")
                    cols_header[3].write("Location")
                    # Table rows
                    for row in rows:
                        cols = st.columns([1,4,1,2], gap="small")
                        cols[0].write(row["Rank"])
                        # Name clickable using expander
                        with cols[1].expander(row["Name"]):
                            comp_data = sheet_df[
                                (sheet_df['Name'].str.lower() == row['Name'].lower()) &
                                (sheet_df[ev] > 0)
                            ][["Date","Tournament","Type",ev]].rename(columns={ev:"Points"})
                            if not comp_data.empty:
                                st.dataframe(comp_data.style.hide_index(), use_container_width=True)
                            else:
                                st.write("No tournament data for this event.")
                        cols[2].write(row["Points"])
                        cols[3].write(row["Location"])
else:
    st.info("Select a region or 'International' and click Go to view standings.")
