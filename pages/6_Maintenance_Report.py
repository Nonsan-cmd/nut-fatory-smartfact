import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import pytz
import io
import requests

# === CONFIG ===
tz = pytz.timezone("Asia/Bangkok")
TELEGRAM_TOKEN = "8479232119:AAEVm2sS365HzMHoeoQGOynqUVPV70A-jHA"
CHAT_ID = "-4786867430"

# === FUNCTION: Telegram Notify ===
def send_telegram_message(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": msg}
        requests.get(url, params=params)
    except:
        pass

# === CONNECTION ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === DB ACTIONS ===
def insert_repair(log_date, shift, department, machine_name, issue, reporter):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maintenance_log 
            (log_date, shift, department, machine_name, issue, reporter, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
        """, (log_date, shift, department, machine_name, issue, reporter, datetime.now(tz)))
        conn.commit()
    send_telegram_message(f"📩 แจ้งซ่อมใหม่\nเครื่อง: {machine_name}\nปัญหา: {issue}\nโดย: {reporter}\nแผนก: {department}")

def assign_job(job_id, assignee):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Assigned', assignee = %s WHERE id = %s
        """, (assignee, job_id))
        conn.commit()
    send_telegram_message(f"✅ มอบหมายงานซ่อม #{job_id} ให้ {assignee}")

def complete_job(job_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Completed', completed_at = %s WHERE id = %s
        """, (datetime.now(tz), job_id))
        conn.commit()
    send_telegram_message(f"✅ ยืนยันการซ่อมเสร็จสำหรับงาน #{job_id}")

def load_repairs():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM maintenance_log ORDER BY created_at DESC", conn)

# === UI ===
st.set_page_config(page_title="Maintenance Report", layout="wide")
st.title("🛠 รายงานงานซ่อมบำรุง")

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
    st.subheader("📋 รายงานและยืนยันการซ่อม")

    df = load_repairs()
    df["log_date"] = pd.to_datetime(df["log_date"])
    df["completed_at"] = pd.to_datetime(df["completed_at"]).dt.tz_localize("UTC").dt.tz_convert(tz)
    df["completed_at"] = pd.to_datetime(df["completed_at"]).dt.tz_localize("UTC").dt.tz_convert(tz) if "completed_at" in df.columns else None

    colf1, colf2 = st.columns(2)
    with colf1:
        start = st.date_input("📅 จากวันที่", datetime.now(tz).date() - timedelta(days=7))
    with colf2:
        end = st.date_input("📅 ถึงวันที่", datetime.now(tz).date())

    status_filter = st.selectbox("กรองสถานะ", ["ทั้งหมด", "Pending", "Assigned", "Completed"])
    dept_filter = st.selectbox("แผนกที่แจ้ง", ["ทั้งหมด"] + sorted(df["department"].unique()))

    df = df[(df["log_date"] >= pd.to_datetime(start)) & (df["log_date"] <= pd.to_datetime(end))]
    if status_filter != "ทั้งหมด":
        df = df[df["status"] == status_filter]
    if dept_filter != "ทั้งหมด":
        df = df[df["department"] == dept_filter]

    st.dataframe(df[["id", "log_date", "shift", "department", "machine_name", "issue", "reporter", "status", "assignee", "created_at", "completed_at"]], use_container_width=True)

    # Export Button
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Maintenance Report')
    st.download_button("⬇️ Export to Excel", data=buffer.getvalue(),
                       file_name=f"maintenance_report_{datetime.now(tz).date()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("### 🛠 ดำเนินการซ่อม (ไม่รวมที่เสร็จแล้ว)")
    df_pending = df[df["status"].isin(["Pending", "Assigned"])]
    for idx, row in df_pending.iterrows():
        with st.expander(f"[{row['status']}] #{row['id']} | เครื่อง: {row['machine_name']} | ปัญหา: {row['issue']}"):
            st.text(f"แผนก: {row['department']} | แจ้งโดย: {row['reporter']} | วันที่: {row['log_date']} | กะ: {row['shift']}")
            if row["status"] == "Pending":
                assignee = st.text_input(f"🧑‍🔧 มอบหมายให้ (#{row['id']})", key=f"assign_{row['id']}")
                if st.button("✅ Assign", key=f"btn_assign_{row['id']}"):
                    assign_job(row["id"], assignee)
                    st.success("มอบหมายงานแล้ว")
                    st.rerun()
            elif row["status"] == "Assigned":
                if st.button("✅ ยืนยันการซ่อมเสร็จ", key=f"btn_complete_{row['id']}"):
                    complete_job(row["id"])
                    st.success("บันทึกการซ่อมเสร็จแล้ว")
                    st.rerun()

# === Summary in Sidebar ===
pending_count = df[df["status"] != "Completed"].shape[0]
completed_count = df[df["status"] == "Completed"].shape[0]
st.sidebar.metric("🔧 งานคงค้าง", pending_count)
st.sidebar.metric("✅ ซ่อมเสร็จแล้ว", completed_count)
