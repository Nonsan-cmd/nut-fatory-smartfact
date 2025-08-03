import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import plotly.express as px

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
            GROUP BY ml.department, pm.part_no
            ORDER BY ml.department, pm.part_no
        """
        return pd.read_sql(sql, conn, params=(start_date, end_date))

# === UI ===
st.set_page_config(page_title="Dashboard Efficiency Report", layout="wide")
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
        # === Filter by Department
        departments = df["department"].unique().tolist()
        selected_depts = st.multiselect("🧭 เลือกแผนก", departments, default=departments)

        df_filtered = df[df["department"].isin(selected_depts)]

        # === Show Summary Table
        st.subheader("📋 รายงาน Efficiency")
        st.dataframe(df_filtered, use_container_width=True)

        # === Chart: Efficiency by Part
        st.subheader("📈 กราฟเปรียบเทียบ Efficiency ราย Part No.")
        fig = px.bar(
            df_filtered,
            x="part_no",
            y="efficiency",
            color="department",
            title="Efficiency (%) by Part No",
            labels={"efficiency": "Efficiency (%)", "part_no": "Part No"},
            text_auto=".1f"
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # === Export Button
        st.download_button(
            label="📥 ดาวน์โหลด Excel",
            data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name="efficiency_report_filtered.csv",
            mime="text/csv"
        )
