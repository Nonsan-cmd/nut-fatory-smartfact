import streamlit as st
import psycopg2
import pandas as pd
from datetime import date, datetime

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load dropdowns ===
@st.cache_data
def get_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code, machine_name FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_parts():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)

# === Insert to production_log ===
def insert_production_log(data):
    with get_connection() as conn:
        cur = conn.cursor()
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO production_log ({keys}) VALUES ({values})"
        cur.execute(sql, list(data.values()))
        conn.commit()

# === UI ===
st.header("📋 บันทึกข้อมูลการผลิต")

machines_df = get_machines()
parts_df = get_parts()

with st.form("form_production"):
    col1, col2 = st.columns(2)
    with col1:
        log_date = st.date_input("วันที่", value=date.today())
        shift = st.selectbox("กะ", ["Day", "Night"])
        machine = st.selectbox("เครื่องจักร", machines_df["machine_code"] + " - " + machines_df["machine_name"])
    with col2:
        part = st.selectbox("Part No", parts_df["part_no"])
        plan_qty = st.number_input("Plan จำนวน", min_value=0)
        actual_qty = st.number_input("Actual จำนวน", min_value=0)
        defect_qty = st.number_input("Defect จำนวน", min_value=0)

    remark = st.text_area("หมายเหตุ")
    created_by = st.text_input("ชื่อผู้กรอก")

    submitted = st.form_submit_button("✅ บันทึกข้อมูล")

    if submitted:
        machine_id = machines_df.loc[machines_df["machine_code"] + " - " + machines_df["machine_name"] == machine, "id"].values[0]
        part_id = parts_df.loc[parts_df["part_no"] == part, "id"].values[0]

        data = {
            "log_date": log_date,
            "shift": shift,
            "machine_id": machine_id,
            "part_id": part_id,
            "plan_qty": plan_qty,
            "actual_qty": actual_qty,
            "defect_qty": defect_qty,
            "remark": remark,
            "created_by": created_by,
            "created_at": datetime.now()
        }

        try:
            insert_production_log(data)
            st.success("✅ บันทึกสำเร็จ")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
