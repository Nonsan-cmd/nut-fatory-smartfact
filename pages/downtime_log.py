import streamlit as st
import psycopg2
from datetime import datetime
import pandas as pd

# === Setup ===
st.set_page_config(page_title="บันทึก Downtime", layout="wide")
st.markdown("""
    <h1 style='text-align: center; font-size: 2.8em;'>🛠️ บันทึก Downtime</h1>
    <hr style='border: 1px solid #ccc;' />
""", unsafe_allow_html=True)

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

with st.container():
    st.write("### กรอกข้อมูลเพื่อบันทึก Downtime")

    col1, col2 = st.columns(2)
    with col1:
        department = st.selectbox("แผนก", sorted(machine_df["department"].unique()))
        log_date = st.date_input("📅 วันที่", datetime.today())
        shift = st.selectbox("🕘 กะ", ["Day", "Night"])
        machine_label = st.selectbox("⚙️ เครื่องจักร", machine_df[machine_df["department"] == department]["machine_name"])

    with col2:
        reason_name = st.selectbox("📌 สาเหตุ Downtime", reason_df["reason_name"])
        duration_min = st.number_input("⏱️ ระยะเวลา (นาที)", min_value=0, step=1, value=0)
        operator_name = st.text_input("✍️ ชื่อผู้กรอก")

# === Save Function ===
def save_downtime():
    machine_row = machine_df[machine_df["machine_name"] == machine_label].iloc[0]
    reason_row = reason_df[reason_df["reason_name"] == reason_name].iloc[0]

    data = {
        "log_date": str(log_date),
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
                INSERT INTO downtime_log (log_date, shift, machine_id, downtime_reason_id, duration_min, operator_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, tuple(data.values()))
            conn.commit()
            st.success("✅ บันทึก Downtime สำเร็จแล้ว")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# === Submit Button ===
st.markdown("""<br>""", unsafe_allow_html=True)
submit_col, _ = st.columns([1, 3])
with submit_col:
    if st.button("✅ บันทึก Downtime", use_container_width=True):
        if not operator_name:
            st.warning("⚠️ กรุณาระบุชื่อผู้กรอกก่อนบันทึก")
        elif duration_min <= 0:
            st.warning("⚠️ ระยะเวลาต้องมากกว่า 0 นาที")
        else:
            save_downtime()
