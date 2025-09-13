# app.py

import streamlit as st
from supabase import create_client
from datetime import date

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Factory Log System", page_icon="🏭", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

# -------------------------------
# Downtime Master
# -------------------------------
downtime_structure = {
    "MC Downtime": {
        "D1": "Breakdown - Major",
        "D2": "Breakdown - Minor",
        "D3": "Utility Issue",
    },
    "Quality Problem": {
        "Q1": "In-process Defect",
        "Q2": "QA Problem",
        "Q3": "Other Quality Problem",
    },
    "Setup and Adjustment": {
        "S1": "Tool Change",
        "S2": "Model Change",
        "S3": "Adjustment / Trial run",
    },
    "Management Downtime (PM Plan)": {
        "M1": "Planned Maintenance",
        "M2": "Waiting for Plan",
    },
    "Technical Downtime": {
        "T1": "Process Instability",
        "T2": "Tool/Die Problem",
        "T3": "Waiting Tool",
    },
    "Other": {
        "O1": "Material Shortage",
        "O2": "Waiting / Box",
        "O3": "Man Issue",
    }
}

# -------------------------------
# Sidebar Menu
# -------------------------------
menu = st.sidebar.radio("📌 เลือกเมนู", ["Production Record", "Downtime Record"])

# -------------------------------
# Production Record
# -------------------------------
if menu == "Production Record":
    st.title("📑 Production Record")

    with st.form("prod_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันที่บันทึก", value=date.today())
        shift = st.selectbox("🕒 กะการทำงาน", ["เช้า", "บ่าย", "ดึก"])
        machine_name = st.text_input("⚙️ เครื่องจักร")
        part_no = st.text_input("🔩 Part No.")
        output_qty = st.number_input("✅ จำนวนผลิต (ชิ้น)", min_value=0, step=1)
        ng_qty = st.number_input("❌ NG (ชิ้น)", min_value=0, step=1)
        downtime_min = st.number_input("⏱️ Downtime (นาที)", min_value=0, step=1)
        operator = st.text_input("👷 ผู้บันทึก")

        submitted = st.form_submit_button("✅ บันทึก")
        if submitted:
            data = {
                "log_date": log_date.isoformat(),
                "shift": shift,
                "machine_name": machine_name,
                "part_no": part_no,
                "output_qty": int(output_qty),
                "ng_qty": int(ng_qty),
                "downtime_min": int(downtime_min),
                "operator": operator,
            }
            res = supabase.table("production_log").insert(data).execute()
            st.success("✅ บันทึก Production สำเร็จ") if res.data else st.error("❌ Error")

    # Show history
    st.subheader("📋 รายการ Production ล่าสุด")
    logs = supabase.table("production_log").select("*").order("created_at", desc=True).limit(10).execute()
    if logs.data:
        st.dataframe(logs.data, use_container_width=True)
    else:
        st.info("ℹ️ ยังไม่มีข้อมูล Production")

# -------------------------------
# Downtime Record
# -------------------------------
elif menu == "Downtime Record":
    st.title("⏱️ Downtime Record")

    with st.form("dt_form", clear_on_submit=True):
        log_date = st.date_input("📅 วันที่บันทึก", value=date.today())
        shift = st.selectbox("🕒 กะการทำงาน", ["เช้า", "บ่าย", "ดึก"])
        department = st.selectbox("🏭 แผนก", ["FM", "TP", "FI"])
        machine_name = st.text_input("⚙️ เครื่องจักร")

        main_category = st.selectbox("📌 Main Category", list(downtime_structure.keys()))
        sub_dict = downtime_structure.get(main_category, {})
        loss_code = st.selectbox("🔢 Sub Category (Code)", list(sub_dict.keys()))
        sub_category = sub_dict[loss_code]

        downtime_min = st.number_input("⏱️ Downtime (นาที)", min_value=0, step=1)
        operator = st.text_input("👷 ผู้บันทึก")
        remark = st.text_area("📝 หมายเหตุ")

        submitted = st.form_submit_button("✅ บันทึก")
        if submitted:
            data = {
                "log_date": log_date.isoformat(),
                "shift": shift,
                "department": department,
                "machine_name": machine_name,
                "main_category": main_category,
                "sub_category": sub_category,
                "loss_code": loss_code,
                "downtime_min": int(downtime_min),
                "operator": operator,
                "remark": remark,
            }
            res = supabase.table("downtime_log").insert(data).execute()
            st.success("✅ บันทึก Downtime สำเร็จ") if res.data else st.error("❌ Error")

    # Show history
    st.subheader("📋 รายการ Downtime ล่าสุด")
    logs = supabase.table("downtime_log").select("*").order("created_at", desc=True).limit(10).execute()
    if logs.data:
        st.dataframe(logs.data, use_container_width=True)
    else:
        st.info("ℹ️ ยังไม่มีข้อมูล Downtime")
