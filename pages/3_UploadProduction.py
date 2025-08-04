import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# === Page Config ===
st.set_page_config(page_title="Upload Production Log", layout="wide")
st.title("📤 Upload Production Log")

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load master data ===
@st.cache_data

def get_machine_master():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, machine_code FROM machine_list WHERE is_active = TRUE", conn)

def get_part_master():
    with get_connection() as conn:
        return pd.read_sql("SELECT id, part_no FROM part_master WHERE is_active = TRUE", conn)

# === Insert function ===
def insert_production_log_bulk(dataframe):
    with get_connection() as conn:
        cur = conn.cursor()
        for _, row in dataframe.iterrows():
            cur.execute("""
                INSERT INTO production_log 
                (log_date, shift, department, machine_id, part_id, plan_qty, actual_qty, defect_qty, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row['log_date'], row['shift'], row['department'], row['machine_id'], row['part_id'],
                int(row['plan_qty']), int(row['actual_qty']), int(row['defect_qty']),
                row.get('created_by', 'upload'), datetime.now()
            ))
        conn.commit()

# === Upload UI ===
uploaded_file = st.file_uploader("เลือกไฟล์งาน Production (.xlsx)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df, use_container_width=True)

    required_columns = ["log_date", "shift", "department", "machine_id", "part_no", "plan_qty", "actual_qty", "defect_qty"]
    if not all(col in df.columns for col in required_columns):
        st.error(f"❌ ไฟล์ที่อัปโหลดต้องมีคอลัมน์ดังนี้: {', '.join(required_columns)}")
        st.stop()

    # โหลด master
    machine_df = get_machine_master()
    part_df = get_part_master()

    # Map machine_id → id
    machine_map = dict(zip(machine_df["machine_code"], machine_df["id"]))
    df["machine_id"] = df["machine_id"].map(machine_map)

    # Map part_no → part_id
    part_map = dict(zip(part_df["part_no"], part_df["id"]))
    df["part_id"] = df["part_no"].map(part_map)

    if df["machine_id"].isnull().any():
        st.error("❌ มี machine_id ที่ไม่ตรงกับฐานข้อมูล กรุณาตรวจสอบ")
        st.stop()
    if df["part_id"].isnull().any():
        st.error("❌ มี part_no ที่ไม่ตรงกับฐานข้อมูล กรุณาตรวจสอบ")
        st.stop()

    if st.button("✅ อัปโหลดข้อมูลเข้า Database"):
        try:
            insert_production_log_bulk(df)
            st.success("✅ อัปโหลดข้อมูลเรียบร้อยแล้ว")
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
