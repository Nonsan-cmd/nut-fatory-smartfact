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
# Load Master Data
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
st.title("📑 Production Record (with Multiple Downtime)")

if "downtimes" not in st.session_state:
    st.session_state.downtimes = []

with st.form("record_form", clear_on_submit=True):
    log_date = st.date_input("📅 วันทำงาน", value=date.today())
    shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])

    # ✅ Department
    dept_selected = st.selectbox(
        "🏭 แผนก",
        df_dept["department_name"].unique() if not df_dept.empty else ["FM", "TP", "FI"]
    )
    dept_selected = str(dept_selected).strip()

    # ✅ Machine ตาม Department
    machine_options = (
        df_machine[df_machine["department"].str.strip() == dept_selected]["machine_name"].unique()
        if not df_machine.empty else []
    )
    machine_name = st.selectbox("⚙️ เครื่องจักร", machine_options)

    # ✅ Part No
    part_no = st.selectbox("🔩 Part No.", df_part["part_no"].unique() if not df_part.empty else [])

    # ✅ Output Qty
    ok_qty = st.number_input("✔️ จำนวน OK", min_value=0, step=1)
    ng_qty = st.number_input("❌ จำนวน NG", min_value=0, step=1)

    untest_qty = 0
    if dept_selected == "FI":
        untest_qty = st.number_input("🔍 Untest Qty (เฉพาะ FI)", min_value=0, step=1)

    # ✅ Problem 4M
    problem_4m = st.selectbox("⚠️ สาเหตุปัญหา (4M)", df_problem["problem"].unique() if not df_problem.empty else ["Man","Machine","Material","Method","Other"])
    problem_remark = ""
    if problem_4m == "Other":
        problem_remark = st.text_area("📝 ระบุปัญหาเพิ่มเติม")

    # ===============================
    # Downtime Section (หลายรายการ)
    # ===============================
    st.subheader("⏱️ รายการ Downtime")

    main_category = st.selectbox("Main Category", df_downtime["main_category"].unique() if not df_downtime.empty else [])
    sub_category = st.selectbox("Sub Category", df_downtime[df_downtime["main_category"]==main_category]["sub_category"].unique() if not df_downtime.empty else [])
    minutes = st.number_input("Downtime (นาที)", min_value=0, step=1)

    if st.form_submit_button("➕ เพิ่ม Downtime"):
        st.session_state.downtimes.append({
            "main": main_category,
            "sub": sub_category,
            "minutes": minutes
        })

    if st.session_state.downtimes:
        st.table(st.session_state.downtimes)

    # ===============================
    # Submit All
    # ===============================
    submitted = st.form_submit_button("✅ บันทึกข้อมูล")
    if submitted:
        try:
            with engine.begin() as conn:
                # insert production record
                result = conn.execute(text("""
                    insert into production_record
                    (log_date, shift, department, machine_name, part_no, ok_qty, ng_qty, untest_qty,
                    problem_4m, problem_remark, emp_code, operator)
                    values (:log_date, :shift, :department, :machine_name, :part_no, :ok_qty, :ng_qty, :untest_qty,
                    :problem_4m, :problem_remark, :emp_code, :operator)
                    returning id
                """), {
                    "log_date": log_date,
                    "shift": shift,
                    "department": dept_selected,
                    "machine_name": machine_name,
                    "part_no": part_no,
                    "ok_qty": int(ok_qty),
                    "ng_qty": int(ng_qty),
                    "untest_qty": int(untest_qty),
                    "problem_4m": problem_4m,
                    "problem_remark": problem_remark,
                    "emp_code": operator_code,
                    "operator": operator
                })
                prod_id = result.scalar_one()

                # insert downtime logs
                for dt in st.session_state.downtimes:
                    conn.execute(text("""
                        insert into downtime_log (production_id, main_category, loss_code, sub_category, downtime_min)
                        values (:pid, :main, 
                               (select loss_code from downtime_master where sub_category=:sub limit 1), 
                               :sub, :minutes)
                    """), {
                        "pid": prod_id,
                        "main": dt["main"],
                        "sub": dt["sub"],
                        "minutes": int(dt["minutes"])
                    })

            st.success("✅ บันทึกเรียบร้อยแล้ว")
            st.session_state.downtimes = []  # reset หลังบันทึก
        except Exception as e:
            st.error(f"❌ Error: {e}")

# -------------------------------
# Show latest record
# -------------------------------
st.subheader("📋 ข้อมูลล่าสุด")
try:
    df = pd.read_sql("""
        select pr.id, pr.log_date, pr.shift, pr.department, pr.machine_name, pr.part_no,
               pr.ok_qty, pr.ng_qty, pr.untest_qty, pr.output_qty, pr.operator,
               dt.main_category, dt.sub_category, dt.downtime_min
        from production_record pr
        left join downtime_log dt on pr.id = dt.production_id
        order by pr.created_at desc
        limit 20
    """, engine)
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.warning(f"ไม่สามารถโหลดข้อมูล: {e}")
