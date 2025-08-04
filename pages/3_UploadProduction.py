import streamlit as st
import pandas as pd
import psycopg2
import io
from datetime import datetime

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# === UploadProduction Page ===
st.set_page_config(page_title="Upload Production", layout="wide")
st.title("📤 Upload Production Record")

uploaded_file = st.file_uploader("📂 Upload Excel File (.xlsx)", type="xlsx")

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        all_data = []

        with get_connection() as conn:
            machine_df = pd.read_sql("SELECT id, machine_name FROM machine_list", conn)
            part_df = pd.read_sql("SELECT id, part_no FROM part_master", conn)

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, skiprows=0)

            col_start = df.columns.get_loc("log_date") if "log_date" in df.columns else None
            if col_start is None:
                st.warning(f"❌ ไม่พบคอลัมน์ 'log_date' ในชีท {sheet}")
                continue

            df_trimmed = df.iloc[:, col_start:]
            df_trimmed = df_trimmed.dropna(subset=["log_date", "machine_name"], how="any")
            df_trimmed = df_trimmed[df_trimmed["part_no"].notna() & (df_trimmed["part_no"].astype(str).str.strip() != "")]
            df_trimmed["log_date"] = pd.to_datetime(df_trimmed["log_date"]).dt.date
            df_trimmed["created_at"] = datetime.now()

            # Map machine_id
            df_trimmed = df_trimmed.merge(machine_df, how="left", on="machine_name")
            df_trimmed = df_trimmed.rename(columns={"id": "machine_id"})

            # Map part_id
            df_trimmed = df_trimmed.merge(part_df, how="left", on="part_no")
            df_trimmed = df_trimmed.rename(columns={"id": "part_id"})

            # ตรวจสอบ missing
            missing_machine = df_trimmed[df_trimmed["machine_id"].isna()]
            missing_part = df_trimmed[df_trimmed["part_id"].isna()]

            if not missing_machine.empty:
                st.warning(f"⚠️ พบเครื่องจักรที่ไม่ตรงกับฐานข้อมูล: {missing_machine['machine_name'].unique().tolist()}")
            if not missing_part.empty:
                st.warning(f"⚠️ พบ Part No. ที่ไม่ตรงกับฐานข้อมูล: {missing_part['part_no'].unique().tolist()}")

            df_trimmed = df_trimmed.dropna(subset=["machine_id", "part_id"])

            all_data.append(df_trimmed)

        if all_data:
            df_upload = pd.concat(all_data, ignore_index=True)
            st.dataframe(df_upload)

            if st.button("📥 Upload to Database"):
                try:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        for _, row in df_upload.iterrows():
                            cur.execute("""
                                INSERT INTO production_log (log_date, shift, department, machine_id, part_id, plan_qty, actual_qty, defect_qty, created_by, created_at, remark)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                row.get("log_date"),
                                row.get("shift"),
                                row.get("department"),
                                int(row.get("machine_id")),
                                int(row.get("part_id")),
                                row.get("plan_qty", 0),
                                row.get("actual_qty", 0),
                                row.get("defect_qty", 0),
                                row.get("created_by", ""),
                                row.get("created_at"),
                                row.get("remark", "")
                            ))
                        conn.commit()
                    st.success("✅ Upload เสร็จสมบูรณ์")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")
    except Exception as e:
        st.error(f"❌ ไม่สามารถอ่านไฟล์ Excel ได้: {e}")
else:
    st.info("กรุณาอัปโหลดไฟล์ Excel ที่มีข้อมูลการผลิต โดยเริ่มจากคอลัมน์ log_date เป็นต้นไป")
