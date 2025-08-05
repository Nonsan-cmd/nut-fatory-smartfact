import streamlit as st
import psycopg2
import pandas as pd

# === Config ===
st.set_page_config(page_title="🔐 Login", page_icon="🔐", layout="centered")

# === Session State Initialization ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

# === DB Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Authenticate User ===
def authenticate_user(username, password):
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT * FROM user_accounts WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )
        if not df.empty:
            return df.iloc[0]["role"]
        else:
            return None

# === UI ===
st.title("🔐 เข้าสู่ระบบ Smart Factory")

with st.form("login_form"):
    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    submitted = st.form_submit_button("เข้าสู่ระบบ")

    if submitted:
        role = authenticate_user(username, password)
        if role:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = role
            st.success(f"ยินดีต้อนรับ {username} ({role})")

            # === Role-Based Navigation ===
            if role in ["Operator", "Leader", "Officer", "Supervisor", "Admin"]:
                st.switch_page("pages/1_📋_Production_Record.py")
            elif role in ["MN_supervisor", "MN_manager", "Technician"]:
                st.switch_page("pages/6_🛠_Maintenance_Report.py")
        else:
            st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
