import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Master Data ===
@st.cache_data
def load_master_data():
    with get_connection() as conn:
        machine_df = pd.read_sql("SELECT id, machine_name, department FROM machine_list WHERE is_active = TRUE", conn)
        part_df = pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)
    return machine_df, part_df

machine_df, part_df = load_master_data()

# === UI ===
st.set_page_config(page_title="Production Record", layout="centered")
st.title("📝 บันทึกข้อมูลการผลิต")

col1, col2 = st.columns(2)
with col1:
    log_date = st.date_input("📅 วันที่", value=date.today())
    shift = st.selectbox("🕐 กะ", ["Day", "Night"])
    department = st.selectbox("📂 แผนก", sorted(machine_df["department"].unique()))
    filtered_machines = machine_df[machine_df["department"] == department]
    machine_name = st.selectbox("⚙ เครื่องจักร", filtered_machines["machine_name"].tolist())
with col2:
    part_no = st.selectbox("#️⃣ Part No", part_df["part_no"].tolist())
    plan_qty = st.number_input("🎯 Plan จำนวน", min_value=0, step=1)
    actual_qty = st.number_input("✅ Actual จำนวน", min_value=0, step=1)
    defect_qty = st.number_input("❌ Defect จำนวน", min_value=0, step=1)
    remark = st.text_area("📝 หมายเหตุ")

# 🔍 Map ID
part_id = part_df.loc[part_df["part_no"] == part_no, "id"].values[0]
machine_id = filtered_machines.loc[filtered_machines["machine_name"] == machine_name, "id"].values[0]

# 👤 ผู้ใช้ (กำหนดเองหรือดึงจากระบบจริง)
created_by = st.text_input("👤 ผู้บันทึก", value="admin")

if st.button("💾 บันทึกข้อมูล"):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO production_log (
                    log_date, shift, machine_id, part_id,
                    plan_qty, actual_qty, defect_qty, remark,
                    created_by, department
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                log_date, shift, machine_id, part_id,
                plan_qty, actual_qty, defect_qty, remark,
                created_by, department
            ))
            conn.commit()
        st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")
