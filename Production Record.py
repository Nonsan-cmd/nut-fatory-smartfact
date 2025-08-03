import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Machine List ===
def load_machine_list():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM machine_list WHERE is_active = TRUE", conn)

# === Load Part Master ===
def load_part_master():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM part_master WHERE is_active = TRUE", conn)

# === Insert Production Log ===
def insert_production_log(data):
    with get_connection() as conn:
        cur = conn.cursor()
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO production_log ({keys}) VALUES ({values})"
        cur.execute(sql, list(data.values()))
        conn.commit()

# === Page Config ===
st.set_page_config(page_title="Production Record", layout="centered")
st.title("📝 บันทึกข้อมูลการผลิต")

# === Load Data ===
machine_df = load_machine_list()
part_df = load_part_master()

# === Validate machine_df ===
if machine_df is None or not isinstance(machine_df, pd.DataFrame) or "department" not in machine_df.columns:
    st.error("ไม่สามารถโหลดข้อมูลเครื่องจักรได้ กรุณาตรวจสอบฐานข้อมูลหรือการเชื่อมต่อ")
    st.stop()

# === UI Input ===
col1, col2 = st.columns(2)
with col1:
    log_date = st.date_input("📅 วันที่", value=date.today())
    shift = st.selectbox("🕒 กะ", ["Day", "Night"])
    department = st.selectbox("📂 แผนก", sorted(machine_df["department"].dropna().unique()))

with col2:
    part_no = st.selectbox("🔢 Part No", sorted(part_df["part_no"].unique()))
    plan_qty = st.number_input("🎯 Plan จำนวน", min_value=0, step=1)
    actual_qty = st.number_input("✅ Actual จำนวน", min_value=0, step=1)
    defect_qty = st.number_input("❌ Defect จำนวน", min_value=0, step=1)

# === Machine Selector ตามแผนก ===
filtered_machines = machine_df[machine_df["department"] == department]
machine_name = st.selectbox("⚙️ เครื่องจักร", filtered_machines["machine_name"])

remark = st.text_area("📝 หมายเหตุ")
created_by = st.text_input("👤 ผู้บันทึก", value="")

if st.button("💾 บันทึกข้อมูล"):
    selected_machine = filtered_machines[filtered_machines["machine_name"] == machine_name].iloc[0]
    selected_part = part_df[part_df["part_no"] == part_no].iloc[0]

    data = {
        "log_date": log_date,
        "shift": shift,
        "machine_id": int(selected_machine["id"]),
        "part_id": int(selected_part["id"]),
        "plan_qty": int(plan_qty),
        "actual_qty": int(actual_qty),
        "defect_qty": int(defect_qty),
        "remark": remark,
        "created_by": created_by,
        "department": department
    }

    try:
        insert_production_log(data)
        st.success("✅ บันทึกข้อมูลสำเร็จ")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")
