import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load all necessary data ===
@st.cache_data
def load_data(start_date, end_date):
    with get_connection() as conn:
        query = f"""
        SELECT p.machine_id, m.machine_name, m.department, p.production_date, p.shift,
               p.actual_qty, p.plan_qty,
               d.downtime_minutes, r.reason_name
        FROM production_log p
        LEFT JOIN machine_list m ON p.machine_id = m.id
        LEFT JOIN downtime_log d ON p.machine_id = d.machine_id AND p.production_date = d.log_date
        LEFT JOIN downtime_reason_master r ON d.reason_id = r.id
        WHERE p.production_date BETWEEN %s AND %s
        """
        df = pd.read_sql(query, conn, params=(start_date, end_date))
    return df

# === UI Filters ===
st.header("📊 Dashboard Efficiency & Downtime")

today = date.today()
start_date = st.date_input("📅 Start date", today - timedelta(days=7))
end_date = st.date_input("📅 End date", today)

df = load_data(start_date, end_date)

if df.empty:
    st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
    st.stop()

# Filter แผนก และเครื่องจักร
departments = df["department"].dropna().unique().tolist()
selected_dept = st.selectbox("🏭 เลือกแผนก", ["ทั้งหมด"] + departments)

if selected_dept != "ทั้งหมด":
    df = df[df["department"] == selected_dept]

machines = df["machine_name"].dropna().unique().tolist()
selected_machine = st.selectbox("🛠 เลือกเครื่องจักร", ["ทั้งหมด"] + machines)

if selected_machine != "ทั้งหมด":
    df = df[df["machine_name"] == selected_machine]

# === Summary Calculation ===
summary = df.groupby(["machine_name", "production_date", "shift"]).agg(
    actual_qty=("actual_qty", "sum"),
    plan_qty=("plan_qty", "sum"),
    downtime_min=("downtime_minutes", "sum"),
    top_reason=("reason_name", lambda x: x.mode()[0] if not x.mode().empty else "-")
).reset_index()

summary["efficiency (%)"] = round((summary["actual_qty"] / summary["plan_qty"]) * 100, 2)

# === Display Table ===
st.subheader("📋 ตารางสรุปประสิทธิภาพ")
st.dataframe(summary, use_container_width=True)
