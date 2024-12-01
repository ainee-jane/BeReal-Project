import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Lade Firebase-Anmeldeinformationen aus Umgebungsvariablen
firebase_credentials = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)

# Telegram-Bot-Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Chat-ID in Firestore speichern
def save_chat_id(chat_id):
    doc_ref = db.collection("chat_ids").document(str(chat_id))
    doc_ref.set({"chat_id": chat_id})

# Begrüßung und Registrierung bei /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    save_chat_id(chat_id)
    await update.message.reply_text("Willkommen zur Studie! Du bist registriert und erhältst Benachrichtigungen.")

# Nachricht an alle Chat-IDs senden
async def send_message_to_all(context: ContextTypes.DEFAULT_TYPE, message: str):
    docs = db.collection("chat_ids").stream()
    for doc in docs:
        chat_id = doc.to_dict().get("chat_id")
        if chat_id:
            await context.bot.send_message(chat_id=chat_id, text=message)

# Hauptfunktion
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler hinzufügen
    application.add_handler(CommandHandler("start", start))

    # Bot starten
    application.run_polling()

if __name__ == "__main__":
    main()
