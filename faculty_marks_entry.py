import json
import datetime as dt
from typing import Dict, List, Tuple

import streamlit as st
import pandas as pd

import firebase_admin
from firebase_admin import credentials, firestore

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Faculty Grading Dashboard", layout="wide")
st.title("🧑‍🏫 Faculty Grading Dashboard")

# =========================
# FIREBASE INIT (robust)
# =========================
def init_firestore():
    if firebase_admin._apps:
        return firestore.client()

    cfg = None
    # Try secrets (supports firebase_key as JSON string, or [firebase] table)
    try:
        raw = st.secrets.get("firebase_key", None)
        if raw is None:
            raw = st.secrets.get("firebase", None)
        if raw is not None:
            cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        cfg = None

    if cfg:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
        return firestore.client()

    # Fallback to local file
    import os, json as _json
    if os.path.exists("firebase_key.json"):
        with open("firebase_key.json", "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
        return firestore.client()

    st.error("Firebase configuration not found (secrets or local firebase_key.json).")
    st.stop()

db = init_firestore()

# =========================
# CSV MAP (same names as your main app)
# =========================
FILES = {
    "Aptitude Test": "aptitude.csv",
    "Adaptability & Learning": "adaptability_learning.csv",
    "Communication Skills - Objective": "communcation_skills_objective.csv",
    "Communication Skills - Descriptive": "communcation_skills_descriptive.csv",
}

# =========================
# HELPERS
# =========================
@st.cache_data(ttl=20)
def load_section_csv(section: str) -> pd.DataFrame:
    """Load the section CSV that contains QuestionID, Question, Type, Option1..4, Correct, and optional Max/Marks."""
    import os
    path = FILES.get(section, "")
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    # normalize whitespace
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    return df

@st.cache_data(ttl=20)
def fetch_submissions(collection: str = "student_responses") -> pd.DataFrame:
    docs = db.collection(collection).stream()
    data = []
    for d in docs:
        x = d.to_dict()
        x["_doc_id"] = d.id
        data.append(x)
    return pd.DataFrame(data) if data else pd.DataFrame()

def df_mcq_index(df_csv: pd.DataFrame) -> Dict[str, dict]:
    """
    Build an index: QuestionID -> {
        "type": "mcq"/"short"/..., 
        "correct": normalized correct key (option text or letter), 
        "marks": weight (float),
        "options": [Option1..Option4]  (normalized)
    }
    """
    out = {}
    if df_csv.empty: 
        return out

    # detect option columns
    opt_cols = [c for c in df_csv.columns if c.lower().startswith("option")]
    for _, row in df_csv.iterrows():
        qid = str(row.get("QuestionID", "")).strip()
        if not qid:
            continue
        qtype = str(row.get("Type", "")).strip().lower()
        # weight/maximum
        marks = None
        for cand in ["Marks", "Max", "MaxMarks", "Weight"]:
            if cand in df_csv.columns and pd.notna(row.get(cand)):
                try:
                    marks = float(row[cand])
                except Exception:
                    pass
                break
        if marks is None:
            # default: mcq 1, short 1
            marks = 1.0 if qtype == "mcq" else 1.0

        # options (normalized)
        opts = []
        for oc in opt_cols:
            val = row.get(oc)
            if pd.notna(val):
                opts.append(str(val).strip().lower())
        # correct can be A/B/C/D, 1/2/3/4, or exact option text
        corr_raw = row.get("Correct", "")
        corr_norm = str(corr_raw).strip()
        out[qid] = {
            "type": qtype,
            "marks": float(marks),
            "correct": corr_norm,
            "options": opts,
        }
    return out

def normalize_answer(text: str) -> str:
    return (text or "").strip().lower()

def mcq_match(student_answer: str, qmeta: dict) -> bool:
    """Return True if student's MCQ answer matches qmeta['Correct'].
       Supports A/B/C/D, 1..n, or exact text match against options."""
    ans = normalize_answer(student_answer)
    corr = str(qmeta.get("correct", "")).strip()

    # letter or number mapping to option index
    letters = {"a":0, "b":1, "c":2, "d":3, "e":4}
    nums    = {"1":0, "2":1, "3":2, "4":3, "5":4}

    opts = qmeta.get("options", [])
    if not ans:
        return False

    # if student's answer equals exact option text
    if ans in opts:
        ans_idx = opts.index(ans)
    else:
        # if student's answer is letter/number
        if ans in letters:
            ans_idx = letters[ans]
        elif ans in nums:
            ans_idx = nums[ans]
        else:
            # last try: raw text vs raw correct
            return ans == normalize_answer(corr)

    # Map correct corr to index
    corr_l = normalize_answer(corr)
    if corr_l in letters:
        corr_idx = letters[corr_l]
    elif corr_l in nums:
        corr_idx = nums[corr_l]
    else:
        # correct as text
        corr_idx = opts.index(corr_l) if corr_l in opts else None

    if corr_idx is None:
        return False

    return ans_idx == corr_idx

def compute_auto_score(section_csv: pd.DataFrame, responses: List[dict]) -> Tuple[float, Dict[str, int]]:
    """Compute MCQ auto-score and return score plus per-question correctness (0/1)."""
    idx = df_mcq_index(section_csv)
    score = 0.0
    detail = {}
    for r in responses or []:
        if str(r.get("Type","")).lower() != "mcq": 
            continue
        qid = str(r.get("QuestionID", "")).strip()
        if not qid or qid not in idx: 
            continue
        if mcq_match(r.get("Response",""), idx[qid]):
            score += float(idx[qid]["marks"] or 1.0)
            detail[qid] = 1
        else:
            detail[qid] = 0
    return score, detail

def get_short_items(responses: List[dict]) -> List[dict]:
    return [r for r in (responses or []) if str(r.get("Type","")).lower() == "short"]

def per_question_max_for_short(df_csv: pd.DataFrame) -> Dict[str, int]:
    """QuestionID->Max (int) for short; default 1 if not provided."""
    out = {}
    if df_csv.empty: 
        return out
    for _, row in df_csv.iterrows():
        if str(row.get("Type","")).strip().lower() != "short":
            continue
        qid = str(row.get("QuestionID","")).strip()
        if not qid: continue
        mx = None
        for cand in ["Max","Marks","MaxMarks","Weight"]:
            if cand in df_csv.columns and pd.notna(row.get(cand)):
                try:
                    mx = int(float(row[cand]))
                except Exception:
                    pass
                break
        if mx is None:
            mx = 1
        out[qid] = max(1, mx)
    return out

def save_marks(doc_id: str, short_marks: Dict[str,int], auto_score: float):
    total_short = sum(int(v or 0) for v in short_marks.values())
    total = float(auto_score) + float(total_short)
    db.collection("student_responses").document(doc_id).set(
        {
            "ShortMarks": short_marks,
            "ShortMarksTotal": float(total_short),
            "AutoScore": float(auto_score),
            "TotalScore": float(total),
            "Evaluated": True,
            "EvaluatedAt": dt.datetime.utcnow().isoformat()
        },
        merge=True
    )
    return total_short, total

# =========================
# FILTERS / CONTROLS
# =========================
st.sidebar.header("Filters")
section = st.sidebar.selectbox("Section", list(FILES.keys()))
page_size = st.sidebar.selectbox("Page size", [25, 50, 100, 200], index=1)
search = st.sidebar.text_input("Search (roll or name)").strip().lower()

df_csv = load_section_csv(section)
df_all = fetch_submissions("student_responses")
if df_all.empty:
    st.info("No submissions found.")
    st.stop()

df = df_all[df_all["Section"] == section].copy()
if df.empty:
    st.info(f"No submissions for **{section}** yet.")
    st.stop()

# quick flags
df["Evaluated"] = df["Evaluated"].fillna(False)
df["Descriptive"] = df["ShortMarksTotal"].fillna(0.0)
df["AutoScore"] = df["AutoScore"].fillna(0.0)
df["TotalScore"] = df["TotalScore"].fillna(df["Descriptive"] + df["AutoScore"])

# search
if search:
    df = df[df.apply(lambda r: search in str(r.get("Roll","")).lower() or
                               search in str(r.get("Name","")).lower(), axis=1)]

# counts + tabs
total = len(df)
graded = int(df["Evaluated"].sum())
pending = total - graded
c1,c2,c3 = st.columns(3)
c1.metric("Total", total)
c2.metric("Graded", graded)
c3.metric("Pending", pending)

tab_pending, tab_graded = st.tabs([f"⏳ Pending ({pending})", f"✅ Graded ({graded})"])

def list_table(_df: pd.DataFrame):
    _df = _df[["Roll","Name","TotalScore","AutoScore","Descriptive","_doc_id"]].sort_values(["Roll"])
    _df = _df.rename(columns={"_doc_id":"DocID"})
    return _df

with tab_pending:
    dfP = df[df["Evaluated"] != True].copy()
    if dfP.empty:
        st.info("Everything is graded — great job!")
    else:
        pages = max(1, (len(dfP)+page_size-1)//page_size)
        p = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1)
        sl = (p-1)*page_size; sr = sl+page_size
        st.dataframe(list_table(dfP).iloc[sl:sr], use_container_width=True, height=360)

with tab_graded:
    dfG = df[df["Evaluated"] == True].copy()
    if dfG.empty:
        st.info("No graded submissions yet.")
    else:
        pages_g = max(1, (len(dfG)+page_size-1)//page_size)
        pg = st.number_input("Page (graded)", min_value=1, max_value=pages_g, value=1, step=1)
        slg = (pg-1)*page_size; srg = slg+page_size
        st.dataframe(list_table(dfG).iloc[slg:srg], use_container_width=True, height=360)

st.divider()

# =========================
# PICK A STUDENT TO GRADE
# =========================
left, right = st.columns([0.42, 0.58], gap="large")

with left:
    st.subheader("Select a student")
    # order: pending first
    df = df.sort_values(["Evaluated","Roll"], ascending=[True, True])
    choices = df.apply(lambda r: f"{'🟡' if not r['Evaluated'] else '🟢'}  {r['Roll']} — {r['Name']}  ({r['_doc_id']})", axis=1).tolist()
    choice = st.selectbox("Student", choices)
    doc_id = choice.split("(")[-1].rstrip(")")
    row = df[df["_doc_id"] == doc_id].iloc[0]

    st.markdown(f"**Roll:** {row['Roll']}  |  **Name:** {row['Name']}  |  **Section:** {row['Section']}")
    st.caption(f"AutoScore: {row['AutoScore']:.2f}  |  Descriptive: {row['Descriptive']:.2f}  |  Total: {row['TotalScore']:.2f}")

# =========================
# RIGHT: GRADING FORM
# =========================
with right:
    st.subheader("Grade this submission")

    responses = row.get("Responses", []) or []
    short_items = [r for r in responses if str(r.get("Type","")).lower() == "short"]

    # MCQ auto-score (from CSV "Correct")
    auto_score, mcq_detail = compute_auto_score(df_csv, responses)

    # Prepare radio bounds for short questions
    short_max = per_question_max_for_short(df_csv)

    existing_short = row.get("ShortMarks", {}) if isinstance(row.get("ShortMarks"), dict) else {}

    if not short_items:
        st.info("No 'Short' questions detected in this submission.")
    else:
        marks_to_save: Dict[str,int] = {}
        for i, item in enumerate(short_items, start=1):
            qid = str(item.get("QuestionID", f"Q{i}")).strip()
            qtext = str(item.get("Question","")).strip()
            ans = str(item.get("Response","")).strip()

            mx = int(short_max.get(qid, 1))
            prev = int(existing_short.get(qid, 0))

            with st.expander(f"{qid} — {qtext}", expanded=True):
                st.markdown("**Student answer:**")
                st.write(ans if ans else "_(no answer)_")
                # radio 0..mx
                r = st.radio(
                    f"Score (0..{mx})",
                    options=list(range(0, mx+1)),
                    index=min(prev, mx),
                    horizontal=True,
                    key=f"radio_{doc_id}_{qid}"
                )
                marks_to_save[qid] = int(r)

        c1, c2, c3 = st.columns([0.3, 0.35, 0.35])
        if c1.button("💾 Save"):
            short_total, total = save_marks(doc_id, marks_to_save, auto_score)
            st.success(f"Saved: Short={short_total}, Auto={auto_score:.2f}, Total={total:.2f}")
            st.cache_data.clear()
            st.experimental_rerun()

        if c2.button("💾 Save & Next Pending"):
            short_total, total = save_marks(doc_id, marks_to_save, auto_score)
            st.success(f"Saved: Short={short_total}, Auto={auto_score:.2f}, Total={total:.2f}")
            # find next pending
            pending_ids = df[df["Evaluated"] != True]["_doc_id"].tolist()
            st.cache_data.clear()
            if pending_ids:
                next_id = pending_ids[0] if pending_ids[0] != doc_id else (pending_ids[1] if len(pending_ids)>1 else pending_ids[0])
                st.experimental_set_query_params(sel=next_id)
            st.experimental_rerun()

        if c3.button("🔄 Recalculate AutoScore only"):
            # just update autoscore (in case CSV changed)
            db.collection("student_responses").document(doc_id).set(
                {"AutoScore": float(auto_score), "TotalScore": float(auto_score) + float(row.get("ShortMarksTotal") or 0)},
                merge=True,
            )
            st.success(f"AutoScore updated to {auto_score:.2f}")
            st.cache_data.clear()
            st.experimental_rerun()

st.divider()

# =========================
# SUMMARY / EXPORT
# =========================
st.subheader("Summary & Export")
df = fetch_submissions("student_responses")
df = df[df["Section"] == section].copy()
df["Evaluated"] = df["Evaluated"].fillna(False)
df["Descriptive"] = df["ShortMarksTotal"].fillna(0.0)
df["AutoScore"] = df["AutoScore"].fillna(0.0)
df["TotalScore"] = df["TotalScore"].fillna(df["Descriptive"] + df["AutoScore"])

summary = df[["Roll","Name","AutoScore","Descriptive","TotalScore","Evaluated","_doc_id"]].sort_values(["Evaluated","Roll"], ascending=[True, True])
st.dataframe(summary, use_container_width=True)

csv_bytes = summary.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download CSV", csv_bytes, file_name=f"{section}_grading_summary.csv", mime="text/csv")
