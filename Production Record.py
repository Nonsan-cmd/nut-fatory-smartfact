import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Master Data ===
@st.cache_data
def load_master_data():
    with get_connection() as conn:
        machines_df = pd.read_sql("SELECT * FROM machine_list WHERE is_active = TRUE ORDER BY machine_code", conn)
        parts_df = pd.read_sql("SELECT * FROM part_master WHERE is_active = TRUE ORDER BY part_no", conn)
    return machines_df, parts_df

# === Insert Function ===
def insert_data(data):
    with get_connection() as conn:
        cur = conn.cursor()
        insert_query = """
            INSERT INTO production_log 
            (log_date, shift, machine_id, part_id, plan_qty, actual_qty, defect_qty, remark, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(insert_query, data)
        conn.commit()

# === UI Layout ===
st.markdown("## 📝 บันทึกข้อมูลการผลิต")
machines_df, parts_df = load_master_data()

with st.form("production_form"):
    col1, col2 = st.columns(2)

    with col1:
        log_date = st.date_input("วันที่", value=date.today())
        selected_part = st.selectbox("Part No", parts_df["part_no"].unique())
        shift = st.selectbox("กะ", ["Day", "Night"])
        plan_qty = st.number_input("Plan จำนวน", min_value=0, step=1)

    with col2:
        selected_machine = st.selectbox("เครื่องจักร", machines_df["machine_code"] + " - " + machines_df["machine_name"])
        actual_qty = st.number_input("Actual จำนวน", min_value=0, step=1)
        defect_qty = st.number_input("Defect จำนวน", min_value=0, step=1)

        # แสดงชื่อแผนก
        machine_code = selected_machine.split(" - ")[0]
        department = machines_df[machines_df["machine_code"] == machine_code]["department"].values[0]
        st.text_input("แผนก", value=department, disabled=True)

    remark = st.text_area("หมายเหตุ")
    created_by = st.text_input("ชื่อผู้บันทึก", max_chars=50)

    submitted = st.form_submit_button("💾 บันทึกข้อมูล")
    if submitted:
        try:
            part_id = int(parts_df.loc[parts_df["part_no"] == selected_part, "id"].values[0])
            machine_id = int(machines_df.loc[machines_df["machine_code"] == machine_code, "id"].values[0])

            data = (
                str(log_date),
                shift,
                machine_id,
                part_id,
                int(plan_qty),
                int(actual_qty),
                int(defect_qty),
                remark,
                created_by
            )

            insert_data(data)
            st.success("✅ บันทึกข้อมูลสำเร็จ")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
