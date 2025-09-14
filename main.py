import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Production Record", page_icon="🏭", layout="wide")

# Connect Supabase
conn_str = st.secrets["postgres"]["conn_str"]
engine = create_engine(conn_str)

# -------------------------------
# Login System
# -------------------------------
if "user" not in st.session_state:
    with st.form("login"):
        st.write("🔐 Login เข้าสู่ระบบ")
        emp_code = st.text_input("รหัสพนักงาน")
        pw = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                query = text("select * from user_roles where emp_code = :emp and password = :pw")
                with engine.begin() as conn:
                    user = conn.execute(query, {"emp": emp_code, "pw": pw}).fetchone()
                if user:
                    st.session_state.user = dict(user._mapping)
                    st.success(f"ยินดีต้อนรับ {user.emp_name} ({user.role})")
                else:
                    st.error("❌ รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง")
            except Exception as e:
                st.error(f"❌ Error: {e}")
    st.stop()

# ข้อมูลผู้ใช้
user = st.session_state.user
operator = user["emp_name"]
operator_code = user["emp_code"]
operator_role = user["role"]
operator_dept = user["department"]

st.sidebar.success(f"👷 {operator} ({operator_role})")

# -------------------------------
# โหลด Master Data
# -------------------------------
def load_master(table):
    try:
        return pd.read_sql(f"select * from {table}", engine)
    except:
        return pd.DataFrame()

df_dept = load_master("department_master")
df_machine = load_master("machine_list")
df_part = load_master("part_master")
df_downtime = load_master("downtime_master")
df_problem = load_master("problem_master")

# -------------------------------
# UI Form
# -------------------------------
st.title("📑 Production Record (All-in-one)")

with st.form("record_form", clear_on_submit=True):
    log_date = st.date_input("📅 วันทำงาน", value=date.today())
    shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])

    department = st.selectbox("🏭 แผนก", df_dept["department_name"].unique() if not df_dept.empty else ["FM","TP","FI"])
    machine_name = st.selectbox("⚙️ เครื่องจักร", df_machine[df_machine["department"]==department]["machine_name"].unique() if not df_machine.empty else [])
    part_no = st.selectbox("🔩 Part No.", df_part["part_no"].unique() if not df_part.empty else [])

    ok_qty = st.number_input("✔️ จำนวน OK", min_value=0, step=1)
    ng_qty = st.number_input("❌ จำนวน NG", min_value=0, step=1)

    untest_qty = 0
    if department == "FI":
        untest_qty = st.number_input("🔍 Untest Qty (เฉพาะ FI)", min_value=0, step=1)

    main_category = st.selectbox("⏱️ Downtime Main Category", df_downtime["main_category"].unique() if not df_downtime.empty else [])
    sub_category = st.selectbox("📌 Downtime Sub Category", df_downtime[df_downtime["main_category"]==main_category]["sub_category"].unique() if not df_downtime.empty else [])
    downtime_min = st.number_input("⏱️ Downtime (นาที)", min_value=0, step=1)

    problem_4m = st.selectbox("⚠️ สาเหตุปัญหา (4M)", df_problem["problem"].unique() if not df_problem.empty else ["Man","Machine","Material","Method","Other"])
    problem_remark = ""
    if problem_4m == "Other":
        problem_remark = st.text_area("📝 ระบุปัญหาเพิ่มเติม")

    submitted = st.form_submit_button("✅ บันทึกข้อมูล")
    if submitted:
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    insert into production_record 
                    (log_date, shift, department, machine_name, part_no, ok_qty, ng_qty, untest_qty,
                    main_category, sub_category, downtime_min, problem_4m, problem_remark,
                    emp_code, operator)
                    values (:log_date, :shift, :department, :machine_name, :part_no, :ok_qty, :ng_qty, :untest_qty,
                    :main_category, :sub_category, :downtime_min, :problem_4m, :problem_remark,
                    :emp_code, :operator)
                """), {
                    "log_date": log_date,
                    "shift": shift,
                    "department": department,
                    "machine_name": machine_name,
                    "part_no": part_no,
                    "ok_qty": int(ok_qty),
                    "ng_qty": int(ng_qty),
                    "untest_qty": int(untest_qty),
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "downtime_min": int(downtime_min),
                    "problem_4m": problem_4m,
                    "problem_remark": problem_remark,
                    "emp_code": operator_code,
                    "operator": operator
                })
            st.success("✅ บันทึกเรียบร้อยแล้ว")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# -------------------------------
# Show latest record
# -------------------------------
st.subheader("📋 ข้อมูลล่าสุด")
try:
    df = pd.read_sql("select * from production_record order by created_at desc limit 10", engine)
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.warning(f"ไม่สามารถโหลดข้อมูล: {e}")
