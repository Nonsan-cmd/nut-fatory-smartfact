
import streamlit as st
import pandas as pd
import psycopg2
import io
from datetime import datetime

# ============ Config ============
st.set_page_config(page_title="Upload Production", layout="wide")
st.title("📤 Upload Production Record")

# ใช้ชื่อผู้ใช้งานจาก session ถ้ามี
current_user = st.session_state.get("username", "")

# ============ DB ============
def get_connection():
    return psycopg2.connect(st.secrets["postgres"]["conn_str"])

# ============ Helper ============
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ทำให้ชื่อคอลัมน์เป็นตัวพิมพ์เล็ก ตัดช่องว่างหน้า-หลัง"""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def coerce_int(s):
    """แปลงเป็น int ถ้าแปลงไม่ได้เป็น 0"""
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)

# ============ UI ============

uploaded_file = st.file_uploader("📂 Upload Excel File (.xlsx)", type=["xlsx"])

if not uploaded_file:
    st.info("กรุณาอัปโหลดไฟล์ Excel ที่มีหัวคอลัมน์ เช่น log_date, shift, department, machine_name, part_no, plan_qty, actual_qty, defect_qty, remark, operator_name")
    st.stop()

try:
    xls = pd.ExcelFile(uploaded_file)
except Exception as e:
    st.error(f"❌ ไม่สามารถอ่านไฟล์ Excel ได้: {e}")
    st.stop()

# โหลด Master
with get_connection() as conn:
    machine_df = pd.read_sql("SELECT id AS machine_id, machine_name FROM machine_list WHERE is_active = TRUE", conn)
    part_df = pd.read_sql("SELECT id AS part_id, part_no FROM part_master WHERE is_active = TRUE", conn)

all_rows = []

for sheet in xls.sheet_names:
    try:
        raw = pd.read_excel(xls, sheet_name=sheet)
        df = normalize_columns(raw)

        # หา index ของคอลัมน์ log_date เพื่อ "ตัดหัว" ซ้ายมือทิ้ง (กันไฟล์มีคอลัมน์โน้ตอยู่ก่อนหน้า)
        if "log_date" in df.columns:
            start_idx = df.columns.get_loc("log_date")
            df = df.iloc[:, start_idx:]
        else:
            st.warning(f"❌ ชีท '{sheet}' ไม่พบคอลัมน์ 'log_date' ข้ามชีทนี้")
            continue

        # เติมคอลัมน์ที่อาจไม่มีมาในไฟล์
        for col in ["remark", "operator_name", "created_by"]:
            if col not in df.columns:
                df[col] = ""

        needed = ["log_date", "shift", "department", "machine_name", "part_no",
                  "plan_qty", "actual_qty", "defect_qty", "remark", "operator_name", "created_by"]

        # ถ้าไฟล์ไม่มีบางคอลัมน์ จำเป็น ให้แจ้งเตือน (ยกเว้น created_by, remark, operator_name ที่เติมว่างไว้แล้ว)
        must_have = ["log_date", "shift", "department", "machine_name", "part_no"]
        missing = [c for c in must_have if c not in df.columns]
        if missing:
            st.warning(f"⚠️ ชีท '{sheet}' ขาดคอลัมน์จำเป็น: {missing} ข้ามชีทนี้")
            continue

        # จำกัดเฉพาะคอลัมน์ที่เราสนใจ (ถ้าบางคอลัมน์ไม่มีก็จะถูกเติมว่างไว้แล้ว)
        df = df.reindex(columns=needed, fill_value="")

        # ทำความสะอาดข้อมูล
        df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce").dt.date
        df = df.dropna(subset=["log_date", "machine_name", "part_no"])

        # number columns
        df["plan_qty"] = coerce_int(df["plan_qty"])
        df["actual_qty"] = coerce_int(df["actual_qty"])
        df["defect_qty"] = coerce_int(df["defect_qty"])

        # created_by ถ้าไม่ใส่ในไฟล์ให้ใช้ผู้ใช้ปัจจุบัน
        df["created_by"] = df["created_by"].apply(lambda x: x if str(x).strip() != "" else current_user)

        # เวลาอัปโหลด
        df["created_at"] = datetime.now()

        # map machine_id / part_id
        df = df.merge(machine_df, how="left", on="machine_name")
        df = df.merge(part_df, how="left", on="part_no")

        # แจ้งรายการที่ไม่แมป
        miss_m = df[df["machine_id"].isna()]
        miss_p = df[df["part_id"].isna()]
        if not miss_m.empty:
            st.warning(f"⚠️ ชีท '{sheet}' พบเครื่องจักรไม่ตรงกับ master: {sorted(miss_m['machine_name'].dropna().unique().tolist())}")
        if not miss_p.empty:
            st.warning(f"⚠️ ชีท '{sheet}' พบ Part No. ไม่ตรงกับ master: {sorted(miss_p['part_no'].dropna().unique().tolist())}")

        # เก็บเฉพาะแถวที่แมปได้
        df_ok = df.dropna(subset=["machine_id", "part_id"]).copy()

        all_rows.append(df_ok)

    except Exception as e:
        st.error(f"❌ อ่านชีท '{sheet}' ล้มเหลว: {e}")

if not all_rows:
    st.stop()

df_upload = pd.concat(all_rows, ignore_index=True)

st.subheader("👀 ตัวอย่างข้อมูลที่จะบันทึก")
preview_cols = [
    "log_date", "shift", "department", "machine_name", "part_no",
    "plan_qty", "actual_qty", "defect_qty", "operator_name", "remark", "created_by"
]
st.dataframe(df_upload[preview_cols], use_container_width=True)

# ปุ่ม Export Preview (optional)
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_upload.to_excel(writer, index=False, sheet_name="upload_preview")
st.download_button("📥 ดาวน์โหลดตัวอย่าง (Excel)",
                   data=buffer.getvalue(),
                   file_name="upload_preview.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
if st.button("📥 Upload to Database", type="primary"):
    try:
        insert_sql = """
            INSERT INTO production_log (
                log_date, shift, department, machine_id, part_id,
                plan_qty, actual_qty, defect_qty,
                created_by, created_at, remark, operator_name
            ) VALUES (
                %(log_date)s, %(shift)s, %(department)s, %(machine_id)s, %(part_id)s,
                %(plan_qty)s, %(actual_qty)s, %(defect_qty)s,
                %(created_by)s, %(created_at)s, %(remark)s, %(operator_name)s
            )
        """

        records = df_upload[[
            "log_date", "shift", "department", "machine_id", "part_id",
            "plan_qty", "actual_qty", "defect_qty", "created_by", "created_at",
            "remark", "operator_name"
        ]].to_dict(orient="records")

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_sql, records)
            conn.commit()

        st.success(f"✅ อัปโหลดสำเร็จ {len(records)} แถว")

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")
