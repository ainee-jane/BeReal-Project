import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from datetime import datetime
import pytz
from threading import Thread

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

# Telegram-Bot-Token laden
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")
bot = Bot(token=BOT_TOKEN)

# Zeitzone festlegen (z. B. UTC)
TIMEZONE = pytz.utc

# Start-Handler: Registrierung und Gruppenauswahl
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = str(update.message.chat_id)
        first_name = update.message.from_user.first_name or "Unbekannt"
        last_name = update.message.from_user.last_name or ""
        username = update.message.from_user.username or ""

        doc_ref = db.collection("chat_ids").document(chat_id)

        # Prüfen, ob der Benutzer bereits registriert ist
        if doc_ref.get().exists:
            await update.message.reply_text(
                "✅ You are already registered. Use /new to submit an additional entry."
            )
            return

        # Benutzerinformationen speichern
        doc_ref.set({
            "chat_id": chat_id,
            "name": f"{first_name} {last_name}".strip(),
            "username": username,
            "group": None,
            "active_days_list": [],
            "survey_links_sent": [],
        })

        # Gruppenauswahl senden
        keyboard = [
            [InlineKeyboardButton("BeReal User", callback_data="bereal"),
             InlineKeyboardButton("Bystander", callback_data="bystander")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Welcome to the BeReal study! Please select your group:",
            reply_markup=reply_markup,
        )
    except Exception as e:
        print(f"Error in start handler: {e}")
        await update.message.reply_text(
            "❌ An error occurred during registration. Please try again later."
        )

# Gruppenauswahl-Handler
async def group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat.id)
    group = query.data  # "bereal" oder "bystander"

    try:
        # Gruppe in Firebase aktualisieren
        db.collection("chat_ids").document(chat_id).update({"group": group})

        # Buttons entfernen
        await query.edit_message_reply_markup(reply_markup=None)

        # Nachricht basierend auf der Gruppe senden
        if group == "bereal":
            message = (
                f"✅ **You are registered as a BeReal User.**\n\n"
                "💌 You'll receive a survey link after each BeReal moment.\n"
                "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                "➕ Use /new to submit additional entries."
            )
        elif group == "bystander":
            message = (
                f"✅ **You are registered as a Bystander.**\n\n"
                "💌 You'll receive a survey link after a BeReal moment.\n"
                "🚫 Ignore notifications if no BeReal moments occur.\n\n"
                "📅 Participation ends after 14 active days.\n"
                "➕ Use /new to submit additional entries."
            )
        else:
            message = "❌ Invalid group. Please restart with /start."

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    except Exception as e:
        print(f"Error in group_selection handler: {e}")
        await query.message.reply_text("❌ An error occurred. Please try again later.")

# Handler für zusätzlichen Eintrag (/new)
async def new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)

    try:
        # Benutzerinformationen aus Firebase abrufen
        doc_ref = db.collection("chat_ids").document(chat_id)
        user_doc = doc_ref.get()

        if not user_doc.exists:
            await update.message.reply_text("❌ You are not registered. Please start with /start.")
            return

        user_data = user_doc.to_dict()
        group = user_data.get("group", "")

        # Survey-Link generieren
        if group == "bereal":
            survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_0H4idVDYEQwVX7w?STUDY_ID={chat_id}"
            message = (
                f"📋 **BeReal User Survey Link**:\n{survey_link}\n\n"
                "➕ Use /new to submit additional entries."
            )
        elif group == "bystander":
            survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_Bystander123?STUDY_ID={chat_id}"
            message = (
                f"📋 **Bystander Survey Link**:\n{survey_link}\n\n"
                "➕ Use /new to submit additional entries."
            )
        else:
            message = "❌ Unknown group. Please contact support."

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    except Exception as e:
        print(f"Error in new_entry handler: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

# Flask-Handler für aktive Tage
@app.route("/track_active_day", methods=["GET"])
def track_active_day():
    study_id = request.args.get("STUDY_ID")
    active = request.args.get("active")

    if not study_id or active is None:
        return jsonify({"error": "Missing STUDY_ID or active parameter"}), 400

    try:
        # Firebase-Dokument abrufen
        doc_ref = db.collection("chat_ids").document(study_id)
        doc = doc_ref.get()

        if not doc.exists():
            return jsonify({"error": "Participant not found"}), 404

        user_data = doc.to_dict()
        current_date = datetime.now(TIMEZONE).date()

        # Aktive Tage aktualisieren
        active_days_list = user_data.get("active_days_list", [])
        if active.lower() == "true" and str(current_date) not in active_days_list:
            active_days_list.append(str(current_date))
            doc_ref.update({"active_days_list": active_days_list})
            bot.send_message(
                chat_id=study_id,
                text=f"✅ Thank you! Today is marked as active. Total active days: {len(active_days_list)}."
            )
        elif active.lower() == "true":
            bot.send_message(
                chat_id=study_id,
                text="✅ Thank you! Today has already been counted as an active day."
            )
        else:
            bot.send_message(
                chat_id=study_id,
                text="⚠️ Your response was recorded, but today does not count as an active day."
            )
        return jsonify({"message": "Tracking updated successfully"}), 200
    except Exception as e:
        print(f"Error in track_active_day: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

# Hauptfunktion: Telegram-Bot und Flask zusammenführen
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_entry))
    application.add_handler(CallbackQueryHandler(group_selection))

    # Flask parallel ausführen
    def run_flask():
        app.run(host="0.0.0.0", port=5000)

    Thread(target=run_flask).start()

    # Telegram-Bot starten
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
