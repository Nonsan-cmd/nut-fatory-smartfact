import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import plotly.express as px

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Efficiency Report ===
def load_efficiency_report(start_date, end_date, department_filter=None):
    with get_connection() as conn:
        sql = """
            SELECT 
                ml.department,
                ml.machine_name,
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
                , 1) AS efficiency
            FROM production_log pl
            JOIN machine_list ml ON pl.machine_id = ml.id
            JOIN part_master pm ON pl.part_id = pm.id
            WHERE pl.log_date BETWEEN %s AND %s
            """
        params = [start_date, end_date]
        if department_filter and department_filter != "All":
            sql += " AND ml.department = %s"
            params.append(department_filter)
        sql += """
            GROUP BY ml.department, ml.machine_name, pm.part_no, pm.std_cycle_time_sec
            ORDER BY ml.department, ml.machine_name, pm.part_no
        """
        return pd.read_sql(sql, conn, params=params)

# === Streamlit UI ===
st.set_page_config(page_title="Dashboard Efficiency Report", layout="wide")
st.title("\U0001F4CA Dashboard Efficiency Report")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("\U0001F4C5 Start Date", value=date.today())
with col2:
    end_date = st.date_input("\U0001F4C5 End Date", value=date.today())

# Department filter
with st.sidebar:
    st.header("\U0001F3E2 ตัวกรองรายแผนก")
    department_filter = st.selectbox("เลือกแผนก:", options=["All", "Forming", "Tapping", "Final", "Warehouse", "Other"])

if start_date > end_date:
    st.warning("\U0001F6DB Start Date ต้องน้อยกว่าหรือเท่ากับ End Date")
else:
    df = load_efficiency_report(start_date, end_date, department_filter)
    if df.empty:
        st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
    else:
        st.success(f"\u2705 พบทั้งหมด {len(df)} รายการ")
        st.dataframe(df, use_container_width=True)

        # Chart
        fig = px.bar(
            df,
            x="machine_name",
            y="efficiency",
            color="department",
            title="Efficiency by Machine",
            hover_data=["part_no", "plan_qty", "actual_qty", "downtime_min"],
            labels={"efficiency": "Efficiency (%)"}
        )
        st.plotly_chart(fig, use_container_width=True)

        # Export
        st.download_button(
            label="\U0001F4BE ดาวน์โหลด Excel",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="efficiency_report.csv",
            mime="text/csv"
        )
