import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import pytz
import io
import requests

# === Config ===
tz = pytz.timezone("Asia/Bangkok")
st.set_page_config(page_title="🛠 Maintenance Report", layout="wide")

# === Auth Check ===
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("กรุณาเข้าสู่ระบบก่อน")
    st.stop()

user = st.session_state.username
role = st.session_state.role

# === DB + Telegram ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

def send_telegram(message):
    token = st.secrets["telegram"]["token"]
    chat_id = st.secrets["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})

# === Insert / Update Functions ===
def insert_repair(log_date, shift, department, machine_name, issue, reporter):
    now = datetime.now(tz)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maintenance_log 
            (log_date, shift, department, machine_name, issue, reporter, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
        """, (log_date, shift, department, machine_name, issue, reporter, now))
        conn.commit()
    send_telegram(f"""📢 แจ้งซ่อมเครื่องจักร\n📅 วันที่: {log_date}\n🕘 กะ: {shift}\n🏭 แผนก: {department}\n⚙️ เครื่อง: {machine_name}\n🔧 ปัญหา: {issue}\n👤 ผู้แจ้ง: {reporter}""")

def assign_job(job_id, assignee):
    now = datetime.now(tz)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE maintenance_log SET status='Assigned', assignee=%s, assigned_at=%s WHERE id=%s", (assignee, now, job_id))
        conn.commit()
    send_telegram(f"📦 มอบหมายงานซ่อม #{job_id} ให้ {assignee}")

def start_repair(job_id):
    now = datetime.now(tz)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE maintenance_log SET repair_started_at=%s WHERE id=%s", (now, job_id))
        conn.commit()

def complete_job(job_id, spare_part_used):
    now = datetime.now(tz)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE maintenance_log SET status='Completed', completed_at=%s, spare_part=%s WHERE id=%s", (now, spare_part_used, job_id))
        conn.commit()
    send_telegram(f"✅ งานซ่อม #{job_id} เสร็จสมบูรณ์แล้ว")

# === Load Data ===
@st.cache_data(ttl=600)
def load_repairs():
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM maintenance_log ORDER BY created_at DESC", conn)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_localize(None)
    return df

# === Tabs ===
tab1, tab2 = st.tabs(["📩 แจ้งซ่อม", "📋 รายงาน / ยืนยัน"])

# === Tab1: แจ้งซ่อม ===
with tab1:
    st.subheader("📩 แจ้งซ่อมเครื่องจักร")
    if role in ["Operator", "Leader", "Officer", "Supervisor", "Admin"]:
        with st.form("repair_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                log_date = st.date_input("วันที่แจ้ง", datetime.now(tz).date())
                shift = st.selectbox("กะ", ["Day", "Night"])
                department = st.selectbox("แผนก", ["Production", "Engineering", "Tooling", "FM", "TP", "FI", "WH", "HR", "AF", "GA"])
            with col2:
                machine_name = st.text_input("ชื่อเครื่องจักร")
                issue = st.text_area("ปัญหา")
                reporter = st.text_input("ผู้แจ้ง", value=user)
            submitted = st.form_submit_button("📨 แจ้งซ่อม")
            if submitted:
                insert_repair(log_date, shift, department, machine_name, issue, reporter)
                st.success("✅ แจ้งซ่อมเรียบร้อย")

# === Tab2: รายงาน / ยืนยัน ===
with tab2:
    st.subheader("📋 รายการซ่อมบำรุง")
    df = load_repairs()

    # 🩹 Patch: แปลง log_date เป็น datetime ก่อน filter
    df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce")

    # === Filter ===
    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.date_input("📅 วันที่เริ่ม", datetime.now(tz).date() - timedelta(days=7))
    with col2:
        end = st.date_input("📅 วันที่สิ้นสุด", datetime.now(tz).date())
    with col3:
        status_filter = st.selectbox("กรองสถานะ", ["ทั้งหมด", "Pending", "Assigned", "Completed"])

    df = df[(df["log_date"] >= pd.to_datetime(start)) & (df["log_date"] <= pd.to_datetime(end))]
    if status_filter != "ทั้งหมด":
        df = df[df["status"] == status_filter]

    # === Export Excel ===
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 ดาวน์โหลด Excel", data=buffer.getvalue(), file_name="maintenance_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # === แสดงตาราง ===
    st.dataframe(df[[
        "id", "log_date", "shift", "department", "machine_name", "issue",
        "status", "reporter", "assignee", "spare_part_used",
        "created_at", "assigned_at", "start_repair_at", "completed_at", "verified_at"
    ]], use_container_width=True)
# === Summary Count ===
total_pending = df[df["status"].isin(["Pending", "Assigned", "Working"])].shape[0]
total_completed = df[df["status"] == "Completed"].shape[0]

col_a, col_b = st.columns(2)
with col_a:
    st.metric("🕒 งานที่ยังรอดำเนินการ", total_pending)
with col_b:
    st.metric("✅ งานที่ดำเนินการเสร็จแล้ว", total_completed)

    # === รายการดำเนินการ ===
    for _, row in df.iterrows():
        if row["status"] == "Completed":
            continue
        with st.expander(f"[{row['status']}] เครื่อง {row['machine_name']} - {row['issue']}"):
            st.text(f"📅 วันที่: {row['log_date']} | 🕘 กะ: {row['shift']} | 🏭 แผนก: {row['department']}")
            st.text(f"👤 ผู้แจ้ง: {row['reporter']} | 🔧 ผู้รับผิดชอบ: {row.get('assignee','-')}")
            if role in ["MN_Supervisor", "MN_Manager"] and row["status"] == "Pending":
                assignee = st.text_input(f"มอบหมายให้ใคร", key=f"assign_{row['id']}")
                if st.button("✅ Assign", key=f"btn_assign_{row['id']}"):
                    assign_job(row["id"], assignee)
                    st.rerun()
            if role in ["Technician"] and row["status"] == "Assigned":
                if st.button("▶️ เริ่มซ่อม", key=f"btn_start_{row['id']}"):
                    start_repair(row["id"])
                    st.rerun()
                spare = st.text_input("🧰 Spare Part ที่ใช้", key=f"spare_{row['id']}")
                if st.button("✅ ซ่อมเสร็จ", key=f"btn_done_{row['id']}"):
                    complete_job(row["id"], spare)
                    st.rerun()
