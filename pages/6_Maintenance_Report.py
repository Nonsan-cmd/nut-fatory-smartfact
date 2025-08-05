import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Maintenance Data ===
def load_maintenance_data():
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM maintenance_log", conn)
    df["log_date"] = pd.to_datetime(df["log_date"]).dt.date
    df["created_at"] = pd.to_datetime(df["created_at"]) + timedelta(hours=7)
    df["completed_at"] = pd.to_datetime(df["completed_at"]) + timedelta(hours=7)
    return df

# === Sidebar Filters ===
st.sidebar.markdown("🔧 **ตัวกรองข้อมูลงานซ่อม**")
status_options = ["Pending", "Assigned", "Completed"]
selected_status = st.sidebar.multiselect("📌 สถานะ", status_options, default=status_options)

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT department FROM maintenance_log")
    departments = [row[0] for row in cursor.fetchall()]
selected_dept = st.sidebar.multiselect("🏭 แผนก", departments, default=departments)

start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", value=datetime.today() - timedelta(days=7))
end_date = st.sidebar.date_input("📅 วันที่สิ้นสุด", value=datetime.today())

# === Load and Filter Data ===
df = load_maintenance_data()
df_filtered = df[
    df["status"].isin(selected_status) &
    df["department"].isin(selected_dept) &
    (df["log_date"] >= start_date) &
    (df["log_date"] <= end_date)
]

# === Display Data ===
st.title("📊 รายงานซ่อมทั้งหมด")

col1, col2 = st.columns(2)
with col1:
    pending_count = df[df["status"] != "Completed"].shape[0]
    st.markdown(f"🛠 **งานคงค้าง:** `{pending_count}`")

with col2:
    completed_count = df[df["status"] == "Completed"].shape[0]
    st.markdown(f"✅ **ซ่อมเสร็จแล้ว:** `{completed_count}`")

st.dataframe(df_filtered.reset_index(drop=True))

# === Optional: Export CSV ===
st.download_button(
    label="📥 ดาวน์โหลดรายงาน CSV",
    data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name="maintenance_report.csv",
    mime="text/csv"
)
