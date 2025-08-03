import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta
import plotly.express as px

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Data ===
@st.cache_data
def load_data(start_date, end_date):
    with get_connection() as conn:
        query = """
            SELECT 
                pl.log_date,
                pl.shift,
                ml.machine_name,
                ml.department,
                pm.part_no,
                pm.std_cycle_time_sec,
                pl.plan_qty,
                pl.actual_qty,
                pl.defect_qty,
                pl.downtime_min,
                ROUND(
                    CASE 
                        WHEN (pl.actual_qty * pm.std_cycle_time_sec) + (COALESCE(pl.downtime_min, 0) * 60) = 0 THEN 0
                        ELSE 
                            ((pl.actual_qty * pm.std_cycle_time_sec)::NUMERIC / 
                            ((pl.actual_qty * pm.std_cycle_time_sec) + (COALESCE(pl.downtime_min, 0) * 60)) * 100)
                    END, 1
                ) AS efficiency_percent
            FROM production_log pl
            JOIN machine_list ml ON pl.machine_id = ml.id
            JOIN part_master pm ON pl.part_id = pm.id
            WHERE pl.log_date BETWEEN %s AND %s
            ORDER BY pl.log_date DESC, ml.machine_name
        """
        return pd.read_sql(query, conn, params=(start_date, end_date))

# === UI ===
st.set_page_config(page_title="Efficiency Dashboard", layout="wide")
st.title("\U0001F4CA Dashboard Efficiency Report")

today = date.today()
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("\U0001F4C5 Start Date", today - timedelta(days=7))
with col2:
    end_date = st.date_input("\U0001F4C5 End Date", today)

# === Load Data ===
df = load_data(start_date, end_date)

if df.empty:
    st.warning("ไม่มีข้อมูลในช่วงวันที่ที่เลือก หรือยังไม่มีการบันทึกข้อมูลการผลิต")
else:
    st.success(f"\u2705 พบทั้งหมด {len(df)} รายการ")

    # Slicer by department
    dept_options = df["department"].unique().tolist()
    selected_depts = st.multiselect("เลือกแผนก", dept_options, default=dept_options)
    df_filtered = df[df["department"].isin(selected_depts)]

    # Table
    st.dataframe(df_filtered.style.format({"efficiency_percent": "{:.1f}"}), use_container_width=True)

    # Chart
    chart_df = df_filtered.groupby(["log_date", "department"]).agg({"efficiency_percent": "mean"}).reset_index()
    fig = px.line(chart_df, x="log_date", y="efficiency_percent", color="department", markers=True,
                  title="\U0001F4C8 Efficiency รายวันเฉลี่ยแยกตามแผนก")
    st.plotly_chart(fig, use_container_width=True)

    # Export
    st.download_button(
        label="\U0001F4C2 ดาวน์โหลด Excel",
        data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="efficiency_dashboard.csv",
        mime="text/csv"
    )
