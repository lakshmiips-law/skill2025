import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json

# Remove Streamlit branding first
st.set_page_config(
    page_title="Student Dashboard",
    layout="wide",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display:none;}
[data-testid="stHeader"] {display:none;}
[data-testid="stToolbar"] {display:none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ---------------- FIREBASE INIT (drop-in) ----------------
def init_firestore():
    """Initialize Firebase from Streamlit secrets (supports [firebase_key] or [firebase]).
    Falls back to local firebase_key.json if present."""
    if firebase_admin._apps:
        return firestore.client()

    cfg = None
    try:
        raw = st.secrets.get("firebase_key", None)
        if raw is None:
            raw = st.secrets.get("firebase", None)

        if raw is not None:
            # st.secrets returns a Mapping (TOML table) or str (JSON) depending on how you saved it
            cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        cfg = None

    if cfg:
        cred = credentials.Certificate(cfg)
        firebase_admin.initialize_app(cred)
        return firestore.client()

    # Local fallback for development
    import os
    if os.path.exists("firebase_key.json"):
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
        return firestore.client()

    st.error("Firebase configuration not found in secrets or local file.")
    st.stop()

# Call it BEFORE any Firestore usage
db = init_firestore()
st.success(f"Connected to Firestore project: {firebase_admin.get_app().project_id}")


if db:
    st.success("✅ Firebase connected successfully via Secrets!")
    
    # Test the connection
    try:
        # Try to read a document to verify connection
        test_ref = db.collection('users').limit(1)
        docs = test_ref.stream()
        st.success("✅ Firebase Firestore connection verified!")
    except Exception as e:
        st.warning(f"⚠️ Connected but test query failed: {e}")
    
    # Your actual app code continues here...
    st.title("Student Skill Training Dashboard")
    # ... rest of your dashboard code ...
    
else:
    st.error("❌ Firebase connection failed!")
    st.stop()

