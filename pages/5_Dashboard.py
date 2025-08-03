import streamlit as st
import pandas as pd
import psycopg2
from datetime import date, timedelta

# === Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load joined data from production + downtime ===
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
                    pl.plan_qty,
                    pl.actual_qty,
                    pl.defect_qty,
                    COALESCE(dl.duration_min, 0) AS downtime_min,
                    drm.reason_name
                FROM production_log pl
                LEFT JOIN machine_list ml ON pl.machine_id = ml.id
                LEFT JOIN part_master pm ON pl.part_id = pm.id
                LEFT JOIN downtime_log dl ON pl.machine_id = dl.machine_id 
                    AND pl.log_date = dl.log_date AND pl.shift = dl.shift
                LEFT JOIN downtime_reason_master drm ON dl.downtime_reason_id = drm.id
                WHERE pl.log_date BETWEEN %s AND %s
                ORDER BY pl.log_date DESC, ml.machine_name
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))
            return df
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return pd.DataFrame()

# === UI ===
st.title("📊 Dashboard Efficiency Report")

end_date = date.today()
start_date = end_date - timedelta(days=7)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 Start Date", start_date)
with col2:
    end_date = st.date_input("📅 End Date", end_date)

df = load_data(start_date, end_date)

if df.empty:
    st.warning("ไม่พบข้อมูลในช่วงวันที่ที่เลือก หรือยังไม่มีข้อมูล")
else:
    df["Efficiency (%)"] = (df["actual_qty"] / df["plan_qty"]) * 100
    st.success(f"📄 พบทั้งหมด {len(df)} รายการ")
    st.dataframe(df.style.format({"Efficiency (%)": "{:.1f}"}), use_container_width=True)
