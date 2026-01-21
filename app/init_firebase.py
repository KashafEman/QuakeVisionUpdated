import firebase_admin
from firebase_admin import credentials, firestore

db = None

def init_firebase():
    global db
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-service-account.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db  
