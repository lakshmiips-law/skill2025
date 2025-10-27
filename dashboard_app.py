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

@st.cache_resource
def init_firebase():
    try:
        # Check if already initialized
        if firebase_admin._apps:
            return firestore.client()
        
        # Use secrets - no file dependency
        if 'FIREBASE_KEY' in st.secrets:
            # Get the secret (it might be already parsed or as string)
            firebase_config = st.secrets['FIREBASE_KEY']
            
            # If it's a string, parse it as JSON
            if isinstance(firebase_config, str):
                firebase_config = json.loads(firebase_config)
            
            # Create credentials from the config dict
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        else:
            st.error("Firebase configuration not found in secrets!")
            return None
            
    except Exception as e:
        st.error(f"Firebase initialization failed: {str(e)}")
        return None

# Initialize Firebase
db = init_firebase()

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
