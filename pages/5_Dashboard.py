import streamlit as st
import pandas as pd
import psycopg2
from datetime import date
import plotly.express as px

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Update downtime_min into production_log ===
def update_downtime_summary():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE production_log pl
                SET downtime_min = sub.total_downtime_min
                FROM (
                    SELECT log_date, shift, machine_id, SUM(duration_min) AS total_downtime_min
                    FROM downtime_log
                    GROUP BY log_date, shift, machine_id
                ) sub
                WHERE pl.log_date = sub.log_date
                  AND pl.shift = sub.shift
                  AND pl.machine_id = sub.machine_id;
            """)
            conn.commit()

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
                , 1) AS efficiency
            FROM production_log pl
            INNER JOIN machine_list ml ON pl.machine_id = ml.id
            INNER JOIN part_master pm ON pl.part_id = pm.id
            WHERE pl.log_date BETWEEN %s AND %s
            GROUP BY ml.department, pm.part_no, pm.std_cycle_time_sec
            ORDER BY ml.department, pm.part_no
        """
        return pd.read_sql(sql, conn, params=(start_date, end_date))

# === UI ===
st.set_page_config(page_title="Dashboard Efficiency Report", layout="wide")
st.title("📊 Dashboard Efficiency Report")

# ⏱️ Date Filters
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", value=date.today())
with col2:
    end_date = st.date_input("📅 End Date", value=date.today())

# ⛏️ Refresh downtime summary
tabs = st.tabs(["🔄 Efficiency Dashboard", "📉 Downtime by Reason"])

with tabs[0]:
    if start_date > end_date:
        st.warning("📛 Start Date ต้องน้อยกว่าหรือเท่ากับ End Date")
    else:
        update_downtime_summary()
        df = load_efficiency_report(start_date, end_date)

        if df.empty:
            st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก")
        else:
            dept_list = df["department"].unique().tolist()
            selected_dept = st.multiselect("เลือกแผนก", dept_list, default=dept_list)
            df_filtered = df[df["department"].isin(selected_dept)]

            st.dataframe(df_filtered, use_container_width=True)

            fig = px.bar(df_filtered, 
                         x="part_no", y="efficiency", 
                         color="department", barmode="group",
                         title="Efficiency by Part",
                         labels={"efficiency": "Efficiency (%)", "part_no": "Part No"})
            st.plotly_chart(fig, use_container_width=True)

            st.download_button(
                label="📥 ดาวน์โหลด Excel",
                data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
                file_name="efficiency_report.csv",
                mime="text/csv"
            )

with tabs[1]:
    with get_connection() as conn:
        sql = """
            SELECT 
                dl.log_date,
                dl.shift,
                ml.department,
                ml.machine_name,
                drm.reason_name,
                SUM(dl.duration_min) AS duration_min
            FROM downtime_log dl
            JOIN machine_list ml ON dl.machine_id = ml.id
            JOIN downtime_reason_master drm ON dl.downtime_reason_id = drm.id
            WHERE dl.log_date BETWEEN %s AND %s
            GROUP BY dl.log_date, dl.shift, ml.department, ml.machine_name, drm.reason_name
            ORDER BY dl.log_date DESC, ml.department
        """
        df_downtime = pd.read_sql(sql, conn, params=(start_date, end_date))

    if not df_downtime.empty:
        st.dataframe(df_downtime, use_container_width=True)

        fig2 = px.bar(df_downtime, 
                     x="machine_name", y="duration_min", 
                     color="reason_name", 
                     title="Downtime by Reason",
                     labels={"duration_min": "Downtime (min)"},
                     hover_data=["department", "log_date", "shift"])
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("ยังไม่มีข้อมูล downtime")
