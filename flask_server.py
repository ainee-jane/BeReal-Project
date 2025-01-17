import os
import json
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import pytz
import requests

app = Flask(__name__)

# Firebase initialisieren
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
if not firebase_credentials:
    raise ValueError("FIREBASE_CREDENTIALS environment variable is not set")

firebase_credentials = json.loads(firebase_credentials)
cred = credentials.Certificate(firebase_credentials)
initialize_app(cred)
db = firestore.client()

# Telegram-Bot-Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


# Endpoint to track if the initial survey has been completed.
@app.route("/track_initial_survey", methods=["GET"])
def track_initial_survey():
    try:
        # STUDY_ID aus den Query-Parametern abrufen
        study_id = request.args.get("STUDY_ID")
        completed = request.args.get("completed", "false").lower() == "true"

        if not study_id or not study_id.isdigit():
            return jsonify({"error": "Invalid or missing STUDY_ID"}), 400

        # Fetch Firebase document for the given STUDY_ID
        doc_ref = db.collection("chat_ids").document(study_id)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({"error": "Participant not found"}), 404

        # Update initial survey status in Firebase
        doc_ref.update({"initial_survey_completed": completed})

        # Notify user via Telegram if survey is completed
        if completed:
            user_data = doc.to_dict()
            chat_id = study_id
            group = user_data.get("group", "")

            if group == "bereal":
                message = (
                    "✅ Thank you for completing the onboarding survey!\n\n"
                    "💌 After a BeReal moment, you'll get a survey link with short questions.\n\n"
                    "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                    "➕ Use /new to submit additional entries when posting a BeLate."
                )
            elif group == "bystander":
                message = (
                    "✅ Thank you for completing the onboarding survey!\n\n"
                    "💌️ After a BeReal moment, you'll get a survey link with short questions.\n\n"
                    "🚫 Ignore notifications if you haven't experienced a Bereal moment.\n\n"
                    "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                    "➕ Use /new to submit additional entries if you experience more BeReal interactions."
                )
            else:
                message = (
                    "✅ Thank you for completing the onboarding survey!\n\n"
                    "💡 If you have any questions, feel free to contact the study administrator."
                )

            # Telegram-API verwenden, um Nachricht zu senden
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"  # Falls erforderlich, kann Markdown deaktiviert werden
            }

            response = requests.post(TELEGRAM_API_URL, json=payload)
            if response.status_code != 200:
                print(f"Error sending Telegram message: {response.json()}")

        return jsonify({"message": "Initial survey status updated", "STUDY_ID": study_id, "completed": completed}), 200

    except Exception as e:
        print(f"Error in track_initial_survey: {e}")
        return jsonify({"error": "Failed to update survey status"}), 500

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
                # Firebase-Dokument aktualisieren
                doc_ref.update({"active_days_list": active_days_list})

                # Anzahl der aktiven Tage berechnen
                active_days_count = len(active_days_list)

                # Nachricht nach 7 oder 14 aktiven Tagen senden
                if active_days_count == 7 or active_days_count == 14:
                    send_active_days_notification(chat_id, active_days_count)

                return jsonify({"message": "Active day recorded", "active_days": active_days_count}), 200
            except Exception as e:
                print(f"Update error: {e}")
                return jsonify({"error": "Failed to update active_days_list"}), 500
        else:
            return jsonify({"message": "Today has already been counted as an active day"}), 200

    return jsonify({"message": "Tracking updated successfully", "STUDY_ID": study_id, "active": active}), 200


def send_active_days_notification(chat_id, active_days_count):
    """Send a Telegram notification to the user after 7 or 14 active days."""
    try:
        if active_days_count == 7:
            message = (
                f"🎉 Congratulations, you have achieved {active_days_count} active days so far!\n"
                f"💪 Keep it up, you're halfway there! \n\n"
            )
        if active_days_count == 14:
            # Nachricht für den 14. Tag mit Survey-Link und Doodle-Kalender
            final_survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_6lDaOQOPufoJJPM?STUDY_ID={chat_id}"
            doodle_link = "https://doodle.com/schedule-your-interview"

            message = (
                f"🎉 Congratulations! You have reached 14 active days in the study. This marks the end of your participation!\n\n"
                f"✅ Please complete the final survey: {final_survey_link}\n\n"
                f"🗓️ After completing the survey, please use this link to schedule an interview: {doodle_link}"
            )

        # Telegram-API verwenden, um Nachricht zu senden
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(TELEGRAM_API_URL, json=payload)
        if response.status_code != 200:
            print(f"Error sending Telegram message: {response.json()}")

    except Exception as e:
        print(f"Error in send_active_days_notification: {e}")


# Update questions answered
@app.route("/update_questions", methods=["POST"])
def update_questions():
    try:
        # STUDY_ID und QUESTIONS aus den Query-Parametern abrufen
        study_id = request.args.get("STUDY_ID")
        questions = request.args.get("QUESTIONS")

        # Debug-Ausgabe
        print(f"Received STUDY_ID: {study_id}")
        print(f"Received QUESTIONS: {questions}")

        # Validierung der Parameter
        if not study_id or not questions:
            print("Error: Missing STUDY_ID or QUESTIONS")
            return jsonify({"error": "Missing STUDY_ID or QUESTIONS"}), 400

        # Logik zur Verarbeitung (z. B. Firebase-Update)
        # Überprüfen, ob Firebase korrekt arbeitet
        db = firestore.client()
        doc_ref = db.collection("chat_ids").document(study_id)

        # Dokument abrufen und prüfen, ob es existiert
        doc = doc_ref.get()
        if not doc.exists:
            print(f"Error: Document with STUDY_ID {study_id} not found")
            return jsonify({"error": "Document not found"}), 404

        # Fragen aktualisieren
        questions_answered = doc.to_dict().get("questions_answered", {})
        for question in questions.split(","):
            questions_answered[question] = questions_answered.get(question, 0) + 1

        # Firebase aktualisieren
        doc_ref.update({"questions_answered": questions_answered})
        print(f"Updated questions_answered for {study_id}: {questions_answered}")

        # Erfolgreiche Antwort
        return jsonify({"message": "Update successful"}), 200

    except Exception as e:
        # Fehler protokollieren
        print(f"Error in /update_questions: {e}")
        return jsonify({"error": "Internal server error"}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
