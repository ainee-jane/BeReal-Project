import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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

# Funktion zum Speichern der Chat-ID in Firestore
def save_chat_id(chat_id):
    doc_ref = db.collection("chat_ids").document(str(chat_id))
    doc_ref.set({"chat_id": chat_id})

# Begrüßung und Registrierung bei /start

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        first_name = update.message.from_user.first_name or "Unbekannt"
        last_name = update.message.from_user.last_name or ""
        username = update.message.from_user.username or ""

        doc_ref = db.collection("bereal_users").document(str(chat_id))

        if doc_ref.get().exists:
            await update.message.reply_text(f"You are already registered and will receive notifications.")
            return

        doc_ref.set({
            "chat_id": chat_id,
            "name": f"{first_name} {last_name}".strip(),
            "username": username,
            "active_days": 0,
            "survey_links_sent": []
        })

        await update.message.reply_text("Welcome to the study! You are registered and will receive notifications.")
    except FirebaseError as e:
        await update.message.reply_text("There was an error registering your data. Please try again later.")
        print(f"Firebase error: {e}")


# Nachricht an alle Chat-IDs senden
async def send_message_to_all(context: ContextTypes.DEFAULT_TYPE, message: str):
    docs = db.collection("chat_ids").stream()
    for doc in docs:
        chat_id = doc.to_dict().get("chat_id")
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text=message)

# Hauptfunktion für Webhooks
def main():
    print("Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler hinzufügen
    application.add_handler(CommandHandler("start", start))

    # Webhook-URL und Server-Details
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Beispiel: "https://<your-app-url>"
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL environment variable is not set.")

    # Webhook starten
    application.run_webhook(
        listen="0.0.0.0",  # Lauscht auf alle IPs
        port=8443,        # Standardport für Telegram-Webhooks
        webhook_url=WEBHOOK_URL  # Die vollständige URL deines Bots
    )
    print("Bot is running with Webhooks...")

if __name__ == "__main__":
    main()
