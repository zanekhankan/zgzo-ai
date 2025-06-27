import streamlit as st
import json
from datetime import datetime

# --- Simple user database ---
USER_DB = {
    "admin": "admin123",
    "estimator1": "bidmaster",
    "guest": "test123"
}

# --- Login state setup ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

# --- Login UI ---
def login_ui():
    st.title("🔐 ZGZO.AI Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USER_DB and USER_DB[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success(f"Welcome, {username}!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def logout_ui():
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

# --- File paths ---
COST_MEMORY_FILE = "cost_memory.json"
CORRECTION_LOG_FILE = "correction_log.json"
DELETE_LOG_FILE = "delete_log.json"

# --- JSON file helpers ---
def load_data(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data, file):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# --- Load learning logs ---
cost_memory = load_data(COST_MEMORY_FILE)
correction_log = load_data(CORRECTION_LOG_FILE)
delete_log = load_data(DELETE_LOG_FILE)

# --- Log corrections ---
def track_price_correction(original, user_value, line_item):
    correction = {
        "original_cost": original,
        "corrected_cost": user_value,
        "timestamp": datetime.now().isoformat(),
        "adjustment": user_value - original
    }
    if line_item not in correction_log:
        correction_log[line_item] = []
    correction_log[line_item].append(correction)
    save_data(correction_log, CORRECTION_LOG_FILE)

# --- Log deletions ---
def track_deleted_item(line_item):
    delete_log[line_item] = delete_log.get(line_item, 0) + 1
    save_data(delete_log, DELETE_LOG_FILE)

# --- Train from corrections ---
def update_cost_memory():
    for item, corrections in correction_log.items():
        avg = sum(c["corrected_cost"] for c in corrections) / len(corrections)
        if item in cost_memory:
            cost_memory[item] = round((cost_memory[item] * 0.8 + avg * 0.2), 2)
        else:
            cost_memory[item] = round(avg, 2)
    save_data(cost_memory, COST_MEMORY_FILE)

# --- Flagged deletions ---
def get_flagged_items(threshold=3):
    return [item for item, count in delete_log.items() if count >= threshold]

# --- AI suggestions ---
def ai_suggest_line_items():
    flagged = set(get_flagged_items())
    return [
        {"item": item, "suggested_cost": cost}
        for item, cost in cost_memory.items()
        if item not in flagged
    ]

# --- Main app ---
if not st.session_state.authenticated:
    login_ui()
else:
    st.title("🧠 ZGZO.AI Bid Assistant")
    st.subheader(f"👷 Logged in as: {st.session_state.username}")
    logout_ui()

    st.header("📌 Suggested Line Items")
    if st.button("🔁 Update AI Suggestions"):
        update_cost_memory()

    for suggestion in ai_suggest_line_items():
        st.write(f"**{suggestion['item']}** — ${suggestion['suggested_cost']}")

    st.divider()

    st.header("✍️ Log Price Correction")
    item = st.text_input("Line Item Name:")
    original_cost = st.number_input("Original Cost", min_value=0.0, value=0.0)
    corrected_cost = st.number_input("Corrected Cost", min_value=0.0, value=0.0)
    if st.button("Log Correction"):
        if item:
            track_price_correction(original_cost, corrected_cost, item)
            st.success(f"Logged correction for **{item}**")
        else:
            st.error("Enter a line item name")

    st.divider()

    st.header("🗑️ Log Deleted Item")
    del_item = st.text_input("Item to Delete:")
    if st.button("Log Deletion"):
        if del_item:
            track_deleted_item(del_item)
            st.success(f"Marked **{del_item}** as deleted")
        else:
            st.error("Enter a line item name")
