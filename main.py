import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date, datetime

# ================================
# CONFIG
# ================================
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

DB_CONN = st.secrets.get("postgres", {}).get("conn_str", "")
if not DB_CONN:
    st.error("❌ Missing Supabase connection string. Please set in secrets.toml")
    st.stop()

engine = create_engine(DB_CONN)

# ================================
# LOGIN SYSTEM
# ================================
if "user" not in st.session_state:
    with st.form("login"):
        st.subheader("🔐 เข้าสู่ระบบ")
        emp_code = st.text_input("รหัสพนักงาน")
        pw = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            query = text("SELECT * FROM user_roles WHERE emp_code=:emp AND password=:pw")
            with engine.begin() as conn:
                user = conn.execute(query, {"emp": emp_code, "pw": pw}).fetchone()
            if user:
                st.session_state.user = dict(user._mapping)
                st.success(f"👋 ยินดีต้อนรับ {user.emp_name} ({user.role})")
                st.rerun()
            else:
                st.error("❌ รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง")
    st.stop()

user = st.session_state.user
operator = user["emp_name"]
operator_code = user["emp_code"]
operator_role = user["role"]
operator_dept = user["department"]

st.sidebar.success(f"👷 {operator} ({operator_role})")
mode = st.sidebar.radio("เลือกโหมด", ["Production Record", "Report"])

# ================================
# LOAD MASTER DATA
# ================================
def load_master(table):
    try:
        return pd.read_sql(f"SELECT * FROM {table}", engine)
    except Exception:
        return pd.DataFrame()

df_machine = load_master("machine_list")
df_part = load_master("part_master")
df_problem = load_master("problem_master")
df_action = load_master("action_master")
df_downtime = load_master("downtime_master")

