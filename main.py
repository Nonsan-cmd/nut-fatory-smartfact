import streamlit as st
from supabase import create_client, Client
from datetime import datetime, time
import pytz

# ================================
# CONFIG
# ================================
st.set_page_config(page_title="Factory App", page_icon="🏭", layout="wide")

# Supabase Connect
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TZ = pytz.timezone("Asia/Bangkok")

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
            res = supabase.table("user_roles").select("*").eq("emp_code", emp_code).eq("password", password).execute()
            if res.data:
                st.session_state.user = res.data[0]
                st.success(f"ยินดีต้อนรับ {st.session_state.user['emp_name']} ({st.session_state.user['role']})")
            else:
                st.error("รหัสพนักงานหรือรหัสผ่านไม่ถูกต้อง")

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
# PRODUCTION RECORD FORM
# ================================
if mode == "Production Record":
    st.header("📒 บันทึกการผลิต")

    with st.form("prod_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันที่", datetime.now(TZ).date())
        shift = st.selectbox("กะการทำงาน", ["Day", "Night"])
        machine = st.selectbox("🛠️ เครื่องจักร", 
            [m["machine_name"] for m in supabase.table("machine_list").select("*").eq("department", user["department"]).execute().data]
        )
        part_no = st.selectbox("รหัสงาน (Part No)", 
            [p["part_no"] for p in supabase.table("part_master").select("*").execute().data]
        )
        woc_number = st.text_input("WOC Number")

        start_time = st.time_input("⏱️ เวลาเริ่ม", value=time(8, 0))
        end_time = st.time_input("⏱️ เวลาสิ้นสุด", value=time(17, 0))

        ok_qty = st.number_input("✅ OK Qty", 0, step=1)
        ng_qty = st.number_input("❌ NG Qty", 0, step=1)
        untest_qty = st.number_input("❓ Untested Qty", 0, step=1)
        speed = st.number_input("⚡ Machine Speed (pcs/min)", 0, step=1)

        # ================================
        # 4M + Problem + Action
        # ================================
        st.subheader("⚠️ สาเหตุปัญหา (4M)")
        main_4m = st.selectbox("เลือก 4M", ["Man", "Machine", "Material", "Method", "ไม่มีปัญหา"])
        problems = supabase.table("problem_master").select("*").eq("department", user["department"]).execute().data
        actions = supabase.table("action_master").select("*").eq("department", user["department"]).execute().data

        problem = st.selectbox("📌 เลือกปัญหา", [""] + [p["problem"] for p in problems])
        problem_custom = st.text_input("📝 ระบุปัญหาเพิ่มเติม (ถ้ามี)")
        action = st.selectbox("🛠️ เลือก Action", [""] + [a["action"] for a in actions])
        action_custom = st.text_input("📝 ระบุ Action เพิ่มเติม (ถ้ามี)")

        # ================================
        # MULTI DOWNTIME
        # ================================
        st.subheader("⏱️ รายการ Downtime")

        if "downtime_count" not in st.session_state:
            st.session_state.downtime_count = 1

        add_downtime = st.form_submit_button("➕ เพิ่ม Downtime")
        if add_downtime:
            st.session_state.downtime_count += 1

        downtime_entries = []
        dt_master = supabase.table("downtime_master").select("*").eq("department", user["department"]).execute().data

        for i in range(st.session_state.downtime_count):
            st.markdown(f"### Downtime #{i+1}")
            sub_category = st.selectbox(
                f"📌 เลือก Downtime #{i+1}", 
                ["ไม่มี Downtime"] + [d["sub_category"] for d in dt_master],
                key=f"dt_sub_{i}"
            )
            dt_custom = st.text_input(f"📝 ระบุ Downtime เพิ่มเติม #{i+1}", key=f"dt_custom_{i}")
            start_dt = st.time_input(f"⏱️ เริ่ม Downtime #{i+1}", value=time(0,0), key=f"dt_start_{i}")
            end_dt = st.time_input(f"⏱️ สิ้นสุด Downtime #{i+1}", value=time(0,0), key=f"dt_end_{i}")
            
            if sub_category != "ไม่มี Downtime":
                delta_min = (datetime.combine(datetime.today(), end_dt) - datetime.combine(datetime.today(), start_dt)).seconds // 60
            else:
                delta_min = 0

            downtime_entries.append({
                "sub_category": sub_category if sub_category != "ไม่มี Downtime" else dt_custom,
                "downtime_min": delta_min
            })

        # ================================
        # SUBMIT FORM
        # ================================
        submitted = st.form_submit_button("✅ บันทึกข้อมูล")
        if submitted:
            work_minutes = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).seconds // 60
            problem_final = problem_custom if problem_custom else problem
            action_final = action_custom if action_custom else action

            res = supabase.table("production_record").insert({
                "log_date": str(log_date),
                "shift": shift,
                "department": user["department"],
                "machine_name": machine,
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
            }).execute()

            prod_id = res.data[0]["id"]

            # save downtime logs
            for d in downtime_entries:
                if d["sub_category"]:
                    supabase.table("downtime_log").insert({
                        "production_id": prod_id,
                        "department": user["department"],
                        "main_category": "N/A",
                        "loss_code": "N/A",
                        "sub_category": d["sub_category"],
                        "downtime_min": d["downtime_min"]
                    }).execute()

            st.success("✅ บันทึกข้อมูลสำเร็จ!")

# ================================
# REPORT
# ================================
if mode == "Report":
    st.header("📊 รายงานการผลิต")
    data = supabase.table("production_record").select("*").eq("department", user["department"]).execute().data
    st.dataframe(data)
