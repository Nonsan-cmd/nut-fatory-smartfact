import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
from io import BytesIO

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Data ===
@st.cache_data(ttl=600)
def load_data(start_date, end_date):
    query = """
    SELECT pl.log_date, pl.shift, ml.machine_name, pm.part_no,
           pl.plan_qty, pl.actual_qty, pl.defect_qty,
           COALESCE(SUM(dl.duration_min), 0) AS total_downtime_min
    FROM production_log pl
    JOIN machine_list ml ON pl.machine_id = ml.id
    JOIN part_master pm ON pl.part_id = pm.id
    LEFT JOIN downtime_log dl
        ON pl.log_date = dl.log_date
       AND pl.shift = dl.shift
       AND pl.machine_id = dl.machine_id
    WHERE pl.log_date BETWEEN %s AND %s
    GROUP BY pl.log_date, pl.shift, ml.machine_name, pm.part_no,
             pl.plan_qty, pl.actual_qty, pl.defect_qty
    ORDER BY pl.log_date DESC, ml.machine_name
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params=(start_date, end_date))
    return df

# === Calculate Efficiency ===
def calculate_efficiency(row):
    produced = row["actual_qty"]
    plan = row["plan_qty"]
    downtime = row["total_downtime_min"]
    total_time = 480 - downtime  # 8 ชั่วโมง = 480 นาที
    if total_time <= 0 or pd.isna(plan) or plan == 0:
        return 0
    return round((produced / plan) * 100, 2)

# === UI ===
st.title("📊 Dashboard Efficiency")

# Date filters
def_date = datetime.now().date()
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 วันที่เริ่มต้น", value=def_date - timedelta(days=7))
with col2:
    end_date = st.date_input("📅 วันที่สิ้นสุด", value=def_date)

# Load data
data = load_data(start_date, end_date)

# Dropdown filters
with st.expander("🔍 ตัวกรองเพิ่มเติม"):
    machines = data["machine_name"].unique().tolist()
    shifts = data["shift"].unique().tolist()
    
    selected_machines = st.multiselect("เลือกเครื่องจักร", machines, default=machines)
    selected_shifts = st.multiselect("เลือกกะ", shifts, default=shifts)

# Apply filters
filtered_data = data[
    (data["machine_name"].isin(selected_machines)) &
    (data["shift"].isin(selected_shifts))
].copy()

# Calculate efficiency
filtered_data["Efficiency (%)"] = filtered_data.apply(calculate_efficiency, axis=1)

# Display table
st.dataframe(filtered_data, use_container_width=True)

# Export to Excel
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    filtered_data.to_excel(writer, index=False, sheet_name="Efficiency")
    writer.save()

st.download_button(
    label="📥 ดาวน์โหลด Excel",
    data=buffer,
    file_name="efficiency_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
