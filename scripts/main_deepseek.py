import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import os
from datetime import datetime
import time
import glob

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', 'fleet'))
DATA_FILES = sorted(glob.glob(os.path.join(DATA_DIR, 'vessel_data_*.json')))

def get_timestamp_from_filename(filename):
    try:
        ts_str = os.path.basename(filename).split('_')[-1].split('.')[0]
        ts_str = ts_str.replace('T', '')  # Handle both formats
        return datetime.strptime(ts_str, '%Y%m%d%H%M%S%fZ')
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
        return datetime.now()

def load_vessel_data(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        if 'data' in data and 'vessels' in data['data']:
            return data['data']
        elif 'vessels' in data:
            return data
        return {'vessels': []}
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {'vessels': []}

def create_vessel_map(vessel_data, zoom_level=2):
    m = folium.Map(location=[30, 0], zoom_start=zoom_level, control_scale=True)
    
    vessels_added = 0
    for vessel in vessel_data.get('vessels', []):
        try:
            lat = vessel.get('lat')
            lon = vessel.get('lon')
            if lat is None or lon is None:
                continue
                
            # Safely check type_specific
            type_specific = vessel.get('type_specific', '')
            icon_color = 'red' if type_specific and "LNG Tanker" in type_specific else \
                       'blue' if type_specific and "Floating Storage" in type_specific else 'green'
            
            popup_text = f"""
            <b>Name:</b> {vessel.get('name', 'N/A')}<br>
            <b>Type:</b> {type_specific}<br>
            <b>Status:</b> {vessel.get('navigation_status', 'N/A')}<br>
            <b>Position:</b> {lat:.4f}, {lon:.4f}
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_text, max_width=250),
                icon=folium.Icon(color=icon_color, icon='ship', prefix='fa')
            ).add_to(m)
            vessels_added += 1
        except Exception as e:
            print(f"Error creating marker: {e}")
    
    print(f"Added {vessels_added} markers to map")
    return m

def main():
    st.set_page_config(layout="wide", page_title="FSRU Vessel Timeline")
    
    # Initialize session state
    if 'playing' not in st.session_state:
        st.session_state.playing = False
    if 'speed' not in st.session_state:
        st.session_state.speed = 1.0
    if 'current_file_idx' not in st.session_state:
        st.session_state.current_file_idx = 0
    if 'zoom_level' not in st.session_state:
        st.session_state.zoom_level = 2  # Default zoom level
    
    st.title("FSRU Vessel Timeline Visualization")
    
    # Debug info
    with st.sidebar:
        st.write(f"Files found: {len(DATA_FILES)}")
        if DATA_FILES:
            st.write(f"Current file: {os.path.basename(DATA_FILES[st.session_state.current_file_idx])}")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.header("Timeline Controls")
        
        if not DATA_FILES:
            st.error("No data files found!")
            return
            
        file_labels = [get_timestamp_from_filename(f).strftime("%Y-%m-%d %H:%M:%S") for f in DATA_FILES]
        
        selected_idx = st.select_slider(
            "Select timeline position",
            options=list(range(len(DATA_FILES))),
            value=st.session_state.current_file_idx,
            format_func=lambda x: file_labels[x]
        )
        
        if selected_idx != st.session_state.current_file_idx:
            st.session_state.current_file_idx = selected_idx
            st.session_state.playing = False
        
        col1a, col1b = st.columns(2)
        with col1a:
            if st.button("▶ Play" if not st.session_state.playing else "❚❚ Pause"):
                st.session_state.playing = not st.session_state.playing
        with col1b:
            if st.button("⏹ Stop"):
                st.session_state.playing = False
                st.session_state.current_file_idx = 0
        
        st.session_state.speed = st.slider(
            "Playback speed",
            min_value=0.5,
            max_value=5.0,
            value=st.session_state.speed,
            step=0.5
        )
        
        # Zoom controls
        st.session_state.zoom_level = st.slider(
            "Map Zoom Level",
            min_value=1,
            max_value=10,
            value=st.session_state.zoom_level,
            step=1
        )
    
    with col2:
        if DATA_FILES:
            vessel_data = load_vessel_data(DATA_FILES[st.session_state.current_file_idx])
            timestamp = get_timestamp_from_filename(DATA_FILES[st.session_state.current_file_idx])
            
            st.subheader(f"Vessel Positions at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            st.sidebar.write(f"Vessels loaded: {len(vessel_data.get('vessels', []))}")
            
            vessel_map = create_vessel_map(vessel_data, st.session_state.zoom_level)
            st_folium(
                vessel_map,
                width=800,
                height=600,
                returned_objects=[]
            )
    
    # Auto-play functionality using st.rerun() instead of experimental_rerun()
    if st.session_state.playing and DATA_FILES:
        time.sleep(1.0 / st.session_state.speed)
        if st.session_state.current_file_idx < len(DATA_FILES) - 1:
            st.session_state.current_file_idx += 1
            st.rerun()
        else:
            st.session_state.playing = False
            st.rerun()

if __name__ == "__main__":
    main()