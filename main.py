import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import os

# -------------------------------
# PAGE CONFIGURATION
# -------------------------------
st.set_page_config(page_title="Student Assessment Portal", layout="centered")
st.title("🎓 Student Assessment Portal")

# -------------------------------
# FIREBASE INITIALIZATION
# -------------------------------
@st.cache_resource
def init_firebase():
    try:
        # --- First try: using Streamlit Cloud secrets ---
        if "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            cred = credentials.Certificate(key_dict)
            database_url = st.secrets["database_url"]
            firebase_admin.initialize_app(cred, {"databaseURL": database_url})
            st.success("✅ Firebase connected successfully (Cloud mode).")
            return True

        # --- Fallback: local file (for local testing) ---
        elif os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
            firebase_admin.initialize_app(cred, {
                "databaseURL": os.getenv("DATABASE_URL", "https://your-local.firebaseio.com")
            })
            st.warning("⚠️ Using local firebase_key.json (development mode).")
            return True

        else:
            st.error("❌ Firebase key not found! Upload it to Streamlit Secrets or place firebase_key.json locally.")
            return False

    except Exception as e:
        st.error(f"❌ Firebase initialization failed: {e}")
        return False


firebase_ready = init_firebase()

# -------------------------------
# STUDENT FORM
# -------------------------------
st.markdown("---")
st.subheader("🧾 Student Login")

# Input fields
name = st.text_input("Enter Your Name (letters only)")
roll = st.text_input("Enter Roll Number (e.g., 25BBAB001)")

# Validation for name (letters + space)
def valid_name(n):
    return all(x.isalpha() or x.isspace() for x in n)

# Submit button
if st.button("Submit Details"):
    if not name or not roll:
        st.warning("⚠️ Please fill in both fields.")
    elif not valid_name(name):
        st.error("❌ Name should contain only letters and spaces.")
    elif not firebase_ready:
        st.error("⚠️ Firebase not connected — please check configuration.")
    else:
        st.success(f"Welcome, {name.title()} ({roll})!")
        try:
            ref = db.reference("/students")
            ref.push({
                "name": name.title(),
                "roll": roll,
                "status": "logged_in"
            })
            st.success("✅ Record saved to Firebase.")
        except Exception as e:
            st.error(f"⚠️ Could not save to Firebase: {e}")

st.markdown("---")
st.info("👉 Please enter your Name and Roll Number to start.")
