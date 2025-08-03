import streamlit as st
import psycopg2
from datetime import datetime
import pandas as pd

# === Setup ===
st.set_page_config(page_title="บันทึก Downtime", layout="centered")
st.title("🛠️ บันทึก Downtime")

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Master Data ===
@st.cache_data(ttl=600)
def load_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_name, department FROM machine_list ORDER BY machine_name", conn)

@st.cache_data(ttl=600)
def load_reasons():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, reason_name FROM downtime_reason_master ORDER BY reason_name", conn)

# === Form UI ===
machine_df = load_machines()
reason_df = load_reasons()

department = st.selectbox("แผนก", sorted(machine_df["department"].unique()))
log_date = st.date_input("วันที่", datetime.today())
reason_name = st.selectbox("สาเหตุ Downtime", reason_df["reason_name"])
shift = st.selectbox("กะ", ["Day", "Night"])
duration_min = st.number_input("ระยะเวลา (นาที)", min_value=0, step=1, value=0)
machine_label = st.selectbox("เครื่องจักร", machine_df[machine_df["department"] == department]["machine_name"])
operator_name = st.text_input("ชื่อผู้กรอก")

# === Save Function ===
def save_downtime():
    machine_row = machine_df[machine_df["machine_name"] == machine_label].iloc[0]
    reason_row = reason_df[reason_df["reason_name"] == reason_name].iloc[0]

    data = {
        "log_date": str(log_date),
        "department": department,
        "shift": shift,
        "machine_id": int(machine_row["id"]),
        "downtime_reason_id": int(reason_row["id"]),
        "duration_min": int(duration_min),
        "operator_name": operator_name
    }

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO downtime_log (log_date, department, shift, machine_id, downtime_reason_id, duration_min, operator_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, tuple(data.values()))
            conn.commit()
            st.success("✅ บันทึก Downtime สำเร็จแล้ว")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# === Submit Button ===
if st.button("✅ บันทึก Downtime", use_container_width=True):
    if not operator_name:
        st.warning("⚠️ กรุณาระบุชื่อผู้กรอกก่อนบันทึก")
    elif duration_min <= 0:
        st.warning("⚠️ ระยะเวลาต้องมากกว่า 0 นาที")
    else:
        save_downtime()
