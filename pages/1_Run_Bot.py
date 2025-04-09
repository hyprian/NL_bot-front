# front-engagement-bot/pages/1_Run_Bot.py
import streamlit as st
import requests
import time
import json
import logging # Optional: for frontend logging

# --- Configuration ---
BOT_API_URL = st.secrets.get("BOT_API_URL", None)
API_KEY = st.secrets.get("BOT_API_KEY", None)
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}
STATUS_REFRESH_INTERVAL_ACTIVE = 5 # Seconds
STATUS_REFRESH_INTERVAL_IDLE = 30 # Seconds

# --- Initialize Session State ---
if 'bot_api_status' not in st.session_state:
    st.session_state.bot_api_status = {"state": "unknown", "details": "Connecting...", "last_update": None}
if 'last_status_fetch_time' not in st.session_state:
    st.session_state.last_status_fetch_time = 0

# --- Helper Functions ---
def send_control_command(action):
    """Sends 'start' or 'stop' command to the backend API."""
    if not BOT_API_URL: return None, "BOT_API_URL not set."
    api_endpoint = f"{BOT_API_URL}/control"
    payload = {"action": action}
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass # Ignore errors getting details from response
        logging.error(f"API Control Error: {e}")
        return None, f"API Error: {error_detail}"
    except json.JSONDecodeError:
        logging.error("API Control Error: Invalid JSON response")
        return None, "Invalid JSON response from API."

def fetch_status_from_api():
    """Fetches the current bot status from the backend API."""
    if not BOT_API_URL:
        st.session_state.bot_api_status = {"state": "error", "details": "BOT_API_URL not set.", "last_update": time.time()}
        return False

    api_endpoint = f"{BOT_API_URL}/status"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        new_status = response.json()
        if isinstance(new_status, dict) and 'state' in new_status:
             st.session_state.bot_api_status = new_status
             st.session_state.last_status_fetch_time = time.time()
             logging.debug(f"Status fetched: {new_status}")
             return True
        else:
             st.session_state.bot_api_status = {"state": "error", "details": f"Invalid status format: {new_status}", "last_update": time.time()}
             logging.error(f"Invalid status format from API: {new_status}")
             return False
    except requests.exceptions.RequestException as e:
        error_prefix = f"({time.strftime('%H:%M:%S')}) Status Fetch Failed: "
        error_msg = f"{error_prefix}{type(e).__name__}"
        logging.warning(f"Status Fetch Failed: {e}")
        st.session_state.bot_api_status["details"] = error_msg # Update details without losing last state
        # Optionally set state to 'error' or keep previous state? Let's set to error for clarity.
        st.session_state.bot_api_status["state"] = "error"
        st.session_state.last_status_fetch_time = time.time() # Record fetch attempt time
        return False
    except json.JSONDecodeError:
         st.session_state.bot_api_status = {"state": "error", "details": "Invalid JSON status from API.", "last_update": time.time()}
         logging.error("Invalid JSON status from API.")
         return False

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Run Bot (Remote)")
st.title("🚀 Run Engagement Bot (Remote Control)")
st.caption("Start, stop, and monitor the bot running on the local machine.")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Configure logging

# --- Check API Config ---
if not BOT_API_URL: st.error("🚨 Critical Error: BOT_API_URL secret is not set."); st.stop()
if not API_KEY: st.warning("⚠️ Warning: BOT_API_KEY secret not set.")

# --- Fetch Status Update ---
now = time.time()
current_state = st.session_state.bot_api_status.get("state", "unknown")
refresh_interval = STATUS_REFRESH_INTERVAL_ACTIVE if current_state in ["running", "starting", "stopping"] else STATUS_REFRESH_INTERVAL_IDLE
needs_refresh = (now - st.session_state.last_status_fetch_time) > refresh_interval

if needs_refresh or current_state == "unknown":
    with st.spinner("Checking bot status..."):
        fetch_status_from_api()
        # Update current_state after fetch attempt
        current_state = st.session_state.bot_api_status.get("state", "unknown")


# --- Control Buttons ---
st.subheader("Bot Controls")
col1, col2 = st.columns(2)
with col1:
    run_disabled = current_state not in ["idle", "error", "stopped"]
    if st.button("▶️ Run Engagement Bot", disabled=run_disabled, use_container_width=True, type="primary" if not run_disabled else "secondary"):
        with st.spinner("Sending 'start' command..."):
             result, error = send_control_command("start")
             if error: st.error(f"Failed to start bot: {error}")
             else: st.success(result.get("message", "Start command sent.")); time.sleep(1)
        # Trigger immediate status fetch and rerun
        fetch_status_from_api()
        st.rerun()

with col2:
    stop_disabled = current_state not in ["running", "starting"]
    if st.button("⏹️ Stop Bot", disabled=stop_disabled, use_container_width=True):
        with st.spinner("Sending 'stop' command..."):
            result, error = send_control_command("stop")
            if error: st.error(f"Failed to stop bot: {error}")
            else: st.warning(result.get("message", "Stop command sent.")); time.sleep(1)
        # Trigger immediate status fetch and rerun
        fetch_status_from_api()
        st.rerun()

# --- Display Bot Status ---
st.subheader("🤖 Bot Status")
status_placeholder = st.container() # Use container for better element placement

with status_placeholder:
    status_data = st.session_state.bot_api_status
    state_display = status_data.get('state', 'N/A').upper()
    details_display = status_data.get('details', 'N/A')
    last_update_ts = status_data.get('last_update') # Timestamp from backend

    if last_update_ts:
         last_update_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update_ts))
         status_line = f"**Status:** `{state_display}` (Updated: {last_update_str})"
    else:
         status_line = f"**Status:** `{state_display}`"

    if state_display == "RUNNING": st.info(status_line)
    elif state_display == "IDLE" or state_display == "STOPPED": st.success(status_line)
    elif state_display == "ERROR": st.error(status_line)
    elif state_display in ["STARTING", "STOPPING"]: st.warning(status_line)
    else: st.info(status_line) # Unknown or connecting state

    # Display details below the status line
    st.caption(f"Details: {details_display}")

    # Add a manual refresh button
    if st.button("🔄 Refresh Status"):
         with st.spinner("Refreshing..."):
              fetch_status_from_api()
              st.rerun()


# --- Auto-refresh Logic ---
# This ensures the page periodically checks for updates
st.caption(f"Auto-refreshing status every {refresh_interval}s...")
time.sleep(refresh_interval)
st.rerun()