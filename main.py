import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, time, datetime

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

# Connect Supabase
conn_str = st.secrets["postgres"]["conn_str"]
engine = create_engine(conn_str)

# -------------------------------
# LOGIN
# -------------------------------
if "user" not in st.session_state:
    with st.form("login"):
        st.subheader("🔐 Login เข้าสู่ระบบ")
        emp_code = st.text_input("รหัสพนักงาน")
        pw = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            query = text("SELECT * FROM user_roles WHERE emp_code=:emp AND password=:pw")
            with engine.begin() as conn:
                user = conn.execute(query, {"emp": emp_code, "pw": pw}).fetchone()
            if user:
                st.session_state.user = dict(user._mapping)
                st.success(f"ยินดีต้อนรับ {user.emp_name} ({user.role})")
            else:
                st.error("❌ รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง")
    st.stop()

user = st.session_state.user
st.sidebar.success(f"👷 {user['emp_name']} ({user['role']})")

# -------------------------------
# LOAD MASTER DATA
# -------------------------------
def load_table(table):
    return pd.read_sql(f"SELECT * FROM {table}", engine)

df_dept = load_table("department_master")
df_machine = load_table("machine_list")
df_part = load_table("part_master")
df_problem = load_table("problem_master")
df_action = load_table("action_master")
df_downtime = load_table("downtime_master")

# -------------------------------
# PAGE SELECT
# -------------------------------
mode = st.sidebar.radio("เลือกโหมด", ["Production Record", "Report"])

# -------------------------------
# PRODUCTION RECORD
# -------------------------------
if mode == "Production Record":
    st.title("📑 Production Record")

    with st.form("record_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันทำงาน", value=date.today())
        shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])
        department = user["department"]

        machine_name = st.selectbox(
            "⚙️ เครื่องจักร",
            df_machine[df_machine["department"] == department]["machine_name"].tolist()
        )
        part_no = st.selectbox("🔩 Part No.", df_part["part_no"].tolist())
        woc_number = st.text_input("WOC Number")

        col1, col2 = st.columns(2)
        start_hour = col1.selectbox("Start Hour", list(range(0, 24)), index=7)
        start_minute = col2.selectbox("Start Minute", list(range(0, 60, 5)), index=0)

        col3, col4 = st.columns(2)
        end_hour = col3.selectbox("End Hour", list(range(0, 24)), index=16)
        end_minute = col4.selectbox("End Minute", list(range(0, 60, 5)), index=0)

        start_time = time(start_hour, start_minute)
        end_time = time(end_hour, end_minute)
        work_minutes = ((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute))

        ok_qty = st.number_input("✔️ จำนวน OK", min_value=0, step=1)
        ng_qty = st.number_input("❌ จำนวน NG", min_value=0, step=1)
        untest_qty = 0
        if department == "FI":
            untest_qty = st.number_input("🔍 Untest Qty", min_value=0, step=1)

        speed = 0
        if department in ["TP", "FI"]:
            speed = st.number_input("⚡ Machine Speed (pcs/min)", min_value=0, step=1)

        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox("เลือก 4M", ["ไม่มีปัญหา", "Man", "Machine", "Material", "Method"])
        problem = None
        action = None
        if main_4m != "ไม่มีปัญหา":
            problems = df_problem[(df_problem["department"] == department) & (df_problem["main_4m"] == main_4m)]
            problem = st.selectbox("📌 Problem", problems["problem"].tolist() if not problems.empty else ["อื่นๆ"])
            actions = df_action[df_action["department"] == department]
            action = st.selectbox("🛠 Action", actions["action"].tolist() if not actions.empty else ["อื่นๆ"])

        st.subheader("⏱️ รายการ Downtime")
        if "downtime_list" not in st.session_state:
            st.session_state.downtime_list = []

        main_category = st.selectbox(
            "Main Category",
            df_downtime[df_downtime["department"] == department]["main_category"].unique()
        )
        sub_df = df_downtime[(df_downtime["department"] == department) & (df_downtime["main_category"] == main_category)]
        sub_category = st.selectbox("Sub Category", sub_df["sub_category"].tolist())
        downtime_min = st.number_input("Downtime (นาที)", min_value=0, step=1)

        if st.form_submit_button("➕ เพิ่ม Downtime"):
            loss_code = sub_df[sub_df["sub_category"] == sub_category]["loss_code"].values[0]
            st.session_state.downtime_list.append({
                "main_category": main_category,
                "loss_code": loss_code,
                "sub_category": sub_category,
                "downtime_min": downtime_min
            })
            st.success("เพิ่ม Downtime แล้ว")

        st.table(pd.DataFrame(st.session_state.downtime_list))

        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            with engine.begin() as conn:
                # insert production record
                res = conn.execute(text("""
                    INSERT INTO production_record
                    (log_date, shift, department, machine_name, part_no, woc_number,
                     start_time, end_time, work_minutes,
                     ok_qty, ng_qty, untest_qty, speed,
                     main_4m, problem, action,
                     emp_code, operator)
                    VALUES (:log_date, :shift, :department, :machine_name, :part_no, :woc_number,
                            :start_time, :end_time, :work_minutes,
                            :ok_qty, :ng_qty, :untest_qty, :speed,
                            :main_4m, :problem, :action,
                            :emp_code, :operator)
                    RETURNING id
                """), {
                    "log_date": log_date,
                    "shift": shift,
                    "department": department,
                    "machine_name": machine_name,
                    "part_no": part_no,
                    "woc_number": woc_number,
                    "start_time": start_time,
                    "end_time": end_time,
                    "work_minutes": work_minutes,
                    "ok_qty": int(ok_qty),
                    "ng_qty": int(ng_qty),
                    "untest_qty": int(untest_qty),
                    "speed": int(speed),
                    "main_4m": main_4m,
                    "problem": problem,
                    "action": action,
                    "emp_code": user["emp_code"],
                    "operator": user["emp_name"]
                })
                prod_id = res.fetchone()[0]

                # insert downtime log
                for d in st.session_state.downtime_list:
                    conn.execute(text("""
                        INSERT INTO downtime_log
                        (production_id, department, main_category, loss_code, sub_category, downtime_min)
                        VALUES (:production_id, :department, :main_category, :loss_code, :sub_category, :downtime_min)
                    """), {**d, "production_id": prod_id, "department": department})
            st.session_state.downtime_list = []
            st.success("✅ บันทึกเรียบร้อยแล้ว")

# -------------------------------
# REPORT MODE
# -------------------------------
elif mode == "Report":
    if user["role"] not in ["Supervisor", "Admin", "Engineer", "Manager"]:
        st.warning("❌ คุณไม่มีสิทธิ์เข้าถึง Report")
        st.stop()

    st.title("📊 Production Report")

    start_date = st.date_input("📅 วันที่เริ่ม")
    end_date = st.date_input("📅 วันที่สิ้นสุด")

    query = text("""
        SELECT * FROM production_record
        WHERE log_date BETWEEN :start AND :end
        ORDER BY log_date DESC, id DESC
    """)
    df = pd.read_sql(query, engine, params={"start": start_date, "end": end_date})

    st.dataframe(df, use_container_width=True)
