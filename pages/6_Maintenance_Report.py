import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import pytz
import io
import requests

# === Config ===
tz = pytz.timezone("Asia/Bangkok")

# === Telegram Notification ===
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
    send_telegram_message(f"📩 แจ้งซ่อมใหม่\nเครื่อง: {machine_name}\nปัญหา: {issue}\nโดย: {reporter}\nแผนก: {department}")

# === Assign Job ===
def assign_job(job_id, assignee):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Assigned', assignee = %s WHERE id = %s
        """, (assignee, job_id))
        conn.commit()
    send_telegram_message(f"🛠 มอบหมายงานซ่อม\nID: {job_id}\nผู้รับผิดชอบ: {assignee}")

# === Complete Job ===
def complete_job(job_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE maintenance_log SET status = 'Completed', completed_at = %s WHERE id = %s
        """, (datetime.now(tz), job_id))
        conn.commit()
    send_telegram_message(f"✅ ซ่อมเสร็จแล้ว\nงานหมายเลข: {job_id}")

# === Load Repair Data ===
def load_repairs():
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM maintenance_log ORDER BY created_at DESC", conn)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_localize('UTC').dt.tz_convert(tz)
    df["completed_at"] = pd.to_datetime(df["completed_at"]).dt.tz_localize('UTC').dt.tz_convert(tz)
    return df

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

    with st.sidebar:
        st.markdown("## 🔍 ตัวกรองข้อมูล")
        status_filter = st.multiselect("📌 สถานะ", ["Pending", "Assigned", "Completed"], default=["Pending", "Assigned"])
        dept_filter = st.multiselect("🏭 แผนก", df["department"].unique().tolist(), default=df["department"].unique().tolist())
        start_date = st.date_input("วันที่เริ่มต้น", df["log_date"].min().date())
        end_date = st.date_input("วันที่สิ้นสุด", df["log_date"].max().date())
        export_btn = st.button("📥 Export รายงาน")

    # === Filter ===
    filtered_df = df[
        (df["status"].isin(status_filter)) &
        (df["department"].isin(dept_filter)) &
        (df["log_date"] >= pd.to_datetime(start_date)) &
        (df["log_date"] <= pd.to_datetime(end_date))
    ]

    # === Export ===
    if export_btn:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            filtered_df.to_excel(writer, index=False, sheet_name="Maintenance Report")
        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name="maintenance_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # === Show Filtered Data ===
    show_df = filtered_df[["log_date", "shift", "department", "machine_name", "issue", "reporter", "status", "assignee", "created_at", "completed_at"]]
    st.dataframe(show_df, use_container_width=True)

    st.markdown("### 🛠 ดำเนินการ (เฉพาะรายการที่ยังไม่ Completed)")
    action_df = filtered_df[filtered_df["status"] != "Completed"]

    for idx, row in action_df.iterrows():
        with st.expander(f"[{row['status']}] เครื่อง {row['machine_name']} - {row['issue']}"):
            st.text(f"แจ้งโดย: {row['reporter']} | แผนก: {row['department']} | วันที่: {row['log_date']} กะ: {row['shift']}")
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

# === Summary on Sidebar ===
st.sidebar.markdown("## 📊 สถานะงานซ่อม")
st.sidebar.metric("🔧 งานคงค้าง", df[df["status"] != "Completed"].shape[0])
st.sidebar.metric("✅ ซ่อมเสร็จแล้ว", df[df["status"] == "Completed"].shape[0])
