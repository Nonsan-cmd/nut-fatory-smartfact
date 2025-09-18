import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, time

# ================================
# CONFIG
# ================================
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================================
# LOGIN SESSION
# ================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

def login(emp_code, password):
    res = supabase.table("user_roles").select("*").eq("emp_code", emp_code).eq("password", password).execute()
    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        return True
    return False

if not st.session_state.logged_in:
    st.title("🔑 Login")
    emp_code = st.text_input("Employee Code")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(emp_code, password):
            st.success(f"Welcome {st.session_state.user['emp_name']} ({st.session_state.user['role']})")
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

user = st.session_state.user
st.sidebar.success(f"👤 {user['emp_name']} ({user['role']})")

# ================================
# PAGE NAVIGATION
# ================================
mode = st.sidebar.radio("เลือกโหมด", ["Production Record", "Report"])

# ================================
# PRODUCTION RECORD
# ================================
if mode == "Production Record":
    st.header("📝 Production Record")

    # ----------------------------
    # Basic Info
    # ----------------------------
    log_date = st.date_input("📅 วันที่ทำงาน", datetime.now().date())
    shift = st.selectbox("⏰ กะ", ["เช้า", "บ่าย", "ดึก"])
    department = user["department"]
    st.text_input("📌 แผนก", department, disabled=True)

    # ----------------------------
    # Machine
    # ----------------------------
    machines = supabase.table("machine_list").select("machine_name").eq("department", department).execute()
    machine_name = st.selectbox("⚙️ เครื่องจักร", [m["machine_name"] for m in machines.data])

    # ----------------------------
    # Part
    # ----------------------------
    parts = supabase.table("part_master").select("*").execute()
    part_no = st.selectbox("🔩 Part No", [p["part_no"] for p in parts.data])

    woc_number = st.text_input("📑 Work Order Card (WOC)")
    start_col, end_col = st.columns(2)
    with start_col:
        start_time = st.time_input("Start Time", time(8, 0))
    with end_col:
        end_time = st.time_input("End Time", time(17, 0))
    work_minutes = (datetime.combine(datetime.today(), end_time) -
                    datetime.combine(datetime.today(), start_time)).seconds // 60

    # ----------------------------
    # Quantity
    # ----------------------------
    ok_qty = st.number_input("✅ OK Qty", min_value=0, value=0)
    ng_qty = st.number_input("❌ NG Qty", min_value=0, value=0)
    untest_qty = st.number_input("🔎 Untest Qty (FI Only)", min_value=0, value=0 if department != "FI" else 0)
    speed = st.number_input("⚡ Machine Speed (pcs/min)", min_value=0, value=0)

    # ----------------------------
    # 4M
    # ----------------------------
    st.subheader("⚠️ สาเหตุปัญหา (4M)")
    main_4m_options = supabase.table("problem_master").select("main_4m").eq("department", department).execute()
    main_4m_list = sorted(list(set([m["main_4m"] for m in main_4m_options.data])))
    main_4m = st.selectbox("เลือก 4M", main_4m_list)

    problem_options = supabase.table("problem_master").select("problem").eq("department", department).eq("main_4m", main_4m).execute()
    problem = st.selectbox("📌 เลือกปัญหา", [p["problem"] for p in problem_options.data])

    action_options = supabase.table("action_master").select("action").eq("department", department).execute()
    action = st.selectbox("🛠️ เลือก Action", [a["action"] for a in action_options.data])

    problem_remark = st.text_input("📝 ระบุปัญหาเพิ่มเติม (ถ้ามี)", "")

    # ----------------------------
    # Downtime (Multi)
    # ----------------------------
    st.subheader("⏱️ รายการ Downtime")
    if "downtime_rows" not in st.session_state:
        st.session_state.downtime_rows = 1

    downtime_data = []
    for i in range(st.session_state.downtime_rows):
        st.markdown(f"### Downtime #{i+1}")
        dt_col1, dt_col2 = st.columns(2)
        categories = supabase.table("downtime_master").select("*").eq("department", department).execute()
        main_category = dt_col1.selectbox(f"Main Category #{i+1}", [c["main_category"] for c in categories.data], key=f"main_cat_{i}")
        sub_options = [c["sub_category"] for c in categories.data if c["main_category"] == main_category]
        sub_category = dt_col2.selectbox(f"Sub Category #{i+1}", sub_options, key=f"sub_cat_{i}")

        dt_time1, dt_time2 = st.columns(2)
        start_dt = dt_time1.time_input(f"Start Time #{i+1}", time(9, 0), key=f"dt_start_{i}")
        end_dt = dt_time2.time_input(f"End Time #{i+1}", time(10, 0), key=f"dt_end_{i}")
        downtime_min = (datetime.combine(datetime.today(), end_dt) -
                        datetime.combine(datetime.today(), start_dt)).seconds // 60

        downtime_data.append({
            "main_category": main_category,
            "sub_category": sub_category,
            "start_time": str(start_dt),
            "end_time": str(end_dt),
            "downtime_min": downtime_min
        })

    if st.button("➕ เพิ่ม Downtime"):
        st.session_state.downtime_rows += 1
        st.rerun()

    # ----------------------------
    # Save
    # ----------------------------
    if st.button("✅ บันทึกข้อมูล"):
        record = {
            "log_date": str(log_date),
            "shift": shift,
            "department": department,
            "machine_name": machine_name,
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
            "problem": problem,
            "action": action,
            "emp_code": user["emp_code"],
            "operator": user["emp_name"]
        }
        res = supabase.table("production_record").insert(record).execute()
        prod_id = res.data[0]["id"]

        for d in downtime_data:
            d["production_id"] = prod_id
            d["department"] = department
            supabase.table("downtime_log").insert(d).execute()

        st.success("บันทึกข้อมูลสำเร็จ ✅")

# ================================
# REPORT
# ================================
elif mode == "Report":
    if user["role"] not in ["Supervisor", "Engineer", "Manager", "Admin"]:
        st.error("คุณไม่มีสิทธิ์เข้า Report Mode")
        st.stop()

    st.header("📊 Report Summary")

    # Filter
    start_date = st.date_input("Start Date", datetime.now().date())
    end_date = st.date_input("End Date", datetime.now().date())
    dept_filter = st.selectbox("เลือกแผนก", ["All", "FM", "TP", "FI"])

    q = supabase.table("production_record").select("*").gte("log_date", str(start_date)).lte("log_date", str(end_date))
    if dept_filter != "All":
        q = q.eq("department", dept_filter)
    records = q.execute()

    if records.data:
        df = pd.DataFrame(records.data)
        st.dataframe(df)
    else:
        st.info("ไม่พบข้อมูล")
