import streamlit as st
import pydeck as pdk
import pandas as pd
import glob
import os
import json
import math
from datetime import datetime

# --------------------------------------------------------------------
# Helper function to parse datetime from filenames such as:
#   vessel_data_20250408T140312Z.json
# --------------------------------------------------------------------
def get_datetime_from_filename(file_path):
    """
    Extract datetime from filenames in the format:
    vessel_data_YYYYmmddTHHMMSSZ.json
    """
    filename = os.path.basename(file_path)  # e.g. 'vessel_data_20250408T140312Z.json'
    # Remove the prefix 'vessel_data_' and the suffix '.json'
    time_str = filename[len("vessel_data_") : -len(".json")]
    # Convert the string into a Python datetime object
    return datetime.strptime(time_str, "%Y%m%dT%H%M%SZ")

# --------------------------------------------------------------------
# Helper function to load the vessel data from a single JSON file
# --------------------------------------------------------------------
def load_vessel_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Typically, the vessels are found under data["data"]["vessels"]
    return data["data"]["vessels"]

# --------------------------------------------------------------------
# Helper function to compute the distance between two coordinates in miles using the Haversine formula.
# --------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians.
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    # Haversine formula calculation.
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    r = 3958.8  # Radius of Earth in miles.
    return c * r

# --------------------------------------------------------------------
# Main Streamlit app
# --------------------------------------------------------------------
def main():
    st.title("FSRU Timeline Viewer")

    # 1. Collect all JSON files in the target directory.
    fleet_dir = r"C:\Dev\fsru_timeline\fleet"
    file_pattern = os.path.join(fleet_dir, "vessel_data_*.json")
    file_paths = glob.glob(file_pattern)

    if not file_paths:
        st.warning("No vessel_data_*.json files found in the specified directory.")
        return

    # 2. Extract datetime from each file, then sort them chronologically.
    timeline_files = []
    for path in file_paths:
        file_dt = get_datetime_from_filename(path)
        timeline_files.append((file_dt, path))
    timeline_files.sort(key=lambda x: x[0])

    # 3. Create a slider to pick which file/timestamp to use.
    times = [item[0] for item in timeline_files]
    selected_index = st.slider(
        "Select a time index",
        min_value=0,
        max_value=len(times) - 1,
        value=0,
        format="Index: %d"
    )
    selected_dt, selected_file = timeline_files[selected_index]
    st.write(f"**Selected timestamp**: {selected_dt.isoformat()}")

    # 4. Load vessel data from the selected file and create a DataFrame.
    vessels = load_vessel_data(selected_file)
    df = pd.DataFrame(vessels)
    df.rename(columns={'lat': 'latitude', 'lon': 'longitude'}, inplace=True)

    # ----------------------------------------------------------------
    # Compare current vessel positions with the previous snapshot if available.
    # We store the previous slider index and vessel data in session_state.
    # ----------------------------------------------------------------
    if 'prev_vessel_data' not in st.session_state:
        # First run: initialize session state values.
        st.session_state.prev_vessel_data = vessels
        st.session_state.prev_index = selected_index
        changed_vessel_names = []
    else:
        if st.session_state.prev_index != selected_index:
            previous_data = st.session_state.prev_vessel_data
            # Build a dictionary mapping vessel names to (latitude, longitude) tuples.
            prev_positions = {
                vessel['name']: (vessel.get('lat'), vessel.get('lon'))
                for vessel in previous_data
            }
            changed_vessel_names = []
            for vessel in vessels:
                name = vessel['name']
                current_lat = vessel.get('lat')
                current_lon = vessel.get('lon')
                if current_lat is not None and current_lon is not None:
                    if name in prev_positions:
                        prev_lat, prev_lon = prev_positions[name]
                        if prev_lat is not None and prev_lon is not None:
                            dist = haversine_distance(prev_lat, prev_lon, current_lat, current_lon)
                            # Consider the vessel moved if distance > 5 miles.
                            if dist > 5:
                                changed_vessel_names.append(name)
                    else:
                        # Vessel is new in the current snapshot.
                        changed_vessel_names.append(name)
            # Update session state with current snapshot details.
            st.session_state.prev_vessel_data = vessels
            st.session_state.prev_index = selected_index
        else:
            changed_vessel_names = []

    # ----------------------------------------------------------------
    # Display the names of vessels with changed positions on the sidebar.
    # ----------------------------------------------------------------
    st.sidebar.header("Vessels with >5 Miles Change")
    if changed_vessel_names:
        for name in changed_vessel_names:
            st.sidebar.write(name)
    else:
        st.sidebar.write("No significant changes detected")

    # ----------------------------------------------------------------
    # Update DataFrame to mark and style vessels that have moved.
    # Add a "moved" column which is True if the vessel has moved >5 miles.
    # Also add columns for marker_color and marker_radius.
    # ----------------------------------------------------------------
    df['moved'] = df['name'].apply(lambda x: x in changed_vessel_names)
    # Set bright gold for moved vessels, default red for others.
    df['marker_color'] = df['moved'].apply(lambda moved: [255, 215, 0, 200] if moved else [200, 30, 0, 160])
    # Increase the size for moved vessels.
    df['marker_radius'] = df['moved'].apply(lambda moved: 150000 if moved else 100000)

    # 5. Render a map of the vessels using pydeck.
    if not df.empty:
        # Define a basic world view (centered around latitude 20, longitude 0)
        view_state = pdk.ViewState(latitude=20, longitude=0, zoom=2)
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            pickable=True,
            get_position='[longitude, latitude]',
            get_color='marker_color',
            get_radius='marker_radius'
        )
        tooltips = {
            "html": (
                "<b>Name:</b> {name} <br/>"
                "<b>Type:</b> {type_specific} <br/>"
                "<b>Status:</b> {navigation_status} <br/>"
                "<b>Country:</b> {country_iso}"
            )
        }
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltips)
        st.pydeck_chart(r)
    else:
        st.warning("No vessel data found in the selected file.")

if __name__ == "__main__":
    main()
