import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, filters, MessageHandler

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
            await update.message.reply_text("You are already registered and will receive notifications.")
            return

        # Benutzer speichern
        doc_ref.set({
            "chat_id": chat_id,
            "name": f"{first_name} {last_name}".strip(),
            "username": username,
            "active_days": 0,
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
            f"Hi {first_name}, welcome to the study! Please select your group:",
            reply_markup=reply_markup,
        )

    except FirebaseError as e:
        await update.message.reply_text("There was an error registering your data. Please try again later.")
        print(f"Firebase error: {e}")

# Callback-Handler für Gruppenwahl
async def group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    group = query.data  # "bereal" oder "bystander"

    # Firebase aktualisieren
    try:
        db.collection("chat_ids").document(str(chat_id)).update({
            "group": group
        })
        await query.edit_message_text(
            f"Thank you! You have been registered as a {group.capitalize()}. You will receive notifications soon!"
        )
    except FirebaseError as e:
        await query.edit_message_text("There was an error saving your group. Please try again later.")
        print(f"Firebase error: {e}")

# Handler für ungültige Eingaben
async def invalid_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Invalid input! Please use the buttons or commands to interact with the bot."
    )

# Hauptfunktion für Webhooks
def main():
    print("Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Command-Handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(group_selection))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_message))

    # Global Error-Handler 
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Fehler global behandeln und loggen."""
        try:
            raise context.error
        except Exception as e:
            print(f"Error: {e}")

    application.add_error_handler(error_handler)

    # Webhook-URL und Server-Details
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Beispiel: "https://<your-app-url>"
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL environment variable is not set.")

    # Webhook starten
    try:
        application.run_webhook(
            listen="0.0.0.0",  # Lauscht auf alle IPs
            port=8443,        # Standardport für Telegram-Webhooks
            webhook_url=WEBHOOK_URL  # Die vollständige URL deines Bots
        )
        print("Bot is running with Webhooks...")
    except Exception as e:
        print(f"Failed to start the bot: {e}")

if __name__ == "__main__":
    main()
