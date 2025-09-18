import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, date, time as dt_time

# ================================
# CONFIG
# ================================
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

# Connect Supabase via Postgres conn_str
conn_str = st.secrets["postgres"]["conn_str"]
engine = create_engine(conn_str)

# ================================
# LOGIN SYSTEM
# ================================
if "user" not in st.session_state:
    st.session_state.user = None

def login():
    with st.form("login_form"):
        emp_code = st.text_input("รหัสพนักงาน")
        password = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("เข้าสู่ระบบ")
        if submitted:
            try:
                with engine.begin() as conn:
                    res = conn.execute(
                        text("SELECT * FROM user_roles WHERE emp_code = :emp AND password = :pw"),
                        {"emp": emp_code, "pw": password}
                    ).fetchone()
                if res:
                    st.session_state.user = dict(res._mapping)
                    st.success(f"ยินดีต้อนรับ {st.session_state.user['emp_name']} ({st.session_state.user['role']})")
                else:
                    st.error("❌ รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง")
            except Exception as e:
                st.error(f"DB Error: {e}")

if not st.session_state.user:
    st.title("🔐 เข้าสู่ระบบ")
    login()
    st.stop()

user = st.session_state.user
st.sidebar.success(f"👤 {user['emp_name']} ({user['role']})")

# ================================
# MENU
# ================================
mode = st.sidebar.radio("เลือกโหมด", ["Production Record", "Report"])

