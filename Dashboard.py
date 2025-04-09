# front-engagement-bot/Dashboard.py (Corrected)
import streamlit as st
import requests
import json
import datetime
import re
import pandas as pd
import time
import logging # <<< --- ADDED IMPORT --- >>>

# --- Basic Logging Setup ---
# Moved to top after imports
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
BOT_API_URL = st.secrets.get("BOT_API_URL", None)
API_KEY = st.secrets.get("BOT_API_KEY", None)
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}

# --- Helper Functions ---

@st.cache_data(ttl=60)
def fetch_history_data_from_api():
    """Fetches the history data from the backend API."""
    if not BOT_API_URL:
        st.error("🚨 BOT_API_URL secret is not configured.")
        return None

    api_endpoint = f"{BOT_API_URL}/history"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'profiles' in data and isinstance(data['profiles'], dict):
            # Use logging correctly now
            logging.info(f"Successfully fetched history data for {len(data['profiles'])} profiles.")
            return data['profiles']
        else:
            st.error(f"API Error: Unexpected history data format received.")
            # Use logging correctly now
            logging.error(f"Unexpected history format from API: {data}")
            return None
    except requests.exceptions.ConnectionError:
         st.error(f"Connection Error: Could not connect to backend API at `{BOT_API_URL}`.")
         return None
    except requests.exceptions.Timeout:
         st.error(f"Timeout Error: Request to `{api_endpoint}` timed out.")
         return None
    except requests.exceptions.HTTPError as e:
         error_detail = ""
         try: error_detail = response.json().get("error", response.text)
         except: error_detail = response.text
         st.error(f"HTTP Error {response.status_code}: Failed to fetch history. API Message: {error_detail}")
         return None
    except requests.exceptions.RequestException as e:
         st.error(f"Request Error: An unexpected error occurred fetching history: {e}")
         return None
    except json.JSONDecodeError:
        st.error(f"JSON Decode Error: Could not parse the history response from the API.")
        return None

def get_combined_history(profiles_data):
    # (Implementation remains the same)
    all_actions = []
    if not profiles_data: return all_actions
    for profile_id, data in profiles_data.items():
        actions = data.get('actions', [])
        for action in actions:
            action_copy = action.copy(); action_copy['profile_id'] = profile_id
            all_actions.append(action_copy)
    return all_actions

def filter_actions_by_time(actions, days):
    # (Implementation remains the same)
    if not actions: return []
    filtered_actions = []
    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(days=days)
    for action in actions:
        try:
            timestamp_str = action.get('timestamp')
            if not timestamp_str: continue
            timestamp_str = timestamp_str.replace('Z', '+00:00')
            try: timestamp_dt = datetime.datetime.fromisoformat(timestamp_str)
            except ValueError:
                 try: timestamp_dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
                 except ValueError: timestamp_dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            if timestamp_dt.tzinfo: cutoff_time = cutoff_time.replace(tzinfo=timestamp_dt.tzinfo)
            else: timestamp_dt = timestamp_dt.replace(tzinfo=None)
            if timestamp_dt >= cutoff_time: filtered_actions.append(action)
        except (ValueError, TypeError, KeyError) as e:
             # Use logging correctly now
             logging.debug(f"Skipping action due to timestamp parse error: {e}, Action: {action}")
             continue
    return filtered_actions


def display_action_details(details):
    # (Implementation remains the same)
    url_pattern = re.compile(r'https?://\S+')
    urls_found = url_pattern.findall(details)
    if urls_found:
        url = urls_found[0]; text_part = details.replace(url, "").strip()
        if text_part.endswith(':'): text_part = text_part[:-1].strip()
        if text_part: st.write(f"{text_part}:")
        display_url = url[:60] + "..." if len(url) > 60 else url
        with st.expander(f"Link: `{display_url}`"):
             st.markdown(f"[{url}]({url})", unsafe_allow_html=True)
    else: st.write(details)

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Bot History (Remote)")

st.title("📊 Remote Engagement Bot Dashboard")
st.header("📜 Profile Action History")
st.caption(f"Data fetched from backend API: `{BOT_API_URL}`")

# --- Check API Config ---
if not BOT_API_URL:
    st.error("🚨 Critical Error: BOT_API_URL secret is not set in Streamlit deployment.")
    st.info("Please configure the BOT_API_URL secret in your Streamlit Cloud settings or environment variables.")
    st.stop()
if not API_KEY:
    st.warning("⚠️ Warning: BOT_API_KEY secret is not set. Ensure the backend API does not require authentication.")

# --- Load Data ---
profiles_data = fetch_history_data_from_api()

if profiles_data is None:
    st.warning("Could not load history data from the backend API.")
    st.info("Check the API server logs on the local machine and ensure the tunnel is active.")
    st.stop()
elif not profiles_data:
     st.info("No history data found in the backend.")
else:
    st.success(f"Loaded history for {len(profiles_data)} profiles.")

# --- Sidebar Controls ---
st.sidebar.header("History View Controls")
view_mode = st.sidebar.radio("View Mode:", ('Single Profile', 'All Profiles'), key='view_mode', horizontal=True)
st.sidebar.markdown("---")

