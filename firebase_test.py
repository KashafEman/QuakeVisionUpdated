from app.init_firebase import db  # now works

try:
    doc_ref = db.collection("test").add({"status": "Firebase test!"})
    print("Success! Doc ID:", doc_ref[1].id)
except Exception as e:
    print("Error:", e)
