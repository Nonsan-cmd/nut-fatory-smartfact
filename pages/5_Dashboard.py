import streamlit as st
import pandas as pd
import psycopg2
from datetime import date

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Query Efficiency Report ===
def load_efficiency_report(start_date, end_date):
    with get_connection() as conn:
        sql = """
            SELECT 
                ml.department,
                pm.part_no,
                SUM(pl.plan_qty) AS plan_qty,
                SUM(pl.actual_qty) AS actual_qty,
                SUM(pl.defect_qty) AS defect_qty,
                SUM(COALESCE(pl.downtime_min, 0)) AS downtime_min,
                ROUND(
                    CASE 
                        WHEN SUM(pl.actual_qty * pm.std_cycle_time_sec) + SUM(COALESCE(pl.downtime_min, 0) * 60) = 0 THEN 0
                        ELSE 
                            (SUM(pl.actual_qty * pm.std_cycle_time_sec)::NUMERIC 
                            / (SUM(pl.actual_qty * pm.std_cycle_time_sec) + SUM(COALESCE(pl.downtime_min, 0) * 60)) * 100)
                    END
                , 1) AS "Efficiency (%)"
            FROM production_log pl
            INNER JOIN machine_list ml ON pl.machine_id = ml.id
            INNER JOIN part_master pm ON pl.part_id = pm.id
            WHERE pl.log_date BETWEEN %s AND %s
            GROUP BY ml.department, pm.part_no, pm.std_cycle_time_sec
            ORDER BY ml.department, pm.part_no
        """
        return pd.read_sql(sql, conn, params=(start_date, end_date))

# === UI ===
st.set_page_config(page_title="Dashboard Efficiency Report", layout="centered")
st.title("📊 Dashboard Efficiency Report")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", value=date.today())
with col2:
    end_date = st.date_input("📅 End Date", value=date.today())

if start_date > end_date:
    st.warning("📛 Start Date ต้องน้อยกว่าหรือเท่ากับ End Date")
else:
    df = load_efficiency_report(start_date, end_date)
    if df.empty:
        st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
    else:
        st.success(f"✅ พบทั้งหมด {len(df)} รายการ")
        st.dataframe(df, use_container_width=True)
        st.download_button(
            label="📥 ดาวน์โหลด Excel",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="efficiency_report.csv",
            mime="text/csv"
        )