# ================================
# PRODUCTION RECORD
# ================================
if mode == "Production Record":
    st.header("📒 บันทึกการผลิต")

    if "downtime_count" not in st.session_state:
        st.session_state.downtime_count = 1

    # ปุ่มเพิ่ม downtime อยู่นอกฟอร์ม
    if st.button("➕ เพิ่ม Downtime"):
        st.session_state.downtime_count += 1

    with st.form("prod_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันที่", date.today())
        shift = st.selectbox("กะการทำงาน", ["Day", "Night"])

        # โหลด master data โดยกัน error กรณี dept ไม่มีใน table
        try:
            df_machine = pd.read_sql(
                "select * from machine_list where department=:dept",
                engine,
                params={"dept": user.get("department")}
            )
        except:
            df_machine = pd.DataFrame(columns=["machine_name"])

        try:
            df_part = pd.read_sql("select * from part_master", engine)
        except:
            df_part = pd.DataFrame(columns=["part_no"])

        try:
            df_problem = pd.read_sql(
                "select * from problem_master where department=:dept",
                engine,
                params={"dept": user.get("department")}
            )
        except:
            df_problem = pd.DataFrame(columns=["problem"])

        try:
            df_action = pd.read_sql(
                "select * from action_master where department=:dept",
                engine,
                params={"dept": user.get("department")}
            )
        except:
            df_action = pd.DataFrame(columns=["action"])

        try:
            df_downtime = pd.read_sql(
                "select * from downtime_master where department=:dept",
                engine,
                params={"dept": user.get("department")}
            )
        except:
            df_downtime = pd.DataFrame(columns=["sub_category"])

        machine = st.selectbox("🛠️ เครื่องจักร", df_machine["machine_name"].tolist() if not df_machine.empty else [])
        part_no = st.selectbox("รหัสงาน (Part No)", df_part["part_no"].tolist() if not df_part.empty else [])
        woc_number = st.text_input("WOC Number")

        start_time = st.time_input("⏱️ เวลาเริ่ม", value=dt_time(8,0))
        end_time = st.time_input("⏱️ เวลาสิ้นสุด", value=dt_time(17,0))

        ok_qty = st.number_input("✅ OK Qty", 0, step=1)
        ng_qty = st.number_input("❌ NG Qty", 0, step=1)
        untest_qty = st.number_input("❓ Untested Qty", 0, step=1)
        speed = st.number_input("⚡ Machine Speed (pcs/min)", 0, step=1)

        # ========== 4M ==========
        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox("เลือก 4M", ["ไม่มีปัญหา", "Man", "Machine", "Material", "Method"])
        problem = st.selectbox("📌 เลือกปัญหา", [""] + df_problem["problem"].tolist())
        problem_custom = st.text_input("📝 ระบุปัญหาเพิ่มเติม (ถ้ามี)")
        action = st.selectbox("🛠️ เลือก Action", [""] + df_action["action"].tolist())
        action_custom = st.text_input("📝 ระบุ Action เพิ่มเติม (ถ้ามี)")

        # ========== Downtime ==========
        st.subheader("⏱️ รายการ Downtime")
        downtime_entries = []
        for i in range(st.session_state.downtime_count):
            st.markdown(f"### Downtime #{i+1}")
            sub_category = st.selectbox(
                f"📌 เลือก Downtime #{i+1}",
                ["ไม่มี Downtime"] + df_downtime["sub_category"].tolist(),
                key=f"dt_sub_{i}"
            )
            dt_custom = st.text_input(f"📝 ระบุ Downtime เพิ่มเติม #{i+1}", key=f"dt_custom_{i}")
            start_dt = st.time_input(f"⏱️ เริ่ม Downtime #{i+1}", value=dt_time(0,0), key=f"dt_start_{i}")
            end_dt = st.time_input(f"⏱️ สิ้นสุด Downtime #{i+1}", value=dt_time(0,0), key=f"dt_end_{i}")

            if sub_category != "ไม่มี Downtime":
                delta_min = (datetime.combine(date.today(), end_dt) - datetime.combine(date.today(), start_dt)).seconds // 60
            else:
                delta_min = 0

            downtime_entries.append({
                "sub_category": sub_category if sub_category != "ไม่มี Downtime" else dt_custom,
                "downtime_min": delta_min
            })

        # ========== Submit ==========
        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            work_minutes = (datetime.combine(date.today(), end_time) - datetime.combine(date.today(), start_time)).seconds // 60
            problem_final = problem_custom if problem_custom else problem
            action_final = action_custom if action_custom else action

            try:
                with engine.begin() as conn:
                    result = conn.execute(text("""
                        insert into production_record 
                        (log_date, shift, department, machine_name, part_no, woc_number,
                         start_time, end_time, work_minutes, ok_qty, ng_qty, untest_qty, speed,
                         main_4m, problem, action, emp_code, operator)
                        values (:log_date, :shift, :department, :machine, :part_no, :woc_number,
                                :start_time, :end_time, :work_minutes, :ok_qty, :ng_qty, :untest_qty, :speed,
                                :main_4m, :problem, :action, :emp_code, :operator)
                        returning id;
                    """), {
                        "log_date": log_date,
                        "shift": shift,
                        "department": user.get("department"),
                        "machine": machine,
                        "part_no": part_no,
                        "woc_number": woc_number,
                        "start_time": str(start_time),
                        "end_time": str(end_time),
                        "work_minutes": work_minutes,
                        "ok_qty": ok_qty,
                        "ng_qty": ng_qty,
                        "untest_qty": untest_qty,
                        "speed": speed,
                        "main_4m": main_4m,
                        "problem": problem_final,
                        "action": action_final,
                        "emp_code": user["emp_code"],
                        "operator": user["emp_name"],
                    })
                    prod_id = result.fetchone()[0]

                    for d in downtime_entries:
                        if d["sub_category"]:
                            conn.execute(text("""
                                insert into downtime_log
                                (production_id, department, main_category, loss_code, sub_category, downtime_min)
                                values (:pid, :dept, :main_cat, :loss_code, :sub_category, :dt_min)
                            """), {
                                "pid": prod_id,
                                "dept": user.get("department"),
                                "main_cat": "N/A",
                                "loss_code": "N/A",
                                "sub_category": d["sub_category"],
                                "dt_min": d["downtime_min"]
                            })
                st.success("✅ บันทึกข้อมูลสำเร็จ")
            except Exception as e:
                st.error(f"DB Error: {e}")
