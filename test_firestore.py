import firebase_admin
from firebase_admin import credentials, firestore

# Step 1: Load your Firebase service account key
cred = credentials.Certificate("firebase_key.json")

# Step 2: Initialize Firebase app
firebase_admin.initialize_app(cred)

# Step 3: Get Firestore client
db = firestore.client()

# Step 4: Test writing data
data = {
    "Name": "Test User",
    "Roll": "24TEST001",
    "Score": 10,
    "Total": 10
}

# Create or overwrite a document inside 'responses' collection
db.collection("responses").document("24TEST001").set(data)

print("✅ Firestore write successful! Check Firestore → 'responses' collection.")
