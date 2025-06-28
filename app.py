import streamlit as st
import pandas as pd
import json
import openai
import smtplib
from fpdf import FPDF
from io import BytesIO
from datetime import date, datetime
from email.message import EmailMessage
import os

st.set_page_config(page_title="ZGZO.AI Bid Generator", layout="wide")

# --- Ensure bid_history.json exists ---
if not os.path.exists("bid_history.json"):
    with open("bid_history.json", "w") as f:
        f.write("{}")

# --- Authentication ---
USER_DB = {"admin": "admin123", "guest": "test123"}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.authenticated:
    st.title("🔐 ZGZO.AI Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USER_DB and USER_DB[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# --- Load past bids ---
BID_HISTORY_FILE = "bid_history.json"

def load_bid_history():
    try:
        with open(BID_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_bid_history(data):
    with open(BID_HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

bid_history = load_bid_history()
user_bids = bid_history.get(st.session_state.username, {})

# --- AI Suggestion (OpenAI API must be configured) ---
def ai_suggest_line_items(scope):
    try:
        openai.api_key = st.secrets["openai_api_key"]
        prompt = f"Generate a list of construction bid line items with quantity, unit, and unit price for the following scope: {scope}"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        rows = [x.split(',') for x in content.strip().split('\n') if len(x.split(',')) == 4]
        return pd.DataFrame(rows, columns=["Description", "Quantity", "Unit", "Unit Price"])
    except Exception as e:
        st.warning(f"AI suggestion failed: {e}")
        return pd.DataFrame(columns=["Description", "Quantity", "Unit", "Unit Price"])

# --- Interface ---
st.title("🧾 ZGZO.AI Bid Generator")

project_name = st.text_input("Project Name", key="project_name")
if project_name == "" and len(user_bids) > 0:
    st.info("Choose from past bids:")
    st.write(list(user_bids.keys()))

scope = st.text_area("Scope of Work / Description", key="scope")
if st.button("🧠 AI Suggest Line Items"):
    st.session_state.line_items = ai_suggest_line_items(scope)

st.text_input("Prepared For", key="client")
st.text_input("Prepared By", key="gc")
st.text_input("Client Email (Optional)", key="client_email")
st.date_input("Date", value=date.today(), key="bid_date")

st.markdown("---")

st.subheader("📋 Line Items")
if "line_items" not in st.session_state:
    st.session_state.line_items = pd.DataFrame(columns=["Description", "Quantity", "Unit", "Unit Price", "Total"])

edited_table = st.data_editor(
    st.session_state.line_items,
    num_rows="dynamic",
    use_container_width=True,
    key="editor"
)

edited_table["Total"] = edited_table.apply(lambda row: round(float(row["Quantity"] or 0) * float(row["Unit Price"] or 0), 2), axis=1)
st.session_state.line_items = edited_table

grand_total = edited_table["Total"].sum()
st.subheader(f"💰 Grand Total: ${grand_total:,.2f}")

# --- PDF Export ---
def generate_pdf(project, scope, client, gc, email, bid_date, table):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"{project} - Bid Proposal", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Prepared For: {client} ({email})", ln=True)
    pdf.cell(200, 10, txt=f"Prepared By: {gc}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {bid_date}", ln=True)
    pdf.ln(10)
    pdf.multi_cell(0, 10, txt=f"Scope: {scope}")
    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(60, 10, "Description")
    pdf.cell(25, 10, "Quantity")
    pdf.cell(25, 10, "Unit")
    pdf.cell(30, 10, "Unit Price")
    pdf.cell(30, 10, "Total", ln=True)

    pdf.set_font("Arial", size=12)
    for _, row in table.iterrows():
        pdf.cell(60, 10, str(row["Description"]))
        pdf.cell(25, 10, str(row["Quantity"]))
        pdf.cell(25, 10, str(row["Unit"]))
        pdf.cell(30, 10, f"${row['Unit Price']}")
        pdf.cell(30, 10, f"${row['Total']}", ln=True)

    total_sum = table['Total'].sum()
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(140, 10, "Total Bid:")
    pdf.cell(30, 10, f"${round(total_sum, 2)}", ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 10, "Signature: ______________________", ln=True)

    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

if st.button("📤 Generate PDF"):
    if len(st.session_state.line_items) == 0:
        st.warning("Add some line items first!")
    else:
        pdf_data = generate_pdf(
            st.session_state.project_name,
            st.session_state.scope,
            st.session_state.client,
            st.session_state.gc,
            st.session_state.client_email,
            st.session_state.bid_date,
            st.session_state.line_items
        )
        st.download_button("Download Bid PDF", data=pdf_data, file_name="ZGZO_Bid.pdf")

        if st.session_state.client_email:
            with st.spinner("Sending bid to client..."):
                try:
                    msg = EmailMessage()
                    msg['Subject'] = f"Bid Proposal: {st.session_state.project_name}"
                    msg['From'] = "your_email@example.com"
                    msg['To'] = st.session_state.client_email
                    msg.set_content("Attached is the bid proposal you requested.")
                    msg.add_attachment(pdf_data.read(), maintype='application', subtype='pdf', filename="ZGZO_Bid.pdf")

                    with smtplib.SMTP('smtp.gmail.com', 587) as server:
                        server.starttls()
                        server.login("your_email@example.com", "your_password")
                        server.send_message(msg)
                    st.success("Bid emailed to client.")
                except Exception as e:
                    st.warning(f"Email failed: {e}")

# --- Save Bid ---
st.text_input("Save Current Bid As", key="save_name")
if st.button("💾 Save Bid"):
    name = st.session_state.save_name.strip()
    if name:
        user_bids[name] = {
            "project": st.session_state.project_name,
            "scope": st.session_state.scope,
            "client": st.session_state.client,
            "gc": st.session_state.gc,
            "email": st.session_state.client_email,
            "date": str(st.session_state.bid_date),
            "rows": st.session_state.line_items.to_dict(orient="records")
        }
        bid_history[st.session_state.username] = user_bids
        save_bid_history(bid_history)
        st.success("Bid saved.")

# --- Load Bid ---
st.selectbox("Load a Previous Bid", options=["Select..."] + list(user_bids.keys()), key="load_choice")
if st.button("📂 Load Selected Bid"):
    name = st.session_state.load_choice
    if name and name != "Select...":
        bid = user_bids[name]
        st.session_state.project_name = bid["project"]
        st.session_state.scope = bid["scope"]
        st.session_state.client = bid["client"]
        st.session_state.gc = bid["gc"]
        st.session_state.client_email = bid["email"]
        st.session_state.bid_date = pd.to_datetime(bid["date"]).date()
        st.session_state.line_items = pd.DataFrame(bid["rows"])
        st.success(f"Bid '{name}' loaded.")
