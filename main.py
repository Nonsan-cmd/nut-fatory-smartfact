import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date, datetime, time

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

# Connect Supabase
conn_str = st.secrets["postgres"]["conn_str"]
engine = create_engine(conn_str)

# -------------------------------
# LOGIN SYSTEM
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
operator_dept = str(user["department"]).strip() if user["department"] else None

st.sidebar.success(f"👷 {operator} ({operator_role})")

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
df_downtime = load_master("downtime_master")
df_problem = load_master("problem_master")
df_action = load_master("action_master")

# -------------------------------
# NAVIGATION
# -------------------------------
menu = ["📑 Production Record"]
if operator_role in ["Supervisor", "Admin", "Engineer", "Manager"]:
    menu.append("📊 Report")

mode = st.sidebar.radio("เลือกโหมด", menu)

# ============================================================
# PRODUCTION RECORD
# ============================================================
if mode == "📑 Production Record":
    st.title("📑 Production Record")

    if "downtimes" not in st.session_state:
        st.session_state.downtimes = []

    with st.form("record_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันทำงาน", value=date.today())
        shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])

        # ✅ แผนกจาก Login
        st.text_input("🏭 แผนก", operator_dept, disabled=True)

        # ✅ เครื่องจักร filter ตามแผนก
        machine_options = (
            df_machine[df_machine["department"].str.strip() == operator_dept]["machine_name"].unique()
            if not df_machine.empty else []
        )
        machine_name = st.selectbox("⚙️ เครื่องจักร", machine_options)

        # ✅ Part No
        part_no = st.selectbox("🔩 Part No.", df_part["part_no"].unique() if not df_part.empty else [])

        # ✅ WOC Number
        woc_number = st.text_input("📄 หมายเลข WOC")

        # ✅ Start & End Time (เลือกชั่วโมง/นาทีแยก)
        st.markdown("### ⏱️ เวลาเริ่ม–เวลาจบ")
        minutes_options = list(range(0, 60, 5))

        col1, col2, col3, col4 = st.columns(4)
        start_hour = col1.selectbox("Start Hour", list(range(0, 24)), index=7)
        start_minute = col2.selectbox("Start Minute", minutes_options, index=minutes_options.index(45))
        end_hour = col3.selectbox("End Hour", list(range(0, 24)), index=16)
        end_minute = col4.selectbox("End Minute", minutes_options, index=minutes_options.index(45))

        start_time = time(start_hour, start_minute)
        end_time = time(end_hour, end_minute)

        work_minutes = int(
            (datetime.combine(date.today(), end_time) - datetime.combine(date.today(), start_time)).total_seconds() // 60
        )
        if work_minutes < 0:
            work_minutes = None
            st.warning("⚠️ เวลาจบต้องมากกว่าเวลาเริ่ม")

        # ✅ Output Qty
        ok_qty = st.number_input("✔️ จำนวน OK", min_value=0, step=1)
        ng_qty = st.number_input("❌ จำนวน NG", min_value=0, step=1)

        untest_qty = 0
        if operator_dept == "FI":
            untest_qty = st.number_input("🔍 Untest Qty (เฉพาะ FI)", min_value=0, step=1)

        # ✅ Speed (เฉพาะ TP, FI)
        speed = None
        if operator_dept in ["TP", "FI"]:
            speed = st.number_input("⚡ Machine Speed (pcs/min)", min_value=0, step=1)

        # ===============================
        # 4M Problem Section
        # ===============================
        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox("เลือก 4M", ["ไม่มีปัญหา", "Man", "Machine", "Material", "Method"])

        problem_selected, action_selected = None, None
        if main_4m != "ไม่มีปัญหา":
            problems = df_problem[
                (df_problem["department"].str.strip() == operator_dept) &
                (df_problem["main_4m"].str.strip() == main_4m)
            ]["problem"].unique()
            problem_selected = st.selectbox("📌 เลือกปัญหา", list(problems) + ["อื่น ๆ"])
            if problem_selected == "อื่น ๆ":
                problem_selected = st.text_input("📝 ระบุปัญหาเพิ่มเติม")

            actions = df_action["action"].unique() if not df_action.empty else ["Corrective", "Preventive", "Other"]
            action_selected = st.selectbox("🛠️ เลือก Action", list(actions) + ["อื่น ๆ"])
            if action_selected == "อื่น ๆ":
                action_selected = st.text_input("📝 ระบุ Action เพิ่มเติม")

        # ===============================
        # Downtime Section
        # ===============================
        st.subheader("⏱️ รายการ Downtime")
        main_category = st.selectbox("Main Category", df_downtime["main_category"].unique() if not df_downtime.empty else [])
        sub_options = df_downtime[df_downtime["main_category"] == main_category]["sub_category"].unique()
        sub_category = st.selectbox("Sub Category", sub_options)
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
            if work_minutes is None:
                st.error("❌ โปรดตรวจสอบเวลาเริ่ม/เวลาจบ")
            else:
                try:
                    with engine.begin() as conn:
                        # insert production record
                        result = conn.execute(text("""
                            insert into production_record
                            (log_date, shift, department, machine_name, part_no, woc_number,
                            start_time, end_time, work_minutes,
                            ok_qty, ng_qty, untest_qty, speed,
                            main_4m, problem, action, emp_code, operator)
                            values (:log_date, :shift, :department, :machine_name, :part_no, :woc_number,
                            :start_time, :end_time, :work_minutes,
                            :ok_qty, :ng_qty, :untest_qty, :speed,
                            :main_4m, :problem, :action, :emp_code, :operator)
                            returning id
                        """), {
                            "log_date": log_date,
                            "shift": shift,
                            "department": operator_dept,
                            "machine_name": machine_name,
                            "part_no": part_no,
                            "woc_number": woc_number,
                            "start_time": start_time,
                            "end_time": end_time,
                            "work_minutes": work_minutes,
                            "ok_qty": int(ok_qty),
                            "ng_qty": int(ng_qty),
                            "untest_qty": int(untest_qty),
                            "speed": speed,
                            "main_4m": main_4m,
                            "problem": problem_selected,
                            "action": action_selected,
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

                        # insert into summary_log
                        conn.execute(text("""
                            insert into summary_log
                            (log_date, shift, department, machine_name, part_no, woc_number,
                             ok_qty, ng_qty, untest_qty, output_qty, total_downtime,
                             work_minutes, speed, operator)
                            select pr.log_date, pr.shift, pr.department, pr.machine_name, pr.part_no, pr.woc_number,
                                   pr.ok_qty, pr.ng_qty, pr.untest_qty, pr.output_qty,
                                   coalesce(sum(dl.downtime_min), 0) as total_downtime,
                                   pr.work_minutes, pr.speed, pr.operator
                            from production_record pr
                            left join downtime_log dl on pr.id = dl.production_id
                            where pr.id = :pid
                            group by pr.id
                        """), {"pid": prod_id})

                    st.success("✅ บันทึกเรียบร้อยแล้ว")
                    st.session_state.downtimes = []  # reset
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# ============================================================
# REPORT MODE
# ============================================================
elif mode == "📊 Report":
    st.title("📊 Production Report")

    col1, col2 = st.columns(2)
    start_date = col1.date_input("📅 วันที่เริ่มต้น", value=date.today())
    end_date = col2.date_input("📅 วันที่สิ้นสุด", value=date.today())

    dept_filter = st.selectbox("🏭 แผนก", ["All", "FM", "TP", "FI"])
    machines = df_machine["machine_name"].unique() if not df_machine.empty else []
    machine_filter = st.selectbox("⚙️ เครื่องจักร", ["All"] + list(machines))

    query = """
        select * from summary_log
        where log_date between :start and :end
    """
    params = {"start": start_date, "end": end_date}
    df = pd.read_sql(text(query), engine, params=params)

    if dept_filter != "All":
        df = df[df["department"] == dept_filter]
    if machine_filter != "All":
        df = df[df["machine_name"] == machine_filter]

    if df.empty:
        st.warning("ไม่พบข้อมูล")
    else:
        st.subheader("📋 ตารางสรุป")
        summary = df.groupby(["log_date", "department", "machine_name"]).agg({
            "ok_qty": "sum",
            "ng_qty": "sum",
            "untest_qty": "sum",
            "output_qty": "sum",
            "total_downtime": "sum"
        }).reset_index()
        st.dataframe(summary, use_container_width=True)

        csv = summary.to_csv(index=False).encode("utf-8")
        st.download_button("📥 ดาวน์โหลด CSV", data=csv, file_name="production_report.csv", mime="text/csv")

        st.subheader("📈 กราฟ")
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(summary.set_index("log_date")[["ok_qty", "ng_qty"]])
        with col2:
            st.line_chart(summary.set_index("log_date")[["total_downtime"]])
