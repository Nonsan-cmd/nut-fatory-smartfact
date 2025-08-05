import streamlit as st
import requests
import psycopg2
from datetime import datetime

# === ตั้งค่า Page ===
st.set_page_config(page_title="แจ้งซ่อมเครื่องจักร", layout="centered")
st.title("🛠️ แจ้งซ่อมเครื่องจักร")

# === เชื่อมต่อ Database ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === ฟังก์ชันส่งข้อความ Telegram ===
def send_telegram_message(message):
    token = st.secrets["telegram"]["token"]
    chat_id = st.secrets["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
    try:
        requests.get(url)
    except Exception as e:
        st.error(f"❌ ไม่สามารถส่งข้อความ Telegram ได้: {e}")

# === Form แจ้งซ่อม ===
with st.form("maintenance_form"):
    log_date = st.date_input("📅 วันที่", datetime.today())
    shift = st.selectbox("🕘 กะ", ["Day", "Night"])
    department = st.selectbox("🏭 แผนก", ["Forming", "Tapping", "Final Inspection", "Other"])
    machine_name = st.text_input("⚙️ ชื่อเครื่องจักร")
    issue = st.text_area("🔧 รายละเอียดปัญหา")
    reporter = st.text_input("👤 ผู้แจ้ง")

    submitted = st.form_submit_button("📨 แจ้งซ่อม")

    if submitted:
        if not machine_name or not issue or not reporter:
            st.warning("❗ กรุณากรอกข้อมูลให้ครบถ้วน")
        else:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO maintenance_log (log_date, shift, department, machine_name, issue, reporter, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (log_date, shift, department, machine_name, issue, reporter))
                conn.commit()

            st.success("✅ บันทึกการแจ้งซ่อมเรียบร้อยแล้ว")

            # === ส่งข้อความ Telegram ===
            message = (
                f"📢 แจ้งซ่อมเครื่องจักร\n"
                f"📅 วันที่: {log_date.strftime('%Y-%m-%d')}\n"
                f"🕘 กะ: {shift}\n"
                f"🏭 แผนก: {department}\n"
                f"⚙️ เครื่อง: {machine_name}\n"
                f"🔧 ปัญหา: {issue}\n"
                f"👤 ผู้แจ้ง: {reporter}"
            )
            send_telegram_message(message)
