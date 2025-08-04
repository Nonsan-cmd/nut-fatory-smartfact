import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# === DB Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === โหลดข้อมูลจาก Supabase ===
@st.cache_data
def get_machines_df():
    with get_connection() as conn:
        return pd.read_sql("SELECT id AS machine_id, machine_name FROM machine_list WHERE is_active = TRUE", conn)

@st.cache_data
def get_parts_df():
    with get_connection() as conn:
        return pd.read_sql("SELECT id AS part_id, part_no FROM part_master WHERE is_active = TRUE", conn)

# === Insert ฟังก์ชัน ===
def insert_batch_to_production_log(df):
    with get_connection() as conn:
        cur = conn.cursor()
        for _, row in df.iterrows():
            sql = """
                INSERT INTO production_log
                (log_date, shift, department, machine_id, part_id, plan_qty, actual_qty, defect_qty, remark, created_by, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            values = (
                row["log_date"], row["shift"], row["department"],
                int(row["machine_id"]), int(row["part_id"]),
                int(row["plan_qty"]), int(row["actual_qty"]), int(row["defect_qty"]),
                row.get("remark", ""), row["created_by"], datetime.now()
            )
            cur.execute(sql, values)
        conn.commit()

# === UI เริ่ม ===
st.title("📤 Upload Production Log")

uploaded_file = st.file_uploader("เลือกไฟล์งาน Production (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        st.write("📄 ข้อมูลที่อัปโหลด:")
        st.dataframe(df)

        required_columns = ["log_date", "shift", "department", "machine_name", "part_no",
                            "plan_qty", "actual_qty", "defect_qty", "created_by"]
        if not all(col in df.columns for col in required_columns):
            st.error(f"❌ ไฟล์ที่อัปโหลดต้องมีคอลัมน์ดังนี้: {', '.join(required_columns)}")
        else:
            # โหลด Mapping
            machines_df = get_machines_df()
            parts_df = get_parts_df()

            # Mapping machine_id
            df = df.merge(machines_df, how="left", on="machine_name")
            df = df.merge(parts_df, how="left", on="part_no")

            # ตรวจสอบว่า map ได้ครบไหม
            if df["machine_id"].isnull().any():
                st.error("❌ มี machine_name ที่ไม่ตรงกับฐานข้อมูล กรุณาตรวจสอบ")
            elif df["part_id"].isnull().any():
                st.error("❌ มี part_no ที่ไม่ตรงกับฐานข้อมูล กรุณาตรวจสอบ")
            else:
                if st.button("✅ อัปโหลดข้อมูลเข้า Database"):
                    insert_batch_to_production_log(df)
                    st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว!")

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")
