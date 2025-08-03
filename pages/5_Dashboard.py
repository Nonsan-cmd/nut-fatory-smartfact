import streamlit as st
import psycopg2
import pandas as pd
from datetime import date

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Efficiency Data ===
def load_efficiency_report(start_date, end_date):
    query = """
        SELECT 
            ml.department,
            pm.part_no,
            SUM(pl.plan_qty) AS plan_qty,
            SUM(pl.actual_qty) AS actual_qty,
            SUM(pl.defect_qty) AS defect_qty,
            COALESCE(dl.total_downtime_min, 0) AS downtime_min,
            COALESCE(dl.reason_summary, 'None') AS reason_name,
            ROUND(
                (SUM(pl.actual_qty) * pm.std_cycle_time_sec)::NUMERIC 
                / NULLIF(((SUM(pl.actual_qty) * pm.std_cycle_time_sec) + (COALESCE(dl.total_downtime_min, 0) * 60)), 0)
                * 100, 1
            ) AS "Efficiency (%)"
        FROM 
            production_log pl
        JOIN machine_list ml ON pl.machine_id = ml.id
        JOIN part_master pm ON pl.part_id = pm.id
        LEFT JOIN (
            SELECT 
                log_date, shift, machine_id,
                SUM(duration_min) AS total_downtime_min,
                STRING_AGG(dr.reason_name || ' (' || duration_min || 'min)', ', ') AS reason_summary
            FROM downtime_log dl
            JOIN downtime_reason_master dr ON dl.downtime_reason_id = dr.id
            GROUP BY log_date, shift, machine_id
        ) dl ON pl.log_date = dl.log_date AND pl.shift = dl.shift AND pl.machine_id = dl.machine_id
        WHERE pl.log_date BETWEEN %s AND %s
        GROUP BY ml.department, pm.part_no, pm.std_cycle_time_sec, dl.total_downtime_min, dl.reason_summary
        ORDER BY ml.department, pm.part_no
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn, params=(start_date, end_date))

# === UI ===
st.set_page_config(page_title="Efficiency Dashboard", page_icon="📊", layout="wide")
st.title("📊 Dashboard Efficiency Report")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", value=date.today())
with col2:
    end_date = st.date_input("📅 End Date", value=date.today())

df = load_efficiency_report(start_date, end_date)

if df.empty:
    st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
else:
    st.success(f"พบทั้งหมด {len(df)} รายการ")
    st.dataframe(df, use_container_width=True)
    st.download_button(
        label="📥 ดาวน์โหลด Excel",
        data=df.to_csv(index=False),
        file_name="efficiency_report.csv",
        mime="text/csv"
    )
