# app.py

import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import date
import requests

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Factory Log System", page_icon="🏭", layout="wide")

# Connect to Supabase Postgres (ผ่าน Pooler)
conn_str = st.secrets["postgres"]["conn_str"]
engine = create_engine(conn_str)

# Telegram
TELEGRAM_TOKEN = st.secrets["telegram"]["token"]
TELEGRAM_CHAT_ID = st.secrets["telegram"]["chat_id"]

def send_telegram(msg: str):
    """ส่งข้อความไปยัง Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        st.warning(f"ไม่สามารถส่ง Telegram: {e}")

# -------------------------------
# Downtime Master (Main + Sub Category)
# -------------------------------
downtime_structure = {
    "MC Downtime": {"D1": "Breakdown - Major", "D2": "Breakdown - Minor", "D3": "Utility Issue"},
    "Quality Problem": {"Q1": "In-process Defect", "Q2": "QA Problem", "Q3": "Other Quality Problem"},
    "Setup and Adjustment": {"S1": "Tool Change", "S2": "Model Change", "S3": "Adjustment / Trial run"},
    "Management Downtime (PM Plan)": {"M1": "Planned Maintenance", "M2": "Waiting for Plan"},
    "Technical Downtime": {"T1": "Process Instability", "T2": "Tool/Die Problem", "T3": "Waiting Tool"},
    "Other": {"O1": "Material Shortage", "O2": "Waiting / Box", "O3": "Man Issue"},
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
        department = st.selectbox("🏭 แผนก", ["FM", "TP", "FI"])
        machine_name = st.text_input("⚙️ เครื่องจักร")
        part_no = st.text_input("🔩 Part No.")
        output_qty = st.number_input("✅ จำนวนผลิต (ชิ้น)", min_value=0, step=1)
        ng_qty = st.number_input("❌ NG (ชิ้น)", min_value=0, step=1)
        downtime_min = st.number_input("⏱️ Downtime (นาที)", min_value=0, step=1)
        operator = st.text_input("👷 ผู้บันทึก")

        submitted = st.form_submit_button("✅ บันทึก")
        if submitted:
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        insert into production_log 
                        (log_date, shift, department, machine_name, part_no, output_qty, ng_qty, downtime_min, operator) 
                        values (:log_date, :shift, :department, :machine_name, :part_no, :output_qty, :ng_qty, :downtime_min, :operator)
                    """), {
                        "log_date": log_date,
                        "shift": shift,
                        "department": department,
                        "machine_name": machine_name,
                        "part_no": part_no,
                        "output_qty": int(output_qty),
                        "ng_qty": int(ng_qty),
                        "downtime_min": int(downtime_min),
                        "operator": operator
                    })
                st.success("✅ บันทึก Production สำเร็จ")

                send_telegram(
                    f"📑 Production Record\n"
                    f"Date: {log_date}\nShift: {shift}\nDept: {department}\nMachine: {machine_name}\nPart: {part_no}\n"
                    f"Output: {output_qty}\nNG: {ng_qty}\nDowntime: {downtime_min} min\nBy: {operator}"
                )
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Show history + Delete
    st.subheader("📋 รายการ Production ล่าสุด")
    try:
        df = pd.read_sql("select * from production_log order by created_at desc limit 20", engine)
        st.dataframe(df, use_container_width=True)

        with st.expander("🗑 ลบข้อมูล Production"):
            del_date = st.date_input("เลือกวันที่ที่จะลบ", value=date.today(), key="del_prod")
            if st.button("❌ ลบข้อมูล Production วันที่นี้"):
                with engine.begin() as conn:
                    conn.execute(text("delete from production_log where log_date = :d"), {"d": del_date})
                st.warning(f"ลบข้อมูล Production วันที่ {del_date} เรียบร้อย")
    except Exception as e:
        st.warning(f"ไม่สามารถโหลดข้อมูล: {e}")

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
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        insert into downtime_log 
                        (log_date, shift, department, machine_name, main_category, sub_category, loss_code, downtime_min, operator, remark) 
                        values (:log_date, :shift, :department, :machine_name, :main_category, :sub_category, :loss_code, :downtime_min, :operator, :remark)
                    """), {
                        "log_date": log_date,
                        "shift": shift,
                        "department": department,
                        "machine_name": machine_name,
                        "main_category": main_category,
                        "sub_category": sub_category,
                        "loss_code": loss_code,
                        "downtime_min": int(downtime_min),
                        "operator": operator,
                        "remark": remark
                    })
                st.success("✅ บันทึก Downtime สำเร็จ")

                send_telegram(
                    f"⏱️ Downtime Record\n"
                    f"Date: {log_date}\nShift: {shift}\nDept: {department}\nMachine: {machine_name}\n"
                    f"Category: {main_category}\nCode: {loss_code} - {sub_category}\n"
                    f"Downtime: {downtime_min} min\nBy: {operator}"
                )
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Show history + Delete
    st.subheader("📋 รายการ Downtime ล่าสุด")
    try:
        df = pd.read_sql("select * from downtime_log order by created_at desc limit 20", engine)
        st.dataframe(df, use_container_width=True)

        with st.expander("🗑 ลบข้อมูล Downtime"):
            del_date = st.date_input("เลือกวันที่ที่จะลบ", value=date.today(), key="del_dt")
            if st.button("❌ ลบข้อมูล Downtime วันที่นี้"):
                with engine.begin() as conn:
                    conn.execute(text("delete from downtime_log where log_date = :d"), {"d": del_date})
                st.warning(f"ลบข้อมูล Downtime วันที่ {del_date} เรียบร้อย")
    except Exception as e:
        st.warning(f"ไม่สามารถโหลดข้อมูล: {e}")