# ================================
# MODE : PRODUCTION RECORD
# ================================
if mode == "Production Record":
    st.title("📑 Production Record")

    with st.form("record_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันทำงาน", value=date.today())
        shift = st.selectbox("🕒 กะ", ["เช้า", "โอทีเช้า", "ดึก", "โอทีกะดึก"])

        department = operator_dept
        st.text_input("🏭 แผนก", value=department, disabled=True)

        machine_name = st.selectbox("⚙️ เครื่องจักร",
            df_machine[df_machine["department"] == department]["machine_name"].unique()
        )
        part_no = st.selectbox("🔩 Part No.", df_part["part_no"].unique())

        woc_number = st.text_input("📄 WOC Number")

        # เวลาเริ่ม-จบ
        col1, col2 = st.columns(2)
        with col1:
            start_hour = st.selectbox("Start Hour", list(range(0, 24)))
            start_minute = st.selectbox("Start Minute", list(range(0, 60, 5)))
        with col2:
            end_hour = st.selectbox("End Hour", list(range(0, 24)))
            end_minute = st.selectbox("End Minute", list(range(0, 60, 5)))

        start_time = datetime.strptime(f"{start_hour}:{start_minute}", "%H:%M").time()
        end_time = datetime.strptime(f"{end_hour}:{end_minute}", "%H:%M").time()

        work_minutes = ((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute))
        if work_minutes < 0:
            work_minutes += 24 * 60

        ok_qty = st.number_input("✔️ จำนวน OK", min_value=0, step=1)
        ng_qty = st.number_input("❌ จำนวน NG", min_value=0, step=1)
        untest_qty = st.number_input("🔍 Untest Qty", min_value=0, step=1) if department == "FI" else 0
        speed = st.number_input("⚡ Machine Speed (pcs/min)", min_value=0, step=1) if department in ["TP","FI"] else 0

        # ===== 4M Section =====
        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox("เลือก 4M", ["ไม่มีปัญหา","Man","Machine","Material","Method"])
        problem = st.selectbox("📌 เลือกปัญหา",
            ["ไม่มีปัญหา"] + df_problem[df_problem["department"] == department]["problem"].unique().tolist()
        )
        problem_remark = st.text_area("📝 ระบุปัญหาเพิ่มเติม", placeholder="ใส่ถ้ามี")
        action = st.selectbox("🛠️ เลือก Action",
            ["ไม่มี Action"] + df_action[df_action["department"] == department]["action"].unique().tolist()
        )

        # ===== Downtime Section =====
        st.subheader("⏱️ รายการ Downtime")
        downtime_records = []
        for i in range(3):
            st.markdown(f"**Downtime #{i+1}**")
            dt_choice = st.selectbox(f"เลือก Downtime #{i+1}",
                ["ไม่มี Downtime"] + df_downtime[df_downtime["department"] == department]["sub_category"].unique().tolist()
            )
            dt_remark = st.text_input(f"📝 ระบุปัญหาเพิ่มเติม Downtime #{i+1}", "")
            col1, col2 = st.columns(2)
            with col1:
                dt_start_h = st.selectbox(f"Start Hour DT#{i+1}", list(range(0, 24)))
                dt_start_m = st.selectbox(f"Start Min DT#{i+1}", list(range(0, 60, 5)))
            with col2:
                dt_end_h = st.selectbox(f"End Hour DT#{i+1}", list(range(0, 24)))
                dt_end_m = st.selectbox(f"End Min DT#{i+1}", list(range(0, 60, 5)))
            dt_minutes = ((dt_end_h*60+dt_end_m) - (dt_start_h*60+dt_start_m))
            if dt_minutes < 0: dt_minutes += 24*60
            if dt_choice != "ไม่มี Downtime":
                downtime_records.append((dt_choice, dt_minutes, dt_remark))

        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            with engine.begin() as conn:
                result = conn.execute(text("""
                    INSERT INTO production_record
                    (log_date, shift, department, machine_name, part_no, woc_number,
                     start_time, end_time, work_minutes, ok_qty, ng_qty, untest_qty,
                     speed, main_4m, problem, problem_remark, action,
                     emp_code, operator)
                    VALUES
                    (:log_date,:shift,:department,:machine_name,:part_no,:woc_number,
                     :start_time,:end_time,:work_minutes,:ok_qty,:ng_qty,:untest_qty,
                     :speed,:main_4m,:problem,:problem_remark,:action,
                     :emp_code,:operator) RETURNING id
                """), {
                    "log_date": log_date, "shift": shift, "department": department,
                    "machine_name": machine_name, "part_no": part_no, "woc_number": woc_number,
                    "start_time": start_time, "end_time": end_time, "work_minutes": work_minutes,
                    "ok_qty": int(ok_qty), "ng_qty": int(ng_qty), "untest_qty": int(untest_qty),
                    "speed": int(speed), "main_4m": main_4m, "problem": problem,
                    "problem_remark": problem_remark, "action": action,
                    "emp_code": operator_code, "operator": operator
                })
                prod_id = result.fetchone()[0]

                for (subcat, mins, remark) in downtime_records:
                    conn.execute(text("""
                        INSERT INTO downtime_log (production_id, department, main_category, sub_category, downtime_min, remark)
                        VALUES (:pid, :dept, '', :subcat, :mins, :remark)
                    """), {"pid": prod_id, "dept": department, "subcat": subcat, "mins": mins, "remark": remark})

            st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว")

# ================================
# MODE : REPORT
# ================================
elif mode == "Report":
    if operator_role not in ["Supervisor","Admin","Engineer","Manager"]:
        st.error("❌ คุณไม่มีสิทธิ์เข้าถึง Report")
    else:
        st.title("📊 Production Report")
        start_date = st.date_input("เริ่มวันที่", value=date.today())
        end_date = st.date_input("ถึงวันที่", value=date.today())
        df = pd.read_sql(text("""
            SELECT pr.*, dt.sub_category as downtime, dt.downtime_min, dt.remark as downtime_remark
            FROM production_record pr
            LEFT JOIN downtime_log dt ON pr.id = dt.production_id
            WHERE log_date BETWEEN :s AND :e
            ORDER BY log_date DESC
        """), engine, params={"s": start_date, "e": end_date})
        st.dataframe(df, use_container_width=True)
