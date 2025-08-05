import streamlit as st
import psycopg2
import pandas as pd
from datetime import date, datetime
import pytz

# === CONFIG ===
st.set_page_config(page_title="📋 Production Log", page_icon="🧾", layout="centered")
tz = pytz.timezone("Asia/Bangkok")

# === Session States ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = ""
if "username" not in st.session_state:
    st.session_state.username = ""

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Login Check ===
def authenticate_user(username, password):
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM user_accounts WHERE username=%s AND password=%s", conn, params=(username, password))
        if not df.empty:
            return df.iloc[0]["role"]
        return None

# === Dropdown Loaders ===
@st.cache_data
def get_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code, machine_name, department FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_parts():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)

# === Insert Production Log ===
def insert_production_log(data):
    with get_connection() as conn:
        cur = conn.cursor()
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        cur.execute(f"INSERT INTO production_log ({keys}) VALUES ({values})", list(data.values()))
        conn.commit()

# === Login UI ===
if not st.session_state.authenticated:
    st.title("🔐 เข้าสู่ระบบ Smart Factory")
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
                st.success(f"ยินดีต้อนรับ {username} ({role})")
                st.experimental_rerun()
            else:
                st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# === Access Control ===
allowed_roles = ["Operator", "Leader", "Officer", "Supervisor", "Admin"]

if st.session_state.authenticated and st.session_state.role in allowed_roles:
    st.header("📋 บันทึกข้อมูลการผลิต")

    machines_df = get_machines()
    parts_df = get_parts()

    with st.form("form_production"):
        col1, col2 = st.columns(2)
        with col1:
            log_date = st.date_input("📅 วันที่", value=date.today())
            shift = st.selectbox("🕐 กะ", ["Day", "Night"])

            machine_display_list = machines_df["machine_code"] + " - " + machines_df["machine_name"]
            selected_machine = st.selectbox("⚙️ เครื่องจักร", machine_display_list)

            machine_row = machines_df[machine_display_list == selected_machine]
            if not machine_row.empty:
                machine_id = int(machine_row["id"].values[0])
                department = machine_row["department"].values[0]
                st.text_input("🏭 แผนก", value=department, disabled=True)
            else:
                st.warning("ไม่พบข้อมูลเครื่องจักร")

        with col2:
            selected_part = st.selectbox("🔩 Part No", parts_df["part_no"])
            plan_qty = st.number_input("🎯 Plan จำนวน", min_value=0, step=1)
            actual_qty = st.number_input("✅ Actual จำนวน", min_value=0, step=1)
            defect_qty = st.number_input("❌ Defect จำนวน", min_value=0, step=1)

        remark = st.text_area("📝 หมายเหตุ")
        created_by = st.text_input("👷‍♂️ ชื่อผู้กรอก", value=st.session_state.username)

        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            try:
                part_row = parts_df[parts_df["part_no"] == selected_part]
                if part_row.empty:
                    st.error("❌ ไม่พบ Part No ที่เลือก")
                    st.stop()
                part_id = int(part_row["id"].values[0])
                data = {
                    "log_date": log_date,
                    "shift": shift,
                    "machine_id": machine_id,
                    "part_id": part_id,
                    "plan_qty": int(plan_qty),
                    "actual_qty": int(actual_qty),
                    "defect_qty": int(defect_qty),
                    "remark": remark,
                    "created_by": created_by,
                    "department": department,
                    "created_at": datetime.now(tz)
                }
                insert_production_log(data)
                st.success("✅ บันทึกสำเร็จเรียบร้อย")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

elif st.session_state.authenticated:
    st.error("🚫 คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
