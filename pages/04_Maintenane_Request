import streamlit as st
import psycopg2
from datetime import datetime
import requests

# === Telegram Configuration ===
TELEGRAM_TOKEN = "8479232119:AAEVm2sS365HzMHoeoQGOynqUVPV70A-jHA"
TELEGRAM_CHAT_ID = "-4786867430"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"ไม่สามารถส่งข้อความแจ้งเตือน Telegram ได้: {e}")

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

def insert_repair_request(data):
    with get_connection() as conn:
        cur = conn.cursor()
        query = """
        INSERT INTO repair_request (log_date, shift, department, machine_name, issue_description, reported_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, (
            data["log_date"], data["shift"], data["department"], data["machine_name"],
            data["issue_description"], data["reported_by"], data["created_at"]
        ))
        conn.commit()

# === Streamlit Page ===
st.set_page_config(page_title="แจ้งซ่อมเครื่องจักร", layout="centered")
st.title("🛠️ แจ้งซ่อมเครื่องจักร")

with st.form("repair_form"):
    st.markdown("กรุณากรอกข้อมูลให้ครบถ้วน")
    log_date = st.date_input("📅 วันที่แจ้งซ่อม", datetime.today())
    shift = st.selectbox("🕘 กะการทำงาน", ["Day", "Night"])
    department = st.selectbox("🏭 แผนก", ["FM", "TP", "FI", "OS", "WH"])
    machine_name = st.text_input("⚙️ ชื่อเครื่องจักร")
    issue_description = st.text_area("❗ รายละเอียดปัญหา")
    reported_by = st.text_input("👤 ผู้แจ้งซ่อม")
    submitted = st.form_submit_button("📤 แจ้งซ่อม")

    if submitted:
        if not all([log_date, shift, department, machine_name, issue_description, reported_by]):
            st.warning("กรุณากรอกข้อมูลให้ครบถ้วนก่อนแจ้งซ่อม")
        else:
            data = {
                "log_date": log_date,
                "shift": shift,
                "department": department,
                "machine_name": machine_name,
                "issue_description": issue_description,
                "reported_by": reported_by,
                "created_at": datetime.now(),
            }
            try:
                insert_repair_request(data)
                telegram_msg = f"📢 แจ้งซ่อมใหม่\nวันที่: {log_date}\nกะ: {shift}\nแผนก: {department}\nเครื่อง: {machine_name}\nรายละเอียด: {issue_description}\nผู้แจ้ง: {reported_by}"
                send_telegram_message(telegram_msg)
                st.success("✅ แจ้งซ่อมสำเร็จและส่งข้อความไปยัง Telegram แล้ว")
            except Exception as e:
                st.error(f"❌ แจ้งซ่อมไม่สำเร็จ: {e}")
