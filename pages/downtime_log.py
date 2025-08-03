import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, datetime

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load dropdowns ===
@st.cache_data
def get_departments():
    with get_connection() as conn:
        return pd.read_sql("SELECT DISTINCT department FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_machines_by_dept(dept):
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code, machine_name FROM machine_list WHERE department = %s AND is_active = TRUE", conn, params=(dept,))

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

# === Update downtime in production_log ===
def update_production_downtime(log_date, shift, machine_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT SUM(duration_min)
            FROM downtime_log
            WHERE log_date = %s AND shift = %s AND machine_id = %s
        """, (log_date, shift, machine_id))
        total_downtime = cur.fetchone()[0] or 0

        cur.execute("""
            UPDATE production_log
            SET downtime_min = %s
            WHERE log_date = %s AND shift = %s AND machine_id = %s
        """, (total_downtime, log_date, shift, machine_id))
        conn.commit()

# === UI ===
st.set_page_config(page_title="บันทึก Downtime", layout="centered")
st.header("🔧 บันทึก Downtime")

departments = get_departments()["department"].tolist()
selected_dept = st.selectbox("แผนก", departments)

machines_df = get_machines_by_dept(selected_dept)
reasons_df = get_downtime_reasons()

with st.form("downtime_form"):
    col1, col2 = st.columns(2)
    with col1:
        log_date = st.date_input("วันที่", value=date.today())
        shift = st.selectbox("กะ", ["Day", "Night"])
        machine_display = machines_df["machine_code"] + " - " + machines_df["machine_name"]
        selected_machine = st.selectbox("เครื่องจักร", machine_display)
    with col2:
        reason = st.selectbox("สาเหตุ Downtime", reasons_df["reason_name"])
        duration_min = st.number_input("ระยะเวลา (นาที)", min_value=1)
        created_by = st.text_input("ชื่อผู้กรอก")

    submitted = st.form_submit_button("✅ บันทึก Downtime")

    if submitted:
        try:
            machine_id = machines_df.loc[machine_display == selected_machine, "id"].values[0]
            reason_id = reasons_df.loc[reasons_df["reason_name"] == reason, "id"].values[0]

            data = {
                "log_date": log_date,
                "shift": shift,
                "machine_id": int(machine_id),
                "downtime_reason_id": int(reason_id),
                "duration_min": int(duration_min),
                "created_by": created_by,
                "created_at": datetime.now()
            }

            insert_downtime_log(data)
            update_production_downtime(log_date, shift, machine_id)
            st.success("✅ บันทึก Downtime สำเร็จ และอัปเดต production_log แล้ว")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
