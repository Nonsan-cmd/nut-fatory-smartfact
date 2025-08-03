import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load dropdown options ===
@st.cache_data
def load_part_options():
    with get_connection() as conn:
        df = pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)
    return df

@st.cache_data
def load_machine_options():
    with get_connection() as conn:
        df = pd.read_sql("SELECT id, machine_name, department FROM machine_list WHERE is_active = TRUE", conn)
    return df

# === Insert production record ===
def insert_production_record(data):
    with get_connection() as conn:
        cur = conn.cursor()
        sql = """
            INSERT INTO production_log 
            (log_date, shift, machine_id, part_id, plan_qty, actual_qty, defect_qty, remark, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (
            data["log_date"], data["shift"], data["machine_id"], data["part_id"],
            data["plan_qty"], data["actual_qty"], data["defect_qty"],
            data["remark"], data["created_by"]
        ))
        conn.commit()

# === UI ===
st.set_page_config(page_title="Production Record", layout="centered")
st.title("📝 บันทึกข้อมูลการผลิต")

# Load options
parts_df = load_part_options()
machines_df = load_machine_options()

# Form inputs
today = datetime.today().date()
log_date = st.date_input("วันที่", today)

selected_part = st.selectbox("Part No", parts_df["part_no"])
part_id = parts_df.loc[parts_df["part_no"] == selected_part, "id"].values[0]

shift = st.selectbox("กะ", ["Day", "Night"])

col1, col2 = st.columns(2)
with col1:
    plan_qty = st.number_input("Plan จำนวน", min_value=0, step=1)
with col2:
    actual_qty = st.number_input("Actual จำนวน", min_value=0, step=1)

defect_qty = st.number_input("Defect จำนวน", min_value=0, step=1)

# === เครื่องจักรและแผนก ===
machine_options = machines_df["machine_name"].tolist()
selected_machine_name = st.selectbox("เครื่องจักร", machine_options)
machine_row = machines_df[machines_df["machine_name"] == selected_machine_name]
machine_id = machine_row["id"].values[0]
department = machine_row["department"].values[0]

# จัด layout แสดงเครื่องจักรและแผนกแนวนอน
col4, col5 = st.columns(2)
with col4:
    st.text_input("เครื่องจักรที่เลือก", selected_machine_name, disabled=True)
with col5:
    st.text_input("แผนก", department, disabled=True)

remark = st.text_area("หมายเหตุ")
created_by = st.session_state.get("username", "admin")

# Submit button
if st.button("✅ บันทึกข้อมูล"):
    record = {
        "log_date": log_date,
        "shift": shift,
        "machine_id": machine_id,
        "part_id": part_id,
        "plan_qty": plan_qty,
        "actual_qty": actual_qty,
        "defect_qty": defect_qty,
        "remark": remark,
        "created_by": created_by
    }
    try:
        insert_production_record(record)
        st.success("✅ บันทึกข้อมูลสำเร็จแล้ว")
    except Exception as e:
        st.error(f"❌ บันทึกข้อมูลล้มเหลว: {e}")
