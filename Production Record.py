import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
from psycopg2.extras import RealDictCursor

# === CONFIG ===
st.set_page_config(page_title="Production Record", layout="wide")

# === CONNECTION ===
@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"], cursor_factory=RealDictCursor)

# === LOAD MASTER DATA ===
@st.cache_data(ttl=600)
def load_machines():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM machine_list WHERE is_active = TRUE ORDER BY machine_code", conn)

@st.cache_data(ttl=600)
def load_parts():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM part_master WHERE is_active = TRUE ORDER BY part_no", conn)

# === INSERT ===
def insert_data(data):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO production_log (
                log_date, shift, machine_id, part_id, plan_qty, actual_qty, defect_qty, remark, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, data)
        conn.commit()

# === MAIN UI ===
st.title("📝 Production Record Log")

machines_df = load_machines()
parts_df = load_parts()

with st.form("production_form"):
    col1, col2 = st.columns(2)

    with col1:
        log_date = st.date_input("📅 วันที่", value=date.today())
        selected_part = st.selectbox("🔩 เลือก Part No", parts_df["part_no"])
        shift = st.selectbox("🕐 กะการทำงาน", ["Day", "Night"])
        plan_qty = st.number_input("🎯 จำนวนเป้าหมาย (Plan)", min_value=0, step=1)

    with col2:
        selected_machine = st.selectbox("⚙️ เลือกเครื่องจักร", machines_df["machine_code"] + " - " + machines_df["machine_name"])
        actual_qty = st.number_input("✅ จำนวนผลิตจริง (Actual)", min_value=0, step=1)
        defect_qty = st.number_input("❌ ของเสีย (Defect)", min_value=0, step=1)

        # === Auto-fill Department ===
        if selected_machine:
            machine_code = selected_machine.split(" - ")[0]
            try:
                department = machines_df[machines_df["machine_code"] == machine_code]["department"].values[0]
                st.text_input("🏭 แผนก", value=department, disabled=True)
            except:
                st.warning("ไม่พบข้อมูลแผนก")

    remark = st.text_area("📝 หมายเหตุเพิ่มเติม")
    created_by = st.text_input("👷‍♂️ ชื่อผู้บันทึก", max_chars=50)

    submitted = st.form_submit_button("💾 บันทึกข้อมูล")

    if submitted:
        try:
            part_id = int(parts_df.loc[parts_df["part_no"] == selected_part, "id"].values[0])
            machine_id = int(machines_df.loc[machines_df["machine_code"] == machine_code, "id"].values[0])

            data = (
                str(log_date),
                str(shift),
                machine_id,
                part_id,
                int(plan_qty),
                int(actual_qty),
                int(defect_qty),
                str(remark),
                str(created_by)
            )

            insert_data(data)
            st.success("✅ บันทึกข้อมูลสำเร็จ")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
