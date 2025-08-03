import streamlit as st
import psycopg2
import pandas as pd
from datetime import date, datetime

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load dropdown options ===
@st.cache_data
def get_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code, machine_name FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_downtime_reasons():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, reason_name FROM downtime_reason_master", conn)

# === Insert downtime record ===
def insert_downtime_log(data):
    with get_connection() as conn:
        cur = conn.cursor()
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO downtime_log ({keys}) VALUES ({values})"
        cur.execute(sql, list(data.values()))
        conn.commit()

# === UI ===
st.header("🛠️ บันทึก Downtime เครื่องจักร")

machines_df = get_machines()
reasons_df = get_downtime_reasons()

with st.form("form_downtime"):
    col1, col2 = st.columns(2)
    with col1:
        log_date = st.date_input("วันที่", value=date.today())
        shift = st.selectbox("กะ", ["Day", "Night"])
        machine = st.selectbox("เครื่องจักร", machines_df["machine_code"] + " - " + machines_df["machine_name"])
    with col2:
        reason = st.selectbox("สาเหตุการหยุด", reasons_df["reason_name"])
        duration_min = st.number_input("ระยะเวลา (นาที)", min_value=0)
        created_by = st.text_input("ชื่อผู้กรอก")

    submitted = st.form_submit_button("✅ บันทึก Downtime")

    if submitted:
        machine_id = machines_df.loc[machines_df["machine_code"] + " - " + machines_df["machine_name"] == machine, "id"].values[0]
        reason_id = reasons_df.loc[reasons_df["reason_name"] == reason, "id"].values[0]

        data = {
            "log_date": log_date,
            "shift": shift,
            "machine_id": machine_id,
            "downtime_reason_id": reason_id,
            "duration_min": duration_min,
            "created_by": created_by,
            "created_at": datetime.now()
        }

        try:
            insert_downtime_log(data)
            st.success("✅ บันทึก Downtime สำเร็จแล้ว")
        except Exception as e:
            st.error(f"❌ บันทึกไม่สำเร็จ: {e}")
