import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
from io import BytesIO
from fpdf import FPDF

# --- User DB ---
USER_DB = {
    "admin": "admin123",
    "estimator1": "bidmaster",
    "guest": "test123"
}

# --- Session State ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "saved_bids" not in st.session_state:
    st.session_state.saved_bids = {}

# --- Files ---
COST_MEMORY_FILE = "cost_memory.json"
CORRECTION_LOG_FILE = "correction_log.json"
DELETE_LOG_FILE = "delete_log.json"
PROFILE_FILE = "gc_profile.json"
USER_LOG_FILE = "user_log.json"

# --- Load/Save Functions ---
def load_data(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data, file):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# --- Data Load ---
cost_memory = load_data(COST_MEMORY_FILE)
correction_log = load_data(CORRECTION_LOG_FILE)
delete_log = load_data(DELETE_LOG_FILE)
gc_profiles = load_data(PROFILE_FILE)
user_log = load_data(USER_LOG_FILE)

# --- Logging ---
def log_user_action(action):
    now = datetime.now().isoformat()
    if st.session_state.username not in user_log:
        user_log[st.session_state.username] = []
    user_log[st.session_state.username].append({"time": now, "action": action})
    save_data(user_log, USER_LOG_FILE)

# --- Auth ---
def login_ui():
    st.title("🔐 ZGZO.AI Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USER_DB and USER_DB[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            log_user_action("Login")
            st.rerun()
        else:
            st.error("Invalid credentials")

def logout_ui():
    if st.button("Logout"):
        log_user_action("Logout")
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.rerun()

# --- GC Profiler ---
def gc_profile_creator():
    st.subheader("🧱 GC Profiler")
    name = st.text_input("Company Name")
    specialty = st.selectbox("Specialty", ["Concrete", "Framing", "Drywall", "Paint", "General"])
    license_no = st.text_input("License Number")
    region = st.text_input("Region")
    if st.button("Save Profile"):
        gc_profiles[name] = {"specialty": specialty, "license": license_no, "region": region}
        save_data(gc_profiles, PROFILE_FILE)
        st.success("Profile saved")
        log_user_action(f"Saved GC Profile: {name}")

# --- Corrections/Deletes ---
def track_price_correction(original, corrected, item):
    correction = {"original": original, "corrected": corrected, "time": datetime.now().isoformat()}
    correction_log.setdefault(item, []).append(correction)
    save_data(correction_log, CORRECTION_LOG_FILE)
    log_user_action(f"Corrected {item}: {original} → {corrected}")

def track_deleted_item(item):
    delete_log[item] = delete_log.get(item, 0) + 1
    save_data(delete_log, DELETE_LOG_FILE)
    log_user_action(f"Deleted item: {item}")

def update_cost_memory():
    for item, corrections in correction_log.items():
        avg = sum(c["corrected"] for c in corrections) / len(corrections)
        cost_memory[item] = round(cost_memory.get(item, avg) * 0.8 + avg * 0.2, 2)
    save_data(cost_memory, COST_MEMORY_FILE)

# --- AI Suggestions ---
def get_flagged_items(threshold=3):
    return [k for k, v in delete_log.items() if v >= threshold]

def ai_suggest_line_items():
    return [
        {"item": item, "suggested_cost": cost}
        for item, cost in cost_memory.items()
        if item not in get_flagged_items()
    ]

# --- Autocomplete ---
def autocomplete_options(prefix):
    return [item for item in cost_memory if item.lower().startswith(prefix.lower())]

# --- Bid Save/Load ---
def save_bid(bid_name, bid_data):
    st.session_state.saved_bids[bid_name] = bid_data
    log_user_action(f"Saved bid: {bid_name}")

def load_bid(bid_name):
    return st.session_state.saved_bids.get(bid_name, [])

# --- Export PDF ---
def export_pdf(bid):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="ZGZO.AI Bid Document", ln=True, align='C')
    for item in bid:
        pdf.cell(200, 10, txt=f"{item['item']} - ${item['cost']}", ln=True)
    buffer = BytesIO()
    pdf.output(buffer)
    return buffer

# --- Main App ---
if not st.session_state.authenticated:
    login_ui()
else:
    st.title("🧠 ZGZO.AI Full Suite")
    st.caption(f"👤 Logged in as {st.session_state.username}")
    logout_ui()

    st.divider()
    st.header("📂 Upload Files")
    files = st.file_uploader("Upload plans or docs", accept_multiple_files=True)
    for f in files:
        st.success(f"Uploaded: {f.name}")

    st.divider()
    gc_profile_creator()

    st.divider()
    st.header("📌 AI Line Item Suggestions")
    if st.button("🔁 Refresh Suggestions"):
        update_cost_memory()
    for suggestion in ai_suggest_line_items():
        st.write(f"**{suggestion['item']}** — ${suggestion['suggested_cost']}")

    st.divider()
    st.header("⚡ AI Autocomplete Input")
    prefix = st.text_input("Start typing line item...")
    if prefix:
        matches = autocomplete_options(prefix)
        st.write("Suggestions:", matches[:5])

    st.divider()
    st.header("✍️ Log Price Correction")
    item = st.text_input("Item")
    original = st.number_input("Original Cost")
    corrected = st.number_input("Corrected Cost")
    if st.button("Log Correction"):
        track_price_correction(original, corrected, item)
        st.success("Logged correction")

    st.divider()
    st.header("🗑️ Log Deleted Item")
    del_item = st.text_input("Item to Delete")
    if st.button("Log Deletion"):
        track_deleted_item(del_item)
        st.success("Logged deletion")

    st.divider()
    st.header("💵 Markup Settings")
    global_markup = st.slider("Global Markup %", 0, 100, 10)

    st.divider()
    st.header("💾 Save & Export Bids")
    bid_items = st.text_area("Enter line items (one per line, format: name,cost)")
    parsed_bid = []
    for line in bid_items.strip().split("\n"):
        if line:
            parts = line.split(',')
            if len(parts) == 2:
                name, cost = parts[0], float(parts[1])
                marked_cost = round(cost * (1 + global_markup / 100), 2)
                parsed_bid.append({"item": name, "cost": marked_cost})

    bid_name = st.text_input("Bid Name")
    if st.button("Save This Bid"):
        save_bid(bid_name, parsed_bid)
        st.success("Bid saved")

    if st.button("📥 Export PDF"):
        pdf_data = export_pdf(parsed_bid)
        st.download_button("Download PDF", data=pdf_data.getvalue(), file_name="bid.pdf")

    st.divider()
    st.header("📁 Load Saved Bid")
    selected = st.selectbox("Choose Saved Bid", list(st.session_state.saved_bids.keys()))
    if st.button("Load Selected Bid"):
        loaded = load_bid(selected)
        st.write(loaded)
