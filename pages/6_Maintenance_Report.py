import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import pytz
import io
import requests

# === Telegram Setting ===
TELEGRAM_TOKEN = st.secrets["telegram"]["token"]
TELEGRAM_CHAT_ID = st.secrets["telegram"]["chat_id"]

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=params)
    except:
        st.warning("ส่งข้อความ Telegram ไม่สำเร็จ")

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Layout ===
st.set_page_config(page_title="Maintenance Report", layout="wide")
st.title("🛠 รายงานและติดตามงานซ่อมบำรุง")

# === แจ้งซ่อมใหม่ ===
with st.expander("📥 แจ้งซ่อมใหม่"):
    with st.form("แจ้งซ่อม"):
        col1, col2 = st.columns(2)
        with col1:
            log_date = st.date_input("📅 วันที่แจ้ง", datetime.now().date())
            shift = st.selectbox("🕘 กะ", ["Day", "Night"])
            department = st.text_input("🏭 แผนกที่แจ้ง")
        with col2:
            machine_name = st.text_input("⚙️ เครื่องจักร")
            reporter = st.text_input("👨‍🔧 ผู้แจ้งซ่อม")
            issue = st.text_area("❗ รายละเอียดปัญหา")

        submitted = st.form_submit_button("📨 แจ้งซ่อม")
        if submitted:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO maintenance_log (log_date, shift, department, machine_name, issue, reporter, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Pending', NOW())
                """, (log_date, shift, department, machine_name, issue, reporter))
                conn.commit()
            st.success("✅ แจ้งซ่อมเรียบร้อยแล้ว")
            send_telegram(f"📥 แจ้งซ่อมใหม่!\nแผนก: {department}\nเครื่อง: {machine_name}\nรายละเอียด: {issue}\nโดย: {reporter}")

# === โหลดข้อมูลทั้งหมด ===
@st.cache_data(ttl=300)
def load_data():
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM maintenance_log ORDER BY id DESC", conn)

df = load_data()

# === ยืนยันการซ่อมเสร็จ ===
st.subheader("✅ ยืนยันการซ่อมเสร็จ")
df_pending = df[df["status"] != "Completed"]
if df_pending.empty:
    st.info("ไม่มีรายการคงค้าง")
else:
    selected_row = st.selectbox("เลือกรายการที่ต้องการยืนยัน", df_pending["id"].astype(str) + " | " + df_pending["machine_name"] + " | " + df_pending["issue"])
    if st.button("✅ ยืนยันซ่อมเสร็จ"):
        job_id = int(selected_row.split(" | ")[0])
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE maintenance_log SET status='Completed', completed_at=NOW() WHERE id = %s
            """, (job_id,))
            conn.commit()
        st.success("✅ บันทึกเรียบร้อยแล้ว")
        send_telegram(f"✅ ซ่อมเสร็จแล้ว!\nJob ID: {job_id}")

# === มอบหมายงาน (Assign) ===
st.subheader("👨‍🔧 มอบหมายงานซ่อม")
df_assignable = df[df["status"] == "Pending"]
if not df_assignable.empty:
    selected_assign = st.selectbox("เลือกรายการเพื่อมอบหมาย", df_assignable["id"].astype(str) + " | " + df_assignable["machine_name"])
    assign_to = st.text_input("👷‍♂️ มอบหมายให้")
    if st.button("📌 มอบหมาย"):
        job_id = int(selected_assign.split(" | ")[0])
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE maintenance_log SET status='Assigned', assign_to=%s WHERE id = %s
            """, (assign_to, job_id))
            conn.commit()
        st.success("📌 มอบหมายงานเรียบร้อยแล้ว")
        send_telegram(f"📌 มอบหมายงานซ่อม!\nเครื่อง: {df_assignable[df_assignable['id']==job_id]['machine_name'].values[0]}\nผู้รับผิดชอบ: {assign_to}")

# === Report & Filter ===
st.subheader("📊 รายงานซ่อมทั้งหมด")

with st.expander("📎 ตัวกรอง"):
    status_filter = st.multiselect("📌 สถานะ", df["status"].unique().tolist(), default=df["status"].unique().tolist())
    dept_filter = st.multiselect("🏭 แผนก", df["department"].dropna().unique().tolist(), default=df["department"].dropna().unique().tolist())
    start = st.date_input("เริ่ม", value=df["log_date"].min())
    end = st.date_input("สิ้นสุด", value=df["log_date"].max())

df_filtered = df[
    (df["status"].isin(status_filter)) &
    (df["department"].isin(dept_filter)) &
    (df["log_date"] >= pd.to_datetime(start)) &
    (df["log_date"] <= pd.to_datetime(end))
]

# Format datetime + timezone
tz = pytz.timezone("Asia/Bangkok")
df_filtered["created_at"] = pd.to_datetime(df_filtered["created_at"]).dt.tz_localize("UTC").dt.tz_convert(tz)
df_filtered["completed_at"] = pd.to_datetime(df_filtered["completed_at"]).dt.tz_localize("UTC").dt.tz_convert(tz)

st.dataframe(df_filtered[["id", "log_date", "shift", "department", "machine_name", "issue", "reporter", "status", "assign_to", "created_at", "completed_at"]])

# === Export Button ===
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_filtered.to_excel(writer, index=False, sheet_name="Maintenance_Report")
st.download_button(
    label="📥 ดาวน์โหลดรายงาน Excel",
    data=buffer.getvalue(),
    file_name=f"maintenance_report_{datetime.now().date()}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
