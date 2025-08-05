import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import pytz
import io
import requests

# === Config ===
tz = pytz.timezone("Asia/Bangkok")
st.set_page_config(page_title="Maintenance Report", layout="wide")

# === Telegram ===
def send_telegram_message(message):
    token = st.secrets["telegram"]["token"]
    chat_id = st.secrets["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
    try:
        requests.get(url)
    except Exception as e:
        st.error(f"Telegram Error: {e}")

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === DB Actions ===
def insert_repair(log_date, shift, department, machine_name, issue, reporter):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO maintenance_log 
            (log_date, shift, department, machine_name, issue, reporter, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
        """, (log_date, shift, department, machine_name, issue, reporter, datetime.now(tz)))
        conn.commit()
    send_telegram_message(f"🛠 แจ้งซ่อมใหม่\nเครื่อง: {machine_name}\nปัญหา: {issue}\nโดย: {reporter}")

def assign_job(job_id, assignee):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE maintenance_log SET status = 'Assigned', assignee = %s WHERE id = %s", (assignee, job_id))
        conn.commit()
    send_telegram_message(f"📌 มอบหมายงานซ่อม #{job_id} ให้ {assignee}")

def complete_job(job_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE maintenance_log SET status = 'Completed', completed_at = %s WHERE id = %s", (datetime.now(tz), job_id))
        conn.commit()
    send_telegram_message(f"✅ งานซ่อม #{job_id} เสร็จเรียบร้อยแล้ว")

def load_repairs():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM maintenance_log ORDER BY created_at DESC", conn)

# === Main UI ===
st.title("🛠 Maintenance Report")

tab1, tab2 = st.tabs(["📩 แจ้งซ่อม", "📋 รายงาน / ดำเนินการ"])

# === แจ้งซ่อมใหม่ ===
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

# === รายงานทั้งหมด + ดำเนินการ ===
with tab2:
    st.subheader("📋 รายงานซ่อมทั้งหมด")

    df = load_repairs()

    # === Fix timezone handling ===
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["completed_at"] = pd.to_datetime(df["completed_at"])
    df["log_date"] = pd.to_datetime(df["log_date"])

    df["created_at"] = df["created_at"].dt.tz_localize("UTC").dt.tz_convert(tz)
    df["completed_at"] = df["completed_at"].dt.tz_localize("UTC").dt.tz_convert(tz)
    df["log_date"] = df["log_date"].dt.tz_localize("UTC").dt.tz_convert(tz)

    # === Sidebar Filter ===
    st.sidebar.header("🔎 ตัวกรองข้อมูล")
    start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=df["log_date"].min().date() if not df.empty else datetime.now(tz).date())
    end_date = st.sidebar.date_input("วันที่สิ้นสุด", value=df["log_date"].max().date() if not df.empty else datetime.now(tz).date())
    status_list = st.sidebar.multiselect("🛠 สถานะงานซ่อม", options=df["status"].unique().tolist(), default=list(df["status"].unique()))
    dept_list = st.sidebar.multiselect("🏭 แผนก", options=df["department"].unique().tolist(), default=list(df["department"].unique()))

    filtered_df = df[
        (df["log_date"].dt.date >= start_date) &
        (df["log_date"].dt.date <= end_date) &
        (df["status"].isin(status_list)) &
        (df["department"].isin(dept_list))
    ]

    # === Export Button ===
    csv = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 ดาวน์โหลดรายงาน (CSV)", data=csv, file_name="maintenance_report.csv", mime="text/csv")

    # === Summary Sidebar ===
    st.sidebar.header("📊 สถานะงานซ่อม")
    st.sidebar.metric("🟡 คงค้าง", df[df["status"] != "Completed"].shape[0])
    st.sidebar.metric("✅ ซ่อมเสร็จแล้ว", df[df["status"] == "Completed"].shape[0])

    # === Data Table ===
    st.dataframe(filtered_df[[
        "id", "log_date", "shift", "department", "machine_name", "issue",
        "reporter", "assignee", "status", "created_at", "completed_at"
    ]], use_container_width=True)

    # === In-Progress Operations ===
    st.markdown("### 🛠 งานที่ยังไม่เสร็จ")
    not_done_df = filtered_df[filtered_df["status"] != "Completed"]

    for _, row in not_done_df.iterrows():
        with st.expander(f"[{row['status']}] {row['machine_name']} - {row['issue']} (แผนก: {row['department']})"):
            st.text(f"แจ้งโดย: {row['reporter']} | วันที่แจ้ง: {row['log_date'].strftime('%Y-%m-%d')} | กะ: {row['shift']}")
            if row["status"] == "Pending":
                assignee = st.text_input(f"มอบหมายให้ใคร (#{row['id']})", key=f"assign_{row['id']}")
                if st.button("✅ มอบหมาย", key=f"btn_assign_{row['id']}"):
                    assign_job(row["id"], assignee)
                    st.success("มอบหมายงานเรียบร้อย")
                    st.rerun()
            elif row["status"] == "Assigned":
                if st.button("✅ ยืนยันซ่อมเสร็จ", key=f"btn_complete_{row['id']}"):
                    complete_job(row["id"])
                    st.success("บันทึกการซ่อมเสร็จแล้ว")
                    st.rerun()
