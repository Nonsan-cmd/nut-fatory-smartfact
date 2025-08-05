import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, date
import pytz
import io
import requests

# === CONNECT ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === TELEGRAM ===
def send_telegram_message(message):
    token = st.secrets["telegram"]["token"]
    chat_id = st.secrets["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except:
        st.error("ไม่สามารถส่งข้อความ Telegram ได้")

# === LOAD DATA ===
def load_maintenance_data():
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM maintenance_log ORDER BY log_date DESC", conn)
    df["log_date"] = pd.to_datetime(df["log_date"]).dt.date
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["completed_at"] = pd.to_datetime(df["completed_at"])
    return df

# === HEADER ===
st.set_page_config(page_title="Maintenance Report", layout="wide")
st.title("📊 รายงานซ่อมทั้งหมด")

df = load_maintenance_data()

# === FILTER SECTION ===
st.header("🎛 ตัวกรอง")

col1, col2, col3 = st.columns(3)
with col1:
    status_filter = st.multiselect("🛠️ สถานะ", options=df["status"].dropna().unique(), default=list(df["status"].unique()))
with col2:
    dept_filter = st.multiselect("🏭 แผนก", options=df["department"].dropna().unique(), default=list(df["department"].unique()))
with col3:
    start_date = st.date_input("📅 เริ่ม", date.today())
    end_date = st.date_input("📅 สิ้นสุด", date.today())

# === FILTER APPLY ===
df_filtered = df[
    (df["status"].isin(status_filter)) &
    (df["department"].isin(dept_filter)) &
    (df["log_date"] >= start_date) &
    (df["log_date"] <= end_date)
]

# === TABLE DISPLAY ===
st.dataframe(df_filtered[[
    "id", "log_date", "shift", "department", "machine_name",
    "issue", "reporter", "status", "assignee", "created_at", "completed_at"
]])

# === CONFIRM COMPLETION ===
st.subheader("⚙️ ดำเนินการ")

df_pending = df[df["status"] != "Completed"]

for i, row in df_pending.iterrows():
    with st.expander(f"[{row['status']}] เครื่อง {row['machine_name']} - {row['issue']}"):
        st.write(f"แจ้งโดย: {row['reporter']} | วันที่: {row['log_date']} กะ: {row['shift']} | แผนก: {row['department']}")
        if st.button("✅ ยืนยันการซ่อมเสร็จ", key=f"complete_{row['id']}"):
            with get_connection() as conn:
                cur = conn.cursor()
                completed_time = datetime.now(pytz.timezone("Asia/Bangkok"))
                cur.execute("""
                    UPDATE maintenance_log
                    SET status = 'Completed', completed_at = %s
                    WHERE id = %s
                """, (completed_time, row["id"]))
                conn.commit()
            msg = f"✅ ซ่อมเสร็จแล้ว\n🔧 เครื่อง: {row['machine_name']}\n📅 วันที่: {row['log_date']}\n👷‍♂️ ผู้แจ้ง: {row['reporter']}\n📌 ปัญหา: {row['issue']}"
            send_telegram_message(msg)
            st.success("อัปเดตสถานะเป็น Completed แล้ว")
            st.rerun()

# === SUMMARY BOX ===
st.sidebar.markdown("## 📌 สรุปงานซ่อม")
pending_count = df[df["status"] != "Completed"].shape[0]
completed_count = df[df["status"] == "Completed"].shape[0]
st.sidebar.markdown(f"🛠️ งานคงค้าง: **{pending_count}**")
st.sidebar.markdown(f"✅ ซ่อมเสร็จแล้ว: **{completed_count}**")

# === EXPORT TO EXCEL ===
st.subheader("⬇️ Export รายงาน")

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_filtered.to_excel(writer, sheet_name="Maintenance_Report", index=False)

st.download_button(
    label="📥 ดาวน์โหลด Excel",
    data=buffer.getvalue(),
    file_name=f"maintenance_report_{date.today()}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
