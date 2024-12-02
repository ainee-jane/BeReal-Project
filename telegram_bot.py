import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, Filters

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

# Funktion, um die Benutzergruppe in Firebase zu speichern
def save_user_group(chat_id, group):
    doc_ref = db.collection("user_groups").document(str(chat_id))
    doc_ref.set({"chat_id": chat_id, "group": group})

# Variable, um Benutzergruppen zu speichern
user_states = {}

# Begrüßung und erste Frage bei /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_states[chat_id] = "AWAITING_GROUP_SELECTION"

    # Schicke Nachricht mit Auswahl
    keyboard = [["BeReal-User", "Bystander"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Willkommen zur Studie! Bist du ein BeReal-User oder ein Bystander?",
        reply_markup=reply_markup,
    )

# Antwort auf Gruppenwahl verarbeiten
async def handle_group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # Nur antworten, wenn Benutzer sich im richtigen Zustand befindet
    if user_states.get(chat_id) == "AWAITING_GROUP_SELECTION":
        group = update.message.text

        # Überprüfen, ob die Antwort gültig ist
        if group in ["BeReal-User", "Bystander"]:
            save_chat_id(chat_id)  # Chat-ID speichern
            save_user_group(chat_id, group)  # Gruppe speichern
            user_states.pop(chat_id)  # Zustand entfernen

            await update.message.reply_text(
                f"Du bist als {group} registriert. Du erhältst die entsprechenden Nachrichten!"
            )
        else:
            await update.message.reply_text("Bitte wähle entweder 'BeReal-User' oder 'Bystander'.")

# Unbekannte Nachrichten behandeln
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ich habe dich nicht verstanden. Bitte wähle eine der verfügbaren Optionen."
    )

# Hauptfunktion für den Bot
def main():
    print("Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler für /start
    application.add_handler(CommandHandler("start", start))

    # Message-Handler für Gruppenwahl
    application.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_group_selection))

    # Unbekannte Eingaben
    application.add_handler(MessageHandler(Filters.command, handle_unknown))

    # Webhook-URL und Server-Details
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL environment variable is not set.")

    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        webhook_url=WEBHOOK_URL,
    )
    
    print("Bot is running with Webhooks...")

if __name__ == "__main__":
    main()