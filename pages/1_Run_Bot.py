# front-engagement-bot/pages/1_Run_Bot.py (Complete with Log Display)
import streamlit as st
import requests
import time
import json
import logging

# --- Configuration ---
BOT_API_URL = st.secrets.get("BOT_API_URL", None)
API_KEY = st.secrets.get("BOT_API_KEY", None)
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}
STATUS_REFRESH_INTERVAL_ACTIVE = 3 # Seconds
STATUS_REFRESH_INTERVAL_IDLE = 30 # Seconds

# --- Initialize Session State ---
if 'bot_api_status' not in st.session_state:
    st.session_state.bot_api_status = {"state": "unknown", "details": "Connecting...", "last_update": None}
if 'last_status_fetch_time' not in st.session_state:
    st.session_state.last_status_fetch_time = 0
if 'bot_logs' not in st.session_state:
    st.session_state.bot_logs = ["--- Waiting for bot connection ---"]

# --- Helper Functions ---
def send_control_command(action):
    if not BOT_API_URL: return None, "BOT_API_URL not set."
    api_endpoint = f"{BOT_API_URL}/control"; payload = {"action": action}
    try:
        response = requests.post(api_endpoint, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status(); return response.json(), None
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"; 
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass ; logging.error(f"API Control Error: {e}"); return None, f"API Error: {error_detail}"
    except json.JSONDecodeError: logging.error("API Control Error: Invalid JSON"); return None, "Invalid JSON response."

def fetch_status_from_api():
    if not BOT_API_URL: st.session_state.bot_api_status = {"state": "error", "details": "BOT_API_URL not set."}; return False
    api_endpoint = f"{BOT_API_URL}/status"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10); response.raise_for_status()
        new_status = response.json()
        if isinstance(new_status, dict) and 'state' in new_status:
             st.session_state.bot_api_status = new_status; st.session_state.last_status_fetch_time = time.time(); return True
        else: st.session_state.bot_api_status = {"state": "error", "details": f"Invalid status format: {new_status}"}; logging.error(f"Invalid status: {new_status}"); return False
    except requests.exceptions.RequestException as e:
        error_prefix = f"({time.strftime('%H:%M:%S')}) Status Fail: "; error_msg = f"{error_prefix}{type(e).__name__}"
        logging.warning(f"Status Fetch Fail: {e}"); st.session_state.bot_api_status["details"] = error_msg
        st.session_state.bot_api_status["state"] = "error"; st.session_state.last_status_fetch_time = time.time(); return False
    except json.JSONDecodeError: st.session_state.bot_api_status = {"state": "error", "details": "Invalid JSON status."}; logging.error("Invalid JSON status."); return False

def fetch_logs_from_api():
    if not BOT_API_URL: logging.error("Cannot fetch logs: BOT_API_URL not set."); return False
    api_endpoint = f"{BOT_API_URL}/logs"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'logs' in data and isinstance(data['logs'], list):
             st.session_state.bot_logs = data['logs'] # Replace logs with the latest batch
             logging.debug(f"Fetched {len(data['logs'])} log lines.")
             return True
        else:
             logging.error(f"Invalid logs format from API: {data}")
             st.session_state.bot_logs = ["--- Error fetching logs: Invalid format ---"]
             return False
    except requests.exceptions.RequestException as e:
        logging.warning(f"Logs Fetch Failed: {e}")
        # Add error to logs list instead of replacing?
        # st.session_state.bot_logs = [f"--- Error fetching logs: {type(e).__name__} ---"] + st.session_state.bot_logs[:100] # Keep some old logs
        return False
    except json.JSONDecodeError:
         logging.error("Invalid JSON logs response from API.")
         st.session_state.bot_logs = ["--- Error fetching logs: Invalid JSON ---"]
         return False

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Run Bot (Remote)")
st.title("🚀 Run Engagement Bot (Remote Control)")
st.caption("Start, stop, and monitor the bot running on the local machine.")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Check API Config ---
if not BOT_API_URL: st.error("🚨 Critical Error: BOT_API_URL secret is not set."); st.stop()
if not API_KEY: st.warning("⚠️ Warning: BOT_API_KEY secret is not set.")

# --- Fetch Status and Logs ---
now = time.time()
current_status = st.session_state.bot_api_status
current_state = current_status.get("state", "unknown")
is_active_state = current_state in ["running", "starting", "stopping"]
refresh_interval = STATUS_REFRESH_INTERVAL_ACTIVE if is_active_state else STATUS_REFRESH_INTERVAL_IDLE
needs_refresh = (now - st.session_state.last_status_fetch_time) > refresh_interval

fetch_logs_flag = False # Flag to indicate if logs should be fetched this cycle

if needs_refresh or current_state == "unknown":
    with st.spinner("Checking bot status..."):
        fetch_status_from_api()
        # Get updated state *after* fetch
        current_state = st.session_state.bot_api_status.get("state", "unknown")
        is_active_state = current_state in ["running", "starting", "stopping"] # Recalculate based on new state
        if is_active_state:
            fetch_logs_flag = True # Fetch logs if active
        elif st.session_state.bot_logs != ["--- Bot is not running ---"]:
             # Set idle message if state is now inactive
             st.session_state.bot_logs = ["--- Bot is not running ---"]

if fetch_logs_flag:
    fetch_logs_from_api() # Fetch logs outside the spinner if needed

# --- Control Buttons ---
st.subheader("Bot Controls")
col1, col2 = st.columns(2)
with col1:
    run_disabled = current_state not in ["idle", "error", "stopped"]
    if st.button("▶️ Run Engagement Bot", disabled=run_disabled, use_container_width=True, type="primary" if not run_disabled else "secondary"):
        st.session_state.bot_logs = [f"--- Sending 'start' command: {time.strftime('%H:%M:%S')} ---"]
        with st.spinner("Sending 'start' command..."): result, error = send_control_command("start")
        if error: st.error(f"Failed start: {error}")
        else: st.success(result.get("message", "Start sent.")); time.sleep(1)
        # Force immediate refresh after action
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun()
with col2:
    stop_disabled = current_state not in ["running", "starting"]
    if st.button("⏹️ Stop Bot", disabled=stop_disabled, use_container_width=True):
        st.session_state.bot_logs.append(f"--- Sending 'stop' command: {time.strftime('%H:%M:%S')} ---") # Append stop command
        with st.spinner("Sending 'stop' command..."): result, error = send_control_command("stop")
        if error: st.error(f"Failed stop: {error}")
        else: st.warning(result.get("message", "Stop sent.")); time.sleep(1)
        # Force immediate refresh after action
        fetch_status_from_api(); fetch_logs_from_api(); st.rerun()

# --- Display Bot Status & Logs ---
st.subheader("🤖 Bot Status & Logs")
status_placeholder = st.container()

with status_placeholder:
    # Display Status Line
    status_data = st.session_state.bot_api_status
    state_display = status_data.get('state', 'N/A').upper()
    details_display = status_data.get('details', 'N/A')
    last_update_ts = status_data.get('last_update')
    if last_update_ts: last_update_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update_ts)); status_line = f"**Status:** `{state_display}` (Updated: {last_update_str})"
    else: status_line = f"**Status:** `{state_display}`"
    if state_display == "RUNNING": st.info(status_line)
    elif state_display in ["IDLE", "STOPPED"]: st.success(status_line)
    elif state_display == "ERROR": st.error(status_line)
    elif state_display in ["STARTING", "STOPPING"]: st.warning(status_line)
    else: st.info(status_line)
    st.caption(f"Latest Detail: {details_display}")

    # Display Logs Area
    st.markdown("**Recent Logs:**")
    log_text = "\n".join(st.session_state.bot_logs)
    # Use height to make it scrollable if logs get long
    st.code(log_text, language='log', line_numbers=False)

    # Add a manual refresh button
    if st.button("🔄 Refresh Status & Logs"):
         with st.spinner("Refreshing..."):
              fetch_status_from_api()
              # Only fetch logs if status indicates potential activity
              if st.session_state.bot_api_status.get("state") in ["running", "starting", "stopping"]: fetch_logs_from_api()
              st.rerun()


# --- Auto-refresh Logic ---
# Recalculate interval based on potentially updated state
current_state = st.session_state.bot_api_status.get("state", "unknown")
is_active_state = current_state in ["running", "starting", "stopping"]
refresh_interval = STATUS_REFRESH_INTERVAL_ACTIVE if is_active_state else STATUS_REFRESH_INTERVAL_IDLE
st.caption(f"Auto-refreshing status/logs every {refresh_interval}s...")
time.sleep(refresh_interval)
st.rerun()