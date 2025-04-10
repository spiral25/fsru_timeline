import streamlit as st
import pydeck as pdk
import pandas as pd
import glob
import os
import json
import math
from datetime import datetime

def get_datetime_from_filename(file_path):
    filename = os.path.basename(file_path)  # e.g. 'vessel_data_20250408T140312Z.json'
    time_str = filename[len("vessel_data_") : -len(".json")]
    return datetime.strptime(time_str, "%Y%m%dT%H%M%SZ")

def load_vessel_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data["data"]["vessels"]

def haversine_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    r = 3958.8  # Radius of Earth in miles
    return c * r

def main():
    st.title("FSRU Timeline Viewer")

    # Go one directory up from this file to find 'fleet'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    fleet_dir = os.path.join(project_root, "fleet")

    # Debugging info
    st.write(f"**Script Directory (scripts)**: {script_dir}")
    st.write(f"**Project Root**: {project_root}")
    st.write(f"**Fleet Directory**: {fleet_dir}")

    # List what's inside 'fleet_dir'
    if os.path.exists(fleet_dir):
        st.write("**Contents of 'fleet' folder**:", os.listdir(fleet_dir))
    else:
        st.error("Fleet directory does not exist. Make sure it is located at the same level as 'scripts'.")
        st.stop()

    file_pattern = os.path.join(fleet_dir, "vessel_data_*.json")
    file_paths = glob.glob(file_pattern)

    if not file_paths:
        st.warning("No vessel_data_*.json files found in the specified directory.")
        st.stop()

    # Sort JSON files by timestamp in their filenames
    timeline_files = []
    for path in file_paths:
        file_dt = get_datetime_from_filename(path)
        timeline_files.append((file_dt, path))
    timeline_files.sort(key=lambda x: x[0])

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

    vessels = load_vessel_data(selected_file)
    df = pd.DataFrame(vessels)
    df.rename(columns={'lat': 'latitude', 'lon': 'longitude'}, inplace=True)

    # Compare current vessel positions with previous snapshot
    if 'prev_vessel_data' not in st.session_state:
        st.session_state.prev_vessel_data = vessels
        st.session_state.prev_index = selected_index
        changed_vessel_names = []
    else:
        if st.session_state.prev_index != selected_index:
            previous_data = st.session_state.prev_vessel_data
            prev_positions = {
                v['name']: (v.get('lat'), v.get('lon')) for v in previous_data
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
                            if dist > 5:
                                changed_vessel_names.append(name)
                    else:
                        changed_vessel_names.append(name)
            st.session_state.prev_vessel_data = vessels
            st.session_state.prev_index = selected_index
        else:
            changed_vessel_names = []

    # Sidebar for changed vessels
    st.sidebar.header("Vessels with >5 Miles Change")
    if changed_vessel_names:
        for name in changed_vessel_names:
            st.sidebar.write(name)
    else:
        st.sidebar.write("No significant changes detected")

    # Mark moved vessels in the DataFrame
    df['moved'] = df['name'].apply(lambda x: x in changed_vessel_names)
    df['marker_color'] = df['moved'].apply(lambda moved: [255, 215, 0, 200] if moved else [200, 30, 0, 160])
    df['marker_radius'] = df['moved'].apply(lambda moved: 150000 if moved else 100000)

    # Render a pydeck map
    if not df.empty:
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
