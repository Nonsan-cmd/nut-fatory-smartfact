import streamlit as st
import psycopg2
import pandas as pd

st.set_page_config(page_title="🔐 Login", layout="centered")

# === Session state ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None

# === Connect DB ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Auth Function ===
def authenticate_user(username, password):
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM user_accounts WHERE username=%s AND password=%s", conn, params=(username, password))
        if not df.empty:
            return df.iloc[0]["role"]
        return None

# === Login UI ===
st.title("🔐 Smart Factory Login")

with st.form("login_form"):
    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    submit = st.form_submit_button("เข้าสู่ระบบ")

    if submit:
        role = authenticate_user(username, password)
        if role:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = role
            st.success(f"✅ Login สำเร็จ: {username} ({role})")

            # === Redirect ตาม Role ===
            if role in ["Admin", "Supervisor"]:
                st.switch_page("pages/3_Dashboard.py")
            elif role in ["Leader", "Officer"]:
                st.switch_page("pages/1_Production_Record.py")
            elif role == "Operator":
                st.switch_page("pages/1_Production_Record.py")
            elif role == "Technician":
                st.switch_page("pages/5_Maintenance_Report.py")
            elif role == "MN_Manager":
                st.switch_page("pages/5_Maintenance_Report.py")
            else:
                st.error("ไม่มีสิทธิ์เข้าใช้งานระบบนี้")
        else:
            st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
