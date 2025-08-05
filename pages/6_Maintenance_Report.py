# 6_Maintenance_Report.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import pytz

# === Config ===
tz = pytz.timezone("Asia/Bangkok")

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Add New Repair Request ===
def insert_repair(log_date, shift, department, machine_name, issue, reporter):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maintenance_log 
            (log_date, shift, department, machine_name, issue, reporter, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
        """, (log_date, shift, department, machine_name, issue, reporter, datetime.now(tz)))
        conn.commit()

# === Assign Job ===
def assign_job(job_id, assignee):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Assigned', assignee = %s WHERE id = %s
        """, (assignee, job_id))
        conn.commit()

# === Complete Job ===
def complete_job(job_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Completed', completed_at = %s WHERE id = %s
        """, (datetime.now(tz), job_id))
        conn.commit()

# === Load Repair Data ===
def load_repairs():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM maintenance_log ORDER BY created_at DESC", conn)

# === UI ===
st.title("🛠 Maintenance Report")

tab1, tab2 = st.tabs(["📩 แจ้งซ่อม", "📋 รายงาน / ยืนยัน"])

with tab1:
    st.subheader("📩 แจ้งซ่อมใหม่")
    with st.form("repair_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            log_date = st.date_input("วันที่แจ้งซ่อม", datetime.now(tz).date())
            shift = st.selectbox("กะ", ["Day", "Night"])
            department = st.selectbox("แผนก", ["Forming", "Tapping", "Final", "Outsource", "Warehouse"])
        with col2:
            machine_name = st.text_input("ชื่อเครื่องจักร")
            issue = st.text_area("ปัญหา")
            reporter = st.text_input("ผู้แจ้ง")
        submitted = st.form_submit_button("📨 แจ้งซ่อม")
        if submitted:
            insert_repair(log_date, shift, department, machine_name, issue, reporter)
            st.success("✅ แจ้งซ่อมเรียบร้อยแล้ว")

with tab2:
    st.subheader("📋 รายการแจ้งซ่อมทั้งหมด")
    df = load_repairs()
    status_filter = st.selectbox("กรองสถานะ", ["ทั้งหมด", "Pending", "Assigned", "Completed"])
    if status_filter != "ทั้งหมด":
        df = df[df["status"] == status_filter]

    st.dataframe(df)

    st.markdown("### 🛠 ดำเนินการ")
    for idx, row in df.iterrows():
        with st.expander(f"[{row['status']}] เครื่อง {row['machine_name']} - {row['issue']}"):
            st.text(f"แจ้งโดย: {row['reporter']} | วันที่: {row['log_date']} กะ: {row['shift']}")
            if row["status"] == "Pending":
                assignee = st.text_input(f"มอบหมายให้ใคร (งาน #{row['id']})", key=f"assign_{row['id']}")
                if st.button("✅ Assign", key=f"btn_assign_{row['id']}"):
                    assign_job(row["id"], assignee)
                    st.success("มอบหมายงานเรียบร้อย")
                    st.rerun()
            elif row["status"] == "Assigned":
                if st.button("✅ ยืนยันการซ่อมเสร็จ", key=f"btn_complete_{row['id']}"):
                    complete_job(row["id"])
                    st.success("บันทึกการซ่อมเสร็จแล้ว")
                    st.rerun()

# === Summary Count for Dashboard ===
pending_count = df[df["status"] != "Completed"].shape[0]
completed_count = df[df["status"] == "Completed"].shape[0]
st.sidebar.metric("🔧 งานคงค้าง", pending_count)
st.sidebar.metric("✅ ซ่อมเสร็จแล้ว", completed_count)
