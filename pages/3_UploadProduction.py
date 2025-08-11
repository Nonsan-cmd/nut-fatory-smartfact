import streamlit as st
import pandas as pd
import psycopg2
import io
from datetime import datetime

# === Database Connection ===
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

st.set_page_config(page_title="Upload Production", layout="wide")
st.title("📤 Upload Production Record")

uploaded_file = st.file_uploader("📂 Upload Excel File (.xlsx)", type="xlsx")

# ---- helper: ทำความสะอาดตัวเลขให้ปลอดภัยต่อ INTEGER ----
INT32_MAX = 2_147_483_647
def clean_int_series(s, default=0):
    s = pd.to_numeric(s, errors="coerce").fillna(default)
    # ตัดค่าให้อยู่ในช่วง int32
    s = s.clip(lower=0, upper=INT32_MAX).astype("int64")
    return s

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        all_data = []

        # โหลด master จาก DB และเปลี่ยนชื่อคอลัมน์ id ให้ไม่ชนกันตั้งแต่ต้น
        with get_connection() as conn:
            machine_df = pd.read_sql(
                "SELECT id AS machine_id, machine_name FROM machine_list",
                conn
            )
            part_df = pd.read_sql(
                "SELECT id AS part_id, part_no FROM part_master",
                conn
            )

        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, dtype=str)  # อ่านเป็น string เพื่อลดปัญหาชนิดข้อมูล
            # หา column เริ่มต้นจาก 'log_date'
            if "log_date" not in df.columns:
                st.warning(f"❌ ไม่พบคอลัมน์ 'log_date' ในชีท {sheet}")
                continue

            # ให้แน่ใจว่าชื่อคอลัมน์มาตรฐานครบ
            # ต้องมี: log_date, shift, department, machine_name, part_no, plan_qty, actual_qty, defect_qty, created_by, remark
            needed = ["log_date", "shift", "department", "machine_name", "part_no",
                      "plan_qty", "actual_qty", "defect_qty", "created_by", "remark"]
            for c in needed:
                if c not in df.columns:
                    df[c] = None  # เติมคอลัมน์ที่หายไป

            # ตัดเหลือเฉพาะคอลัมน์ที่ต้องใช้
            df = df[needed].copy()

            # ทำความสะอาดเบื้องต้น
            df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce").dt.date
            df["shift"] = df["shift"].fillna("").str.strip()
            df["department"] = df["department"].fillna("").str.strip()
            df["machine_name"] = df["machine_name"].fillna("").str.strip()
            df["part_no"] = df["part_no"].fillna("").str.strip()
            df["created_by"] = df["created_by"].fillna("").str.strip()
            df["remark"] = df["remark"].fillna("").astype(str)

            # กรอง record ที่ไม่มีวันที่/เครื่อง/part
            df = df.dropna(subset=["log_date"])
            df = df[df["machine_name"] != ""]
            df = df[df["part_no"] != ""]

            # map machine_id / part_id
            df = df.merge(machine_df, how="left", on="machine_name")
            df = df.merge(part_df, how="left", on="part_no")

            # แจ้งเตือนรายการที่หา id ไม่เจอ
            miss_m = df[df["machine_id"].isna()]
            miss_p = df[df["part_id"].isna()]
            if not miss_m.empty:
                st.warning(f"⚠️ ไม่พบเครื่องจักรในฐานข้อมูล: {sorted(miss_m['machine_name'].unique())}")
            if not miss_p.empty:
                st.warning(f"⚠️ ไม่พบ Part No. ในฐานข้อมูล: {sorted(miss_p['part_no'].unique())}")

            df = df.dropna(subset=["machine_id", "part_id"]).copy()

            # แปลงคอลัมน์ตัวเลขอย่างปลอดภัย
            df["plan_qty"] = clean_int_series(df["plan_qty"])
            df["actual_qty"] = clean_int_series(df["actual_qty"])
            df["defect_qty"] = clean_int_series(df["defect_qty"])

            # ตัวระบุเวลา
            df["created_at"] = datetime.now()

            all_data.append(df)

        if not all_data:
            st.info("ไม่มีข้อมูลที่พร้อมอัปโหลด")
            st.stop()

        df_upload = pd.concat(all_data, ignore_index=True)

        # แสดงตัวอย่างข้อมูลก่อนอัปโหลด
        st.subheader("ตัวอย่างข้อมูลที่จะอัปโหลด")
        st.dataframe(df_upload.head(100), use_container_width=True)

        # ปุ่มอัปโหลด
        if st.button("📥 Upload to Database"):
            # เตรียมชุดข้อมูลสำหรับ insert
            rows = []
            for _, r in df_upload.iterrows():
                rows.append((
                    r["log_date"],             # DATE
                    r["shift"],                # TEXT
                    r["department"],           # TEXT
                    int(r["machine_id"]),      # INTEGER
                    int(r["part_id"]),         # INTEGER
                    int(r["plan_qty"]),        # INTEGER
                    int(r["actual_qty"]),      # INTEGER
                    int(r["defect_qty"]),      # INTEGER
                    r["created_by"],           # TEXT
                    r["created_at"],           # TIMESTAMP
                    r["remark"]                # TEXT
                ))

            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.executemany(
                        """
                        INSERT INTO production_log
                        (log_date, shift, department, machine_id, part_id,
                         plan_qty, actual_qty, defect_qty, created_by, created_at, remark)
                        VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        rows
                    )
                    conn.commit()
                st.success(f"✅ Upload เสร็จสมบูรณ์ ({len(rows)} แถว)")
            except Exception as e:
                # จับข้อผิดพลาดแล้วไล่หาแถวที่พัง
                st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")
                st.info("กำลังตรวจสอบแถวที่อาจทำให้เกิดปัญหา...")
                bad = []
                with get_connection() as conn:
                    cur = conn.cursor()
                    for i, vals in enumerate(rows, start=1):
                        try:
                            cur.execute(
                                """
                                INSERT INTO production_log
                                (log_date, shift, department, machine_id, part_id,
                                 plan_qty, actual_qty, defect_qty, created_by, created_at, remark)
                                VALUES
                                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                vals
                            )
                        except Exception as e2:
                            bad.append((i, vals, str(e2)))
                            conn.rollback()
                        else:
                            conn.rollback()  # dry-run เพื่อตรวจสอบเท่านั้น
                if bad:
                    st.error(f"พบบรรทัดที่มีปัญหา {len(bad)} แถว (แสดง 5 แถวแรก):")
                    for i, vals, msg in bad[:5]:
                        st.write(f"แถวที่ {i}: {vals} -> {msg}")

    except Exception as e:
        st.error(f"❌ ไม่สามารถอ่านไฟล์ Excel ได้: {e}")
else:
    st.info("กรุณาอัปโหลดไฟล์ Excel ที่มีคอลัมน์: log_date, shift, department, machine_name, part_no, plan_qty, actual_qty, defect_qty, created_by, remark")
