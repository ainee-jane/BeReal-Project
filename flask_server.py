import os
import json
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import pytz

app = Flask(__name__)

# Firebase initialisieren
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
if not firebase_credentials:
    raise ValueError("FIREBASE_CREDENTIALS environment variable is not set")

firebase_credentials = json.loads(firebase_credentials)
cred = credentials.Certificate(firebase_credentials)
initialize_app(cred)
db = firestore.client()


# Flask-Endpoint: Aktive Tage tracken
@app.route("/track_active_day", methods=["GET"])
def track_active_day():
    print(f"Incoming request: {request.args}")  # Loggt alle URL-Parameter
   
    # STUDY_ID aus der URL abrufen
    study_id = request.args.get("STUDY_ID")
    active = request.args.get("active", "false").lower()

    # Validierung von STUDY_ID
    if not study_id or not study_id.isdigit():
        return jsonify({"error": "Invalid or missing STUDY_ID"}), 400

    # STUDY_ID als chat_id verwenden
    chat_id = study_id

    # Datum des aktuellen Tages (UTC)
    current_date = datetime.now(pytz.utc).date()

    # Firebase-Dokument abrufen
    doc_ref = db.collection("chat_ids").document(chat_id)
    doc = doc_ref.get()

    if not doc.exists:
        return jsonify({"error": "Participant not found"}), 404

    # Daten aus dem Dokument abrufen
    user_data = doc.to_dict()
    active_days_list = user_data.get("active_days_list", [])

    # Aktive Tage aktualisieren
    if active == "true":
        if str(current_date) not in active_days_list:
            active_days_list.append(str(current_date))
            try:
                doc_ref.update({"active_days_list": active_days_list})
                return jsonify({"message": "Active day recorded", "active_days": len(active_days_list)}), 200
            except Exception as e:
                print(f"Update error: {e}")
                return jsonify({"error": "Failed to update active_days_list"}), 500
        else:
            return jsonify({"message": "Today has already been counted as an active day"}), 200

    return jsonify({"message": "Tracking updated successfully", "STUDY_ID": study_id, "active": active}), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