profile_ids = sorted(list(profiles_data.keys())) if profiles_data else []
profile_display_names = {}
for pid in profile_ids:
    profile_info = profiles_data.get(pid, {}).get('profile_info', {})
    name = profile_info.get('name', 'N/A')
    serial_number = profile_info.get('serial_number', 'N/A')
    profile_display_names[pid] = f"{pid} ({name}, SN: {serial_number})"

if view_mode == 'Single Profile':
    st.sidebar.subheader("Single Profile Filter")
    if not profile_ids:
         st.sidebar.warning("No profiles found in history.")
         selected_profile_id = None
    else:
        if 'history_selected_profile_id' not in st.session_state or st.session_state.history_selected_profile_id not in profile_ids:
             st.session_state.history_selected_profile_id = profile_ids[0]
        selected_profile_id = st.sidebar.selectbox("Select Profile:", options=profile_ids, format_func=lambda pid: profile_display_names.get(pid, pid), key='history_selected_profile_id')
else:
    st.sidebar.subheader("All Profiles View")
    st.sidebar.info("Showing combined history for all profiles.")
    selected_profile_id = None

st.sidebar.subheader("Time Filter")
time_filter_option = st.sidebar.radio("Filter:", ('All History', 'Past 7 Days'), key='history_time_filter', horizontal=True)
st.sidebar.divider()
st.sidebar.info("Use sidebar navigation (top left) for other pages.")

# --- Main Content Area ---
actions_to_display = []
if view_mode == 'Single Profile':
    if selected_profile_id and profiles_data and selected_profile_id in profiles_data:
        profile_data = profiles_data[selected_profile_id]
        profile_info = profile_data.get('profile_info', {})
        name = profile_info.get('name', 'N/A')
        serial_number = profile_info.get('serial_number', 'N/A')
        st.caption(f"Displaying history for profile: **{selected_profile_id}**")
        st.markdown(f"**Name:** `{name}` | **Serial #:** `{serial_number}`")
        actions_to_display = profile_data.get('actions', [])
        with st.expander("Show Full Profile Information"): st.json(profile_info)
        st.divider()
    elif selected_profile_id:
         st.warning("Selected profile not found in the current history data.")
    else:
         st.info("Select a profile from the sidebar.")

elif view_mode == 'All Profiles':
    if not profiles_data:
         st.info("No history data available to combine.")
    else:
        st.caption("Displaying combined history for **all profiles**.")
        actions_to_display = get_combined_history(profiles_data)
        st.divider()
else: st.error("Invalid view mode.")

filter_desc = ""
if time_filter_option == 'Past 7 Days':
    actions_to_display = filter_actions_by_time(actions_to_display, days=7)
    filter_desc = " (Past 7 Days)"
else: filter_desc = " (All Time)"

if not actions_to_display:
    st.info(f"No actions found for the selected criteria{filter_desc}.")
else:
    actions_to_display.sort(key=lambda x: x.get('timestamp', '0'), reverse=True)
    st.write(f"**Total actions displayed: {len(actions_to_display)}**{filter_desc}")
    st.markdown("---")

    # Define columns based on view mode
    if view_mode == 'All Profiles':
        col_ts, col_pid, col_snum, col_type, col_details = st.columns([0.2, 0.12, 0.1, 0.13, 0.45])
        # <<< --- FIXED SYNTAX --- >>>
        with col_ts:
            st.caption("**Timestamp**")
        with col_pid:
            st.caption("**Profile ID**")
        with col_snum:
             st.caption("**Serial #**")
        with col_type:
            st.caption("**Action Type**")
        with col_details:
            st.caption("**Details**")
        st.markdown("---", unsafe_allow_html=True) # Header line
    else: # Single Profile view
        col_ts, col_type, col_details = st.columns([0.3, 0.15, 0.55])
        # <<< --- FIXED SYNTAX --- >>>
        with col_ts:
            st.caption("**Timestamp**")
        with col_type:
            st.caption("**Action Type**")
        with col_details:
            st.caption("**Details**")
        st.markdown("---", unsafe_allow_html=True) # Header line

    # Display actions row by row
    for action in actions_to_display:
        timestamp = action.get('timestamp', 'N/A')
        action_type = action.get('action_type', 'N/A')
        details = action.get('details', 'N/A')
        if view_mode == 'All Profiles':
            profile_id_for_action = action.get('profile_id', 'N/A')
            profile_info = profiles_data.get(profile_id_for_action, {}).get('profile_info', {})
            serial_number = profile_info.get('serial_number', 'N/A')
            col_ts, col_pid, col_snum, col_type, col_details = st.columns([0.2, 0.12, 0.1, 0.13, 0.45])
            # <<< --- FIXED SYNTAX --- >>>
            with col_ts:
                st.markdown(f"`{timestamp}`")
            with col_pid:
                st.code(profile_id_for_action)
            with col_snum:
                st.code(serial_number)
            with col_type:
                st.markdown(f"**{action_type.upper()}**")
            with col_details:
                display_action_details(details)
        else: # Single Profile view
            col_ts, col_type, col_details = st.columns([0.3, 0.15, 0.55])
            # <<< --- FIXED SYNTAX --- >>>
            with col_ts:
                st.markdown(f"`{timestamp}`")
            with col_type:
                st.markdown(f"**{action_type.upper()}**")
            with col_details:
                display_action_details(details)
        st.markdown("---") # Separator between actions