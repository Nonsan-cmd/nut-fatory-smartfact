import streamlit as st
import pandas as pd
import psycopg2

# === Streamlit Page Config ===
st.set_page_config(page_title="🔐 Login", page_icon="🔐", layout="centered")

# === Session State Initialization ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === User Authentication ===
def authenticate_user(username, password):
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT * FROM user_roles WHERE username=%s AND password=%s",
            conn,
            params=(username, password)
        )
        if not df.empty:
            return df.iloc[0]["role"], df.iloc[0]["display_name"]
        else:
            return None, None

# === Redirect after login ===
def redirect_by_role(role):
    page_map = {
        "Operator": "1_Production_Record.py",
        "Leader": "1_Production_Record.py",
        "Officer": "3_UploadProduction.py",
        "Supervisor": "5_Dashboard.py",
        "Admin": "5_Dashboard.py",
        "Technician": "6_Maintenance_Report.py",
        "MN_Manager": "6_Maintenance_Report.py",
    }
    if role in page_map:
        st.switch_page(f"pages/{page_map[role]}")
    else:
        st.error("Role นี้ยังไม่ได้กำหนดหน้าที่เข้าสู่ระบบ")

# === Login Form ===
st.title("🔐 เข้าสู่ระบบ")

with st.form("login_form", clear_on_submit=False):
    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    submitted = st.form_submit_button("เข้าสู่ระบบ")

    if submitted:
        role, display_name = authenticate_user(username, password)
        if role:
            st.session_state.authenticated = True
            st.session_state.username = display_name
            st.session_state.role = role
            st.success(f"ยินดีต้อนรับคุณ {display_name} ({role})")
            st.experimental_rerun()
        else:
            st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# === Auto redirect if already logged in ===
if st.session_state.authenticated:
    redirect_by_role(st.session_state.role)
