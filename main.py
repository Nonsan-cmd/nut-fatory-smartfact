import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, time

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
        st.write("🔐 Login เข้าสู่ระบบ")
        emp_code = st.text_input("รหัสพนักงาน")
        pw = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                query = text("select * from user_roles where emp_code=:emp and password=:pw")
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

user = st.session_state.user
operator = user["emp_name"]
emp_code = user["emp_code"]
role = user["role"]
department = user["department"]

st.sidebar.success(f"👷 {operator} ({role})")

# -------------------------------
# LOAD MASTER DATA
# -------------------------------
def load_master(table):
    try:
        return pd.read_sql(f"select * from {table}", engine)
    except:
        return pd.DataFrame()

df_machine = load_master("machine_list")
df_part = load_master("part_master")
df_problem = load_master("problem_master")
df_action = load_master("action_master")
df_downtime = load_master("downtime_master")

# -------------------------------
# MODE
# -------------------------------
mode = st.sidebar.radio("เลือกโหมด", ["Production Record", "Report"])

# -------------------------------
# PRODUCTION RECORD MODE
# -------------------------------
if mode == "Production Record":
    st.title("📑 Production Record")

    # Dynamic downtime list (อยู่นอก form)
    if "downtime_list" not in st.session_state:
        st.session_state.downtime_list = []

    if st.button("➕ เพิ่ม Downtime"):
        st.session_state.downtime_list.append(
            {"main_category": None, "sub_category": None, "downtime_min": 0, "remark": ""}
        )

    with st.form("record_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันทำงาน", value=date.today())
        shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])

        machine_name = st.selectbox(
            "⚙️ เครื่องจักร",
            df_machine[df_machine["department"] == department]["machine_name"].unique()
        )
        part_no = st.selectbox("🔩 Part No.", df_part["part_no"].unique())
        woc_number = st.text_input("WOC Number")

        col1, col2 = st.columns(2)
        start_hour = col1.selectbox("Start Hour", list(range(0, 24)))
        start_min = col2.selectbox("Start Minute", list(range(0, 60, 5)))
        col3, col4 = st.columns(2)
        end_hour = col3.selectbox("End Hour", list(range(0, 24)))
        end_min = col4.selectbox("End Minute", list(range(0, 60, 5)))

        start_time = time(start_hour, start_min)
        end_time = time(end_hour, end_min)
        work_minutes = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)

        ok_qty = st.number_input("✔️ OK Qty", min_value=0, step=1)
        ng_qty = st.number_input("❌ NG Qty", min_value=0, step=1)
        untest_qty = st.number_input("🔍 Untest Qty (เฉพาะ FI)", min_value=0, step=1) if department == "FI" else 0
        speed = st.number_input("⚡ Machine Speed (pcs/min)", min_value=0, step=1)

        # -------------------------------
        # 4M
        # -------------------------------
        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox(
            "เลือก 4M",
            ["ไม่มีปัญหา"] + df_problem[df_problem["department"] == department]["main_4m"].unique().tolist()
        )
        problem, action, problem_remark, action_remark = None, None, "", ""
        if main_4m != "ไม่มีปัญหา":
            problem = st.selectbox(
                "📌 เลือกปัญหา",
                df_problem[(df_problem["department"] == department) & (df_problem["main_4m"] == main_4m)]["problem"].unique().tolist() + ["อื่น ๆ"]
            )
            if problem == "อื่น ๆ":
                problem_remark = st.text_input("📝 ระบุปัญหาเพิ่มเติม")

            action = st.selectbox(
                "🛠️ เลือก Action",
                df_action[df_action["department"] == department]["action"].unique().tolist() + ["อื่น ๆ"]
            )
            if action == "อื่น ๆ":
                action_remark = st.text_input("📝 ระบุ Action เพิ่มเติม")

        # -------------------------------
        # Downtime List
        # -------------------------------
        st.subheader("⏱️ รายการ Downtime")
        dept_downtime = df_downtime[df_downtime["department"] == department]
        for i, dt in enumerate(st.session_state.downtime_list):
            st.markdown(f"### Downtime #{i+1}")
            dt["main_category"] = st.selectbox(
                f"Main Category #{i+1}", ["ไม่มี Downtime"] + dept_downtime["main_category"].unique().tolist(),
                key=f"main{i}"
            )
            if dt["main_category"] != "ไม่มี Downtime":
                dt["sub_category"] = st.selectbox(
                    f"Sub Category #{i+1}",
                    dept_downtime[dept_downtime["main_category"] == dt["main_category"]]["sub_category"].unique(),
                    key=f"sub{i}"
                )
                dt["downtime_min"] = st.number_input(f"Downtime (นาที) #{i+1}", 0, 1000, key=f"min{i}")
                dt["remark"] = st.text_input(f"Remark #{i+1}", key=f"remark{i}")

        # -------------------------------
        # Submit
        # -------------------------------
        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            try:
                with engine.begin() as conn:
                    res = conn.execute(text("""
                        insert into production_record
                        (log_date, shift, department, machine_name, part_no, woc_number,
                         start_time, end_time, work_minutes, ok_qty, ng_qty, untest_qty,
                         speed, main_4m, problem, action, problem_remark, action_remark,
                         emp_code, operator)
                        values
                        (:log_date, :shift, :department, :machine_name, :part_no, :woc_number,
                         :start_time, :end_time, :work_minutes, :ok_qty, :ng_qty, :untest_qty,
                         :speed, :main_4m, :problem, :action, :problem_remark, :action_remark,
                         :emp_code, :operator)
                        returning id
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
                        "problem_remark": problem_remark,
                        "action_remark": action_remark,
                        "emp_code": emp_code,
                        "operator": operator
                    })
                    production_id = res.scalar_one()

                    # insert downtime logs
                    for dt in st.session_state.downtime_list:
                        if dt["main_category"] and dt["main_category"] != "ไม่มี Downtime":
                            conn.execute(text("""
                                insert into downtime_log (production_id, department, main_category, sub_category, downtime_min, downtime_remark)
                                values (:pid, :dept, :main_category, :sub_category, :downtime_min, :remark)
                            """), {
                                "pid": production_id,
                                "dept": department,
                                "main_category": dt["main_category"],
                                "sub_category": dt["sub_category"],
                                "downtime_min": int(dt["downtime_min"]),
                                "remark": dt["remark"]
                            })

                st.success("✅ บันทึกข้อมูลเรียบร้อย")
                st.session_state.downtime_list = []  # reset downtime list
            except Exception as e:
                st.error(f"❌ Error: {e}")

# -------------------------------
# REPORT MODE
# -------------------------------
if mode == "Report":
    if role not in ["Supervisor", "Admin", "Engineer", "Manager"]:
        st.error("❌ คุณไม่มีสิทธิ์เข้าถึง Report")
    else:
        st.title("📊 Production Report")
        start_date = st.date_input("📅 วันที่เริ่ม", value=date.today())
        end_date = st.date_input("📅 วันที่สิ้นสุด", value=date.today())

        try:
            query = text("""
                select * from production_record
                where log_date between :start and :end
                order by log_date desc
            """)
            df = pd.read_sql(query, engine, params={"start": start_date, "end": end_date})
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"❌ Error: {e}")
