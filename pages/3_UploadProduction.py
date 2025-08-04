import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

st.set_page_config(page_title="Upload Production Log", layout="wide")
st.title("📤 Upload Production Log")

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Upload Section ===
uploaded_file = st.file_uploader("เลือกไฟล์งาน Production (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df, use_container_width=True)

    # ตรวจสอบคอลัมน์ที่จำเป็น
    required_columns = ["log_date", "shift", "department", "machine_id", "part_no", "plan_qty", "actual_qty", "defect_qty"]
    if not all(col in df.columns for col in required_columns):
        st.error(f"❌ ไฟล์ที่อัปโหลดต้องมีคอลัมน์: {', '.join(required_columns)}")
    else:
        if st.button("✅ อัปโหลดข้อมูลเข้า Database"):
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    for _, row in df.iterrows():
                        cur.execute("""
                            INSERT INTO production_log 
                            (log_date, shift, department, machine_id, part_no, plan_qty, actual_qty, defect_qty) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            pd.to_datetime(row["log_date"]).date(),
                            row["shift"],
                            row["department"],
                            row["machine_id"],
                            row["part_no"],
                            int(row["plan_qty"]),
                            int(row["actual_qty"]),
                            int(row["defect_qty"]),
                        ))
                    conn.commit()
                st.success("✅ อัปโหลดข้อมูลสำเร็จเรียบร้อยแล้ว")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")
