import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import time
import json
import re
import os

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="SKILL - 2025", layout="wide")
st.title("🧠 SKILL - 2025")

# ---------------- FIREBASE CONNECTION ----------------
@st.cache_resource
def init_firebase():
    """
    Initializes Firebase for Streamlit Cloud (via st.secrets)
    or local development (via firebase_key.json).
    Returns Firestore client if successful.
    """
    try:
        if not firebase_admin._apps:
            # ✅ Case 1: Streamlit Cloud (using secrets)
            if "firebase_key" in st.secrets:
                key_dict = json.loads(st.secrets["firebase_key"])
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred, {
                    "projectId": key_dict.get("project_id"),
                    "databaseURL": st.secrets.get("database_url", f"https://{key_dict.get('project_id')}.firebaseio.com")
                })
                st.success("✅ Firebase connected using Streamlit Cloud Secrets.")

            # ✅ Case 2: Local JSON file (dev mode)
            elif os.path.exists("firebase_key.json"):
                with open("firebase_key.json", "r", encoding="utf-8") as f:
                    key_dict = json.load(f)
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred, {
                    "projectId": key_dict.get("project_id"),
                    "databaseURL": f"https://{key_dict.get('project_id')}.firebaseio.com"
                })
                st.warning("⚠️ Using local firebase_key.json (development mode).")

            else:
                st.error("❌ Firebase key not found. Add it to Streamlit Secrets or place firebase_key.json locally.")
                return None

        return firestore.client()

    except Exception as e:
        st.error(f"❌ Firebase initialization failed: {e}")
        return None


# Initialize Firestore
db = init_firebase()

# ---------------- CSV FILES ----------------
files = {
    "Aptitude Test": "aptitude.csv",
    "Adaptability & Learning": "adaptability_learning.csv",
    "Communication Skills - Objective": "communication_skills_objective.csv",
    "Communication Skills - Descriptive": "communication_skills_descriptive.csv",
}

# ---------------- INPUTS ----------------
name = st.text_input("Enter Your Name (letters only)", value="")
roll = st.text_input("Enter Roll Number (e.g., 25BBAB001)", value="")

# ---------------- VALIDATION ----------------
def valid_name(n: str) -> bool:
    if not isinstance(n, str):
        return False
    n = n.strip()
    if not n:
        return False
    return bool(re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", n))

name_ok = valid_name(name)

if name and not name_ok:
    st.error("Name should contain only letters and spaces (e.g., 'Ravi Kumar').")

clean_name = " ".join(part.capitalize() for part in name.split()) if name_ok else name

# ---------------- MAIN APP ----------------
if name and roll:
    st.success(f"Welcome, {clean_name}! Please choose a test section below 👇")
    section = st.selectbox("Select Section", list(files.keys()))

    if section == "Communication Skills - Descriptive":
        st.info("📝 Q1 to Q10 - Find the error and correct the sentence.")

    if section:
        try:
            df = pd.read_csv(files[section])
        except FileNotFoundError:
            st.error(f"❌ File '{files[section]}' not found.")
            st.stop()

        st.subheader(f"📘 {section}")
        st.write("Answer all the questions below and click **Submit** when done.")

        responses = []

        for idx, row in df.iterrows():
            qid = row.get("QuestionID", f"Q{idx+1}")
            qtext = str(row.get("Question", "")).strip()
            qtype = str(row.get("Type", "")).strip().lower()

            # Instructional text
            if qtype == "info":
                st.markdown(f"### 📝 {qtext}")
                st.markdown("---")
                continue

            st.markdown(f"**Q{idx+1}. {qtext}**")

            # Likert scale
            if qtype == "likert":
                scale_min = int(row.get("ScaleMin", 1))
                scale_max = int(row.get("ScaleMax", 5))
                response = st.slider(
                    "Your Response:",
                    min_value=scale_min,
                    max_value=scale_max,
                    value=(scale_min + scale_max) // 2,
                    key=f"q{idx}_{section}"
                )

            # Multiple Choice
            elif qtype == "mcq":
                options = [
                    str(row.get(f"Option{i}", "")).strip()
                    for i in range(1, 5)
                    if pd.notna(row.get(f"Option{i}")) and str(row.get(f"Option{i}")).strip() != ""
                ]
                response = st.radio("Your Answer:", options, key=f"q{idx}_{section}") if options else ""
                if not options:
                    st.warning(f"No options available for {qid}")

            # Short/Descriptive
            elif qtype == "short":
                response = st.text_area("Your Answer:", key=f"q{idx}_{section}")

            # Unknown type
            else:
                st.info(f"⚠️ Unknown question type '{qtype}' for {qid}.")
                response = ""

            responses.append({
                "QuestionID": qid,
                "Question": qtext,
                "Response": response,
                "Type": qtype,
            })
            st.markdown("---")

        # ---------------- SUBMIT ----------------
        if st.button("✅ Submit"):
            if not db:
                st.error("❌ Database connection failed. Cannot save responses.")
            else:
                with st.spinner("Saving your responses..."):
                    data = {
                        "Name": clean_name,
                        "Roll": roll.upper(),
                        "Section": section,
                        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Responses": responses,
                    }
                    try:
                        # Unique doc ID per Roll + Section
                        doc_ref = db.collection("student_responses").document(
                            f"{roll.upper()}_{section.replace(' ', '_')}"
                        )
                        doc_ref.set(data, merge=True)
                        st.success("✅ Your responses have been successfully submitted (or updated)!")
                    except Exception as e:
                        st.error(f"❌ Error saving to Firestore: {e}")

    st.markdown(
        "<p style='color:#007BFF; font-weight:600;'>⌨️ Press <b>Home</b> to return to the top of the page.</p>",
        unsafe_allow_html=True,
    )

else:
    st.info("👆 Please enter your Name and Roll Number to start.")

# ---------------- STYLING ----------------
st.markdown("""
<style>
div.block-container {
    padding-top: 2.0rem;
    padding-bottom: 1.5rem;
}
h1, .stTitle {
    margin-top: -0.2rem;
}
</style>
""", unsafe_allow_html=True)
