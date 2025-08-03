import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta
import plotly.express as px

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Data with Efficiency Calculation ===
@st.cache_data
def load_data(start_date, end_date):
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
                    COALESCE(dl.total_downtime, 0) AS downtime_min,
                    COALESCE(dl.reason_text, '-') AS reason_text
                FROM production_log pl
                JOIN machine_list ml ON pl.machine_id = ml.id
                JOIN part_master pm ON pl.part_id = pm.id
                LEFT JOIN (
                    SELECT 
                        machine_id,
                        log_date,
                        shift,
                        SUM(duration_min) AS total_downtime,
                        STRING_AGG(dr.reason_name || ' (' || dl.duration_min || 'min)', ', ') AS reason_text
                    FROM downtime_log dl
                    JOIN downtime_reason_master dr ON dl.downtime_reason_id = dr.id
                    GROUP BY machine_id, log_date, shift
                ) dl ON pl.machine_id = dl.machine_id AND pl.log_date = dl.log_date AND pl.shift = dl.shift
                WHERE pl.log_date BETWEEN %s AND %s
                ORDER BY pl.log_date DESC, ml.machine_name
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))
            df["Efficiency (%)"] = df.apply(lambda row: 
                round(
                    (row["actual_qty"] * row["std_cycle_time_sec"]) / 
                    ((row["actual_qty"] * row["std_cycle_time_sec"]) + (row["downtime_min"] * 60)) * 100
                    if (row["actual_qty"] * row["std_cycle_time_sec"] + row["downtime_min"] * 60) > 0 else 0, 1
            , axis=1)
            return df
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")
        return pd.DataFrame()

# === UI ===
st.set_page_config(page_title="Efficiency Dashboard", layout="wide")
st.title("📊 Dashboard Efficiency Report")

# --- Date Picker ---
today = date.today()
start_default = today - timedelta(days=7)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", start_default)
with col2:
    end_date = st.date_input("📅 End Date", today)

# --- Load Data ---
df = load_data(start_date, end_date)

if df.empty:
    st.warning("ไม่มีข้อมูลในช่วงวันที่ที่เลือก")
else:
    st.success(f"✅ พบข้อมูลทั้งหมด {len(df)} รายการ")

    # --- Slicer ---
    dept_selected = st.multiselect("🧭 เลือกแผนก", options=sorted(df["department"].unique()), default=sorted(df["department"].unique()))
    df_filtered = df[df["department"].isin(dept_selected)]

    # --- Table ---
    st.dataframe(df_filtered.style.format({"Efficiency (%)": "{:.1f}"}), use_container_width=True)

    # --- Chart ---
    chart_df = df_filtered.groupby(["log_date", "department"]).agg({
        "Efficiency (%)": "mean"
    }).reset_index()

    fig = px.line(chart_df, x="log_date", y="Efficiency (%)", color="department",
                  markers=True, title="📈 Efficiency ตามวัน (เฉลี่ยต่อแผนก)")
    st.plotly_chart(fig, use_container_width=True)

    # --- Export Button ---
    st.download_button(
        label="📥 ดาวน์โหลด Excel",
        data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="efficiency_dashboard.csv",
        mime="text/csv"
    )
