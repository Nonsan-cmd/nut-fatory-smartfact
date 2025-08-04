import streamlit as st
import pandas as pd
import psycopg2
import io
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === Load Data ===
@st.cache_data(ttl=600)
def load_data(start_date, end_date):
    with get_connection() as conn:
        query = """
        SELECT p.log_date, p.shift, m.machine_name, m.department,
               pt.part_no, p.plan_qty, p.actual_qty, p.defect_qty,
               COALESCE(SUM(d.duration_min), 0) AS total_downtime_min
        FROM production_log p
        JOIN machine_list m ON p.machine_id = m.id
        JOIN part_master pt ON p.part_id = pt.id
        LEFT JOIN downtime_log d ON p.machine_id = d.machine_id AND p.log_date = d.log_date AND p.shift = d.shift
        WHERE p.log_date BETWEEN %s AND %s
        GROUP BY p.log_date, p.shift, m.machine_name, m.department, pt.part_no, p.plan_qty, p.actual_qty, p.defect_qty
        ORDER BY p.log_date DESC
        """
        return pd.read_sql(query, conn, params=(start_date, end_date))

# === Load Downtime Detail ===
@st.cache_data(ttl=600)
def load_downtime_detail(start_date, end_date):
    with get_connection() as conn:
        query = """
        SELECT d.log_date, d.shift, m.machine_name, r.reason_name, d.duration_min
        FROM downtime_log d
        JOIN machine_list m ON d.machine_id = m.id
        JOIN downtime_reason_master r ON d.downtime_reason_id = r.id
        WHERE d.log_date BETWEEN %s AND %s
        ORDER BY d.log_date DESC
        """
        return pd.read_sql(query, conn, params=(start_date, end_date))

# === Layout ===
st.set_page_config(page_title="Dashboard Efficiency", layout="wide")
st.title("📊 Dashboard ประสิทธิภาพการผลิต (Efficiency)")

# Filter Section
st.sidebar.header("🔎 ตัวกรองข้อมูล")
today = datetime.today().date()
start_date = st.sidebar.date_input("📅 วันที่เริ่มต้น", today - timedelta(days=7))
end_date = st.sidebar.date_input("📅 วันที่สิ้นสุด", today)

# Load and filter data
df = load_data(start_date, end_date)
df_detail = load_downtime_detail(start_date, end_date)

all_depts = sorted(df["department"].dropna().unique())
selected_dept = st.sidebar.selectbox("🏭 เลือกแผนก", ["ทั้งหมด"] + all_depts)
if selected_dept != "ทั้งหมด":
    df = df[df["department"] == selected_dept]
    df_detail = df_detail[df_detail["machine_name"].isin(df["machine_name"].unique())]

all_machines = sorted(df["machine_name"].dropna().unique())
selected_machine = st.sidebar.selectbox("⚙️ เลือกเครื่องจักร", ["ทั้งหมด"] + all_machines)
if selected_machine != "ทั้งหมด":
    df = df[df["machine_name"] == selected_machine]
    df_detail = df_detail[df_detail["machine_name"] == selected_machine]

shift_option = st.sidebar.selectbox("🕘 เลือกกะ", ["ทั้งหมด", "Day", "Night"])
if shift_option != "ทั้งหมด":
    df = df[df["shift"] == shift_option]
    df_detail = df_detail[df_detail["shift"] == shift_option]

# === Summary Table ===
st.subheader("📋 สรุปข้อมูลการผลิต")
df["efficiency"] = (df["actual_qty"] / df["plan_qty"].replace(0, 1)) * 100
st.dataframe(df[["log_date", "shift", "department", "machine_name", "part_no", "plan_qty", "actual_qty", "defect_qty", "total_downtime_min", "efficiency"]])

# === Chart: Efficiency By Machine ===
st.subheader("📊 กราฟเปรียบเทียบ Actual (แท่ง) vs Plan (เส้น) By Machine")
df_grouped = df.groupby(["machine_name", "shift"], as_index=False).agg({
    "plan_qty": "sum",
    "actual_qty": "sum"
})

pivot_df = df_grouped.pivot(index="machine_name", columns="shift", values=["plan_qty", "actual_qty"]).fillna(0)
pivot_df.columns = ['plan_day', 'plan_night', 'actual_day', 'actual_night']
pivot_df["plan_total"] = pivot_df["plan_day"] + pivot_df["plan_night"]
pivot_df["actual_total"] = pivot_df["actual_day"] + pivot_df["actual_night"]
pivot_df = pivot_df.reset_index()

fig = go.Figure()
fig.add_trace(go.Bar(
    x=pivot_df["machine_name"],
    y=pivot_df["actual_total"],
    name="Actual",
    marker_color="blue"
))
fig.add_trace(go.Scatter(
    x=pivot_df["machine_name"],
    y=pivot_df["plan_total"],
    name="Plan",
    mode="lines+markers",
    line=dict(color="orange", width=4),
    marker=dict(size=10)
))
fig.update_layout(
    barmode="group",
    xaxis_title="Machine",
    yaxis_title="Qty",
    title="Actual (Bar) vs Plan (Line) By Machine",
    legend=dict(orientation="h")
)
st.plotly_chart(fig, use_container_width=True)

# === Chart: Downtime ===
st.subheader("⏱ กราฟ Downtime แยกตามสาเหตุ")
df_detail_grouped = df_detail.groupby(["log_date", "reason_name"], as_index=False)["duration_min"].sum()
fig2 = px.bar(df_detail_grouped, x="log_date", y="duration_min", color="reason_name", barmode="stack")
fig2.update_layout(title="📌 Downtime Summary by Reason")
st.plotly_chart(fig2, use_container_width=True)

# === Download Section ===
st.subheader("⬇️ ดาวน์โหลดข้อมูลทั้งหมด")
st.markdown("ดาวน์โหลดไฟล์ Excel ที่รวมทั้งข้อมูลการผลิตและ Downtime อย่างมืออาชีพ")
col1, col2 = st.columns([1, 4])
with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Summary", index=False)
        df_detail.to_excel(writer, sheet_name="Downtime Detail", index=False)
    st.download_button(
        label="📥 Export Dashboard to Excel",
        data=buffer.getvalue(),
        file_name=f"dashboard_efficiency_{datetime.now().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="ดาวน์โหลดข้อมูลทั้งหมดในรูปแบบ Excel พร้อม Pivot"
    )
