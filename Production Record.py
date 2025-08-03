import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load dropdown options ===
@st.cache_data
def get_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code, machine_name, department FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_parts():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)

# === Insert production log ===
def insert_production_log(data):
    with get_connection() as conn:
        cur = conn.cursor()
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO production_log ({keys}) VALUES ({values})"
        cur.execute(sql, list(data.values()))
        conn.commit()

# === Main UI ===
st.title("📝 บันทึกข้อมูลการผลิต")

# --- Input Fields ---
selected_date = st.date_input("วันที่", date.today())
parts_df = get_parts()
selected_part_no = st.selectbox("Part No", parts_df["part_no"].tolist())
selected_part_id = parts_df[parts_df["part_no"] == selected_part_no]["id"].values[0]

shift = st.selectbox("กะ", ["Day", "Night"])
plan_qty = st.number_input("Plan จำนวน", min_value=0, value=0)
actual_qty = st.number_input("Actual จำนวน", min_value=0, value=0)
defect_qty = st.number_input("Defect จำนวน", min_value=0, value=0)

# === เลือกเครื่องจักร และแสดง department ===
machines_df = get_machines()  # ต้องมี column: id, machine_code, machine_name, department
machine_options = [f"{row['machine_code']} - {row['machine_name']}" for _, row in machines_df.iterrows()]
selected_machine_display = st.selectbox("เครื่องจักร", machine_options)

# ดึง machine_id และ department
selected_machine_code = selected_machine_display.split(" - ")[0]
selected_machine_row = machines_df[machines_df["machine_code"] == selected_machine_code].iloc[0]
selected_machine_id = selected_machine_row["id"]
selected_department = selected_machine_row["department"]

# แสดง department
st.text_input("แผนก", value=selected_department, disabled=True)

# หมายเหตุ
remark = st.text_area("หมายเหตุ")

# Username
username = st.text_input("ชื่อผู้บันทึก", max_chars=50)

# === Submit Button ===
if st.button("✅ บันทึกข้อมูล"):
    if not username:
        st.warning("กรุณากรอกชื่อผู้บันทึก")
    else:
        data = {
            "log_date": selected_date,
            "shift": shift,
            "machine_id": selected_machine_id,
            "part_id": selected_part_id,
            "plan_qty": plan_qty,
            "actual_qty": actual_qty,
            "defect_qty": defect_qty,
            "remark": remark,
            "created_by": username,
            "department": selected_department  # ✅ เพิ่ม department ที่เลือก
        }
        try:
            insert_production_log(data)
            st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว")
        except Exception as e:
            st.error(f"❌ บันทึกข้อมูลไม่สำเร็จ: {e}")
