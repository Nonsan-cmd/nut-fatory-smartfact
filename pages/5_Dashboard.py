import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Efficiency Report ===
def load_efficiency_report(start_date, end_date):
    with get_connection() as conn:
        sql = """
            SELECT 
                ml.department,
                pm.part_no,
                pm.std_cycle_time_sec,
                SUM(COALESCE(pl.plan_qty, 0)) AS plan_qty,
                SUM(COALESCE(pl.actual_qty, 0)) AS actual_qty,
                SUM(COALESCE(pl.defect_qty, 0)) AS defect_qty,
                SUM(COALESCE(pl.downtime_min, 0)) AS downtime_min,
                ROUND(
                    CASE 
                        WHEN SUM(COALESCE(pl.actual_qty, 0) * COALESCE(pm.std_cycle_time_sec, 0)) 
                             + SUM(COALESCE(pl.downtime_min, 0) * 60) = 0 
                        THEN 0
                        ELSE 
                            (SUM(COALESCE(pl.actual_qty, 0) * COALESCE(pm.std_cycle_time_sec, 0))::NUMERIC 
                            / (SUM(COALESCE(pl.actual_qty, 0) * COALESCE(pm.std_cycle_time_sec, 0)) + SUM(COALESCE(pl.downtime_min, 0) * 60)) * 100)
                    END
                , 1) AS efficiency
            FROM production_log pl
            INNER JOIN machine_list ml ON pl.machine_id = ml.id
            INNER JOIN part_master pm ON pl.part_id = pm.id
            WHERE pl.log_date BETWEEN %s AND %s
            GROUP BY ml.department, pm.part_no, pm.std_cycle_time_sec
            ORDER BY ml.department, pm.part_no
        """
        return pd.read_sql(sql, conn, params=(start_date, end_date))

# === UI Layout ===
st.set_page_config(page_title="Dashboard Efficiency Report", layout="wide")
st.title("📊 Dashboard Efficiency Report")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", value=date.today())
with col2:
    end_date = st.date_input("📅 End Date", value=date.today())

if start_date > end_date:
    st.warning("⚠️ Start Date ต้องน้อยกว่าหรือเท่ากับ End Date")
    st.stop()

df = load_efficiency_report(start_date, end_date)

if df.empty:
    st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
    st.stop()

# === Filter by Department ===
departments = df["department"].unique().tolist()
selected_depts = st.multiselect("เลือกแผนก", departments, default=departments)
filtered_df = df[df["department"].isin(selected_depts)]

# === Show Table ===
st.markdown("### 📋 Efficiency Summary Table")
st.dataframe(filtered_df, use_container_width=True)

# === Chart 1: Efficiency by Part ===
fig1 = px.bar(
    filtered_df,
    x="part_no",
    y="efficiency",
    color="department",
    title="📈 Efficiency (%) by Part No",
    text="efficiency"
)
fig1.update_layout(yaxis_title="Efficiency (%)", xaxis_title="Part No", height=400)
st.plotly_chart(fig1, use_container_width=True)

# === Chart 2: Downtime by Part ===
fig2 = px.bar(
    filtered_df,
    x="part_no",
    y="downtime_min",
    color="department",
    title="🛠️ Downtime (min) by Part No",
    text="downtime_min"
)
fig2.update_layout(yaxis_title="Downtime (min)", xaxis_title="Part No", height=400)
st.plotly_chart(fig2, use_container_width=True)

# === Export Button ===
st.download_button(
    label="📥 ดาวน์โหลด Excel",
    data=filtered_df.to_csv(index=False).encode("utf-8-sig"),
    file_name="efficiency_report.csv",
    mime="text/csv"
)
