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
uploaded_file = st.file_uploader("เลือกรายงาน Production (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df, use_container_width=True)

    # ตรวจสอบคอลัมน์ที่จำเป็น
    required_columns = ["log_date", "shift", "department", "machine_name", "part_no", "plan_qty", "actual_qty", "defect_qty"]
    if not all(col in df.columns for col in required_columns):
        st.error(f"❌ ไฟล์ที่อัปโหลดต้องมีคอลัมน์: {', '.join(required_columns)}")
    else:
        # แปลงวันที่ และชนิดข้อมูล
        df["log_date"] = pd.to_datetime(df["log_date"]).dt.date
        df["plan_qty"] = df["plan_qty"].astype(int)
        df["actual_qty"] = df["actual_qty"].astype(int)
        df["defect_qty"] = df["defect_qty"].astype(int)

        if st.button("✅ อัปโหลดข้อมูลเข้า Database"):
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    for _, row in df.iterrows():
                        cur.execute("""
                            INSERT INTO production_log (log_date, shift, department, machine_name, part_no, plan_qty, actual_qty, defect_qty, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row["log_date"],
                            row["shift"],
                            row["department"],
                            row["machine_name"],
                            row["part_no"],
                            row["plan_qty"],
                            row["actual_qty"],
                            row["defect_qty"],
                            datetime.now()
                        ))
                    conn.commit()
                st.success("✅ อัปโหลดข้อมูลสำเร็จแล้ว")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")
