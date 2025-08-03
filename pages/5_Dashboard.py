import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta
import plotly.express as px

# === Connect to Supabase ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load data with joined downtime ===
@st.cache_data
def load_dashboard_data(start_date, end_date):
    try:
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
                    COALESCE(sub.total_downtime, 0) AS downtime_min,
                    COALESCE(sub.reason_text, '-') AS reason_detail
                FROM production_log pl
                JOIN machine_list ml ON pl.machine_id = ml.id
                JOIN part_master pm ON pl.part_id = pm.id
                LEFT JOIN (
                    SELECT 
                        machine_id, log_date, shift,
                        SUM(duration_min) AS total_downtime,
                        STRING_AGG(dr.reason_name || ' (' || dl.duration_min || 'min)', ', ') AS reason_text
                    FROM downtime_log dl
                    JOIN downtime_reason_master dr ON dl.downtime_reason_id = dr.id
                    GROUP BY machine_id, log_date, shift
                ) sub
                ON pl.machine_id = sub.machine_id AND pl.log_date = sub.log_date AND pl.shift = sub.shift
                WHERE pl.log_date BETWEEN %s AND %s
                ORDER BY pl.log_date DESC, ml.machine_name
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))

            df["Efficiency (%)"] = df.apply(lambda row: 
                round((row["actual_qty"] * row["std_cycle_time_sec"]) / 
                      ((row["actual_qty"] * row["std_cycle_time_sec"]) + (row["downtime_min"] * 60)) * 100
                      if (row["actual_qty"] * row["std_cycle_time_sec"] + row["downtime_min"] * 60) > 0 else 0, 1), axis=1)
            return df
    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        return pd.DataFrame()

# === UI ===
st.set_page_config(page_title="Dashboard Efficiency", layout="wide")
st.title("📊 Dashboard Efficiency Report")

# === Date Selection ===
today = date.today()
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", today - timedelta(days=7))
with col2:
    end_date = st.date_input("📅 End Date", today)

# === Load and Display ===
df = load_dashboard_data(start_date, end_date)

if df.empty:
    st.warning("ไม่มีข้อมูลในช่วงวันที่ที่เลือก")
else:
    st.success(f"✅ พบข้อมูลทั้งหมด {len(df)} รายการ")

    # 🔍 Slicer: Department
    departments = sorted(df["department"].dropna().unique())
    selected_dept = st.multiselect("🏭 เลือกแผนก", departments, default=departments)
    filtered_df = df[df["department"].isin(selected_dept)]

    # 📋 Table
    st.dataframe(filtered_df.style.format({"Efficiency (%)": "{:.1f}"}), use_container_width=True)

    # 📈 Chart
    chart_df = filtered_df.groupby(["log_date", "department"]).agg({
        "Efficiency (%)": "mean"
    }).reset_index()

    fig = px.line(chart_df, x="log_date", y="Efficiency (%)", color="department", markers=True,
                  title="📈 Efficiency ตามวัน (เฉลี่ยรายแผนก)")
    st.plotly_chart(fig, use_container_width=True)

    # 📥 Export
    st.download_button(
        label="📥 ดาวน์โหลด Excel",
        data=filtered_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="dashboard_efficiency.csv",
        mime="text/csv"
    )
