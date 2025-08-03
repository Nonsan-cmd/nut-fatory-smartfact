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
        return pd.read_sql("SELECT id, machine_code, machine_name, department FROM machine_list WHERE is_active = TRUE", conn)

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
st.set_page_config(page_title="Production Record", layout="centered")
st.header("📋 บันทึกข้อมูลการผลิต")

machines_df = get_machines()
parts_df = get_parts()

with st.form("form_production"):
    col1, col2 = st.columns(2)
    with col1:
        log_date = st.date_input("📅 วันที่", value=date.today())
        shift = st.selectbox("🕐 กะ", ["Day", "Night"])

        # ✅ เลือกแผนกก่อน
        dept_list = machines_df["department"].dropna().unique().tolist()
        selected_dept = st.selectbox("🏭 แผนก", dept_list)

        filtered_machines = machines_df[machines_df["department"] == selected_dept]
        machine_display_list = filtered_machines["machine_code"] + " - " + filtered_machines["machine_name"]
        selected_machine = st.selectbox("⚙️ เครื่องจักร", machine_display_list)

        # Get machine_id
        machine_row = filtered_machines[machine_display_list == selected_machine]
        if not machine_row.empty:
            machine_id = int(machine_row["id"].values[0].item())
        else:
            st.stop()

    with col2:
        selected_part = st.selectbox("🔩 Part No", parts_df["part_no"])
        plan_qty = st.number_input("🎯 Plan จำนวน", min_value=0, step=1)
        actual_qty = st.number_input("✅ Actual จำนวน", min_value=0, step=1)
        defect_qty = st.number_input("❌ Defect จำนวน", min_value=0, step=1)

    remark = st.text_area("📝 หมายเหตุ")
    created_by = st.text_input("👷‍♂️ ชื่อผู้กรอก")

    submitted = st.form_submit_button("✅ บันทึกข้อมูล")

    if submitted:
        try:
            part_row = parts_df[parts_df["part_no"] == selected_part]
            if part_row.empty:
                st.error("❌ ไม่พบ Part No ที่เลือก")
                st.stop()

            part_id = int(part_row["id"].values[0].item())

            data = {
                "log_date": log_date,
                "shift": shift,
                "machine_id": int(machine_id),
                "part_id": int(part_id),
                "plan_qty": int(plan_qty),
                "actual_qty": int(actual_qty),
                "defect_qty": int(defect_qty),
                "remark": remark,
                "created_by": created_by,
                "department": selected_dept,
                "created_at": datetime.now()
            }

            insert_production_log(data)
            st.success("✅ บันทึกสำเร็จเรียบร้อย")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
