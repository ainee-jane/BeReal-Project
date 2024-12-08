import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import pytz

# Flask-App initialisieren
app = Flask(__name__)

# Firebase-Anmeldeinformationen laden
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
if not firebase_credentials:
    raise ValueError("FIREBASE_CREDENTIALS environment variable is not set")
firebase_credentials = json.loads(firebase_credentials)

cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Telegram-Bot-Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

# Start-Handler: Registrierung und Gruppenwahl
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        first_name = update.message.from_user.first_name or "Unbekannt"
        last_name = update.message.from_user.last_name or ""
        username = update.message.from_user.username or ""

        doc_ref = db.collection("chat_ids").document(str(chat_id))

        # Benutzer prüfen
        if doc_ref.get().exists:
            await update.message.reply_text("You are already registered and will receive notifications. Use /new to submit an additional entry.")
            return

        # Benutzer speichern
        doc_ref.set({
            "chat_id": chat_id,
            "name": f"{first_name} {last_name}".strip(),
            "username": username,
            "active_days_list": [],  # Neue Struktur: Liste der aktiven Tage
            "survey_links_sent": [],
        })

        # Nutzer informieren und Gruppe abfragen
        keyboard = [
            [
                InlineKeyboardButton("BeReal User", callback_data="bereal"),
                InlineKeyboardButton("Bystander", callback_data="bystander"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Welcome to the BeReal study! Please select your group:",
            reply_markup=reply_markup,
        )

    except FirebaseError as e:
        await update.message.reply_text("There was an error registering your data. Please try again later.")
        print(f"Firebase error: {e}")

# Callback-Handler für Gruppenauswahl
async def group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    group = query.data  # "bereal" oder "bystander"

    try:
        # Registrierung der Gruppe
        db.collection("chat_ids").document(str(chat_id)).update({
            "group": group
        })

        # Bearbeite die ursprüngliche Nachricht, um die Buttons inaktiv zu machen
        await query.edit_message_reply_markup(reply_markup=None)

        # Nachricht und Buttons je nach Auswahl
        if group == "bereal":
            text = (
                f"✅ **Thank you! You are registered as a BeReal User. Your Participant-ID is: {chat_id} **\n\n"
                "💌 After a BeReal moment, you'll get a survey link with short questions.\n\n"
                "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                "➕ Use /new to submit additional entries when posting a BeLate."
            )
        elif group == "bystander":
            text = (
                f"✅ **Thank you! You are registered as a Bystander. Your Participant-ID is: {chat_id} **\n\n"
                "💌️ After a BeReal moment, you'll get a survey link with short questions.\n\n"
                "🚫 Ignore notifications if you haven't experienced a Bereal moment.\n\n"
                "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                "➕ Use /new to submit additional entries if you experience more BeReal interactions."
            )
        else:
            text = "❌ Invalid group. Please try again with /start."

        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

    except FirebaseError as e:
        await query.message.reply_text("There was an error saving your group. Please try again later.")
        print(f"Firebase error: {e}")

# Flask-Endpoint: Aktive Tage tracken
@app.route("/track_active_day", methods=["GET"])
def track_active_day():
    study_id = request.args.get("STUDY_ID")
    active = request.args.get("active", "false").lower()

    if not study_id:
        return jsonify({"error": "Missing STUDY_ID"}), 400

    # Datum des aktuellen Tages (UTC)
    current_date = datetime.now(pytz.utc).date()

    doc_ref = db.collection("chat_ids").document(study_id)
    doc = doc_ref.get()

    if not doc.exists():
        return jsonify({"error": "Participant not found"}), 404

    user_data = doc.to_dict()
    active_days_list = user_data.get("active_days_list", [])

    if active == "true":
        if str(current_date) not in active_days_list:
            active_days_list.append(str(current_date))
            doc_ref.update({"active_days_list": active_days_list})
            return jsonify({"message": "Active day recorded", "active_days": len(active_days_list)}), 200
        else:
            return jsonify({"message": "Today has already been counted as an active day"}), 200

    return jsonify({"message": "Tracking updated successfully"}), 200

# Handler für zusätzlichen Eintrag (/new)
async def new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    try:
        # Benutzerinformationen aus Firebase abrufen
        user_doc = db.collection("chat_ids").document(str(chat_id)).get()
        if not user_doc.exists:
            await update.message.reply_text("❌ You are not registered. Please start with /start.")
            return

        user_data = user_doc.to_dict()
        group = user_data.get("group", "")

        # Survey-Link basierend auf Gruppe generieren
        if group == "bereal":
            survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_0H4idVDYEQwVX7w?STUDY_ID={chat_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📋 **BeReal User Survey Link**:\n{survey_link}\n\n"
                    f"➕ Use /new to submit additional entries when posting a BeLate."
                ),
                parse_mode="Markdown"
            )
        elif group == "bystander":
            survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_Bystander123?STUDY_ID={chat_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📋 **Bystander Survey Link**:\n{survey_link}\n\n"
                    f"➕ Use /new to submit additional entries if you experience more BeReal interactions."
                ),
                parse_mode="Markdown"
            )

        else:
            await update.message.reply_text("❌ Unknown group. Please contact support.")
    except FirebaseError as e:
        print(f"Firebase error: {e}")
        await update.message.reply_text("There was an error processing your request. Please try again later.")

# Hauptfunktion für Webhooks
def main():
    print("Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler und CallbackQueryHandler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_entry))
    application.add_handler(CallbackQueryHandler(group_selection))

    # Webhook-URL und Server-Details
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL environment variable is not set.")

    # Webhook starten
    try:
        application.run_webhook(
            listen="0.0.0.0",
            port=8443,
            webhook_url=WEBHOOK_URL
        )
        print("Bot is running with Webhooks...")
    except Exception as e:
        print(f"Failed to start the bot: {e}")

if __name__ == "__main__":
    main()
    app.run(host="0.0.0.0", port=5000)  # Flask-Server starten
