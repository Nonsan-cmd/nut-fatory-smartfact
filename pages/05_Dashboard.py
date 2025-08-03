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
        query = """
            SELECT 
                m.machine_name, 
                m.department,
                p.production_date, 
                p.shift,
                p.plan_qty, 
                p.actual_qty, 
                p.defect_qty,
                d.downtime_minutes, 
                r.reason_name
            FROM production_log p
            LEFT JOIN machine_list m 
                ON p.machine_id = m.machine_id
            LEFT JOIN downtime_log d 
                ON p.machine_id = d.machine_id AND p.production_date = d.log_date
            LEFT JOIN downtime_reason_master r 
                ON d.reason_id = r.id
            WHERE p.production_date BETWEEN %s AND %s
        """
        df = pd.read_sql(query, conn, params=(start_date, end_date))
        return df

# === UI ===
st.title("📊 Dashboard Efficiency Report")

# Default date range: last 7 days
end_date = date.today()
start_date = end_date - timedelta(days=7)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", start_date)
with col2:
    end_date = st.date_input("📅 End Date", end_date)

# Load and display data
df = load_data(start_date, end_date)

if df.empty:
    st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
else:
    st.success(f"พบทั้งหมด {len(df)} รายการ")
    st.dataframe(df, use_container_width=True)
