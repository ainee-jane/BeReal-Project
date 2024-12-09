import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from firebase_admin import credentials, firestore, initialize_app
from firebase_admin.exceptions import FirebaseError

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


# Start-Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        first_name = update.message.from_user.first_name or "Unbekannt"
        last_name = update.message.from_user.last_name or ""
        username = update.message.from_user.username or ""

        doc_ref = db.collection("chat_ids").document(str(chat_id))

        if doc_ref.get().exists:
            await update.message.reply_text("You are already registered and will receive notifications. Use /new to submit additional entries.")
            return

        doc_ref.set({
            "chat_id": chat_id,
            "name": f"{first_name} {last_name}".strip(),
            "username": username,
            "active_days_list": [],
            "survey_links_sent": [],
        })

        keyboard = [
            [InlineKeyboardButton("BeReal User", callback_data="bereal"),
             InlineKeyboardButton("Bystander", callback_data="bystander")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Welcome to the BeReal study! Please select your group:", reply_markup=reply_markup)

    except FirebaseError as e:
        await update.message.reply_text("Error registering your data. Please try again later.")
        print(f"Firebase error: {e}")


# Callback-Handler für Gruppenauswahl
async def group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    group = query.data  # "bereal" oder "bystander"

    try:
        # Registrierung der Gruppe
        db.collection("chat_ids").document(str(chat_id)).update({"group": group})

        # Bearbeite die ursprüngliche Nachricht, um die Buttons inaktiv zu machen
        await query.edit_message_reply_markup(reply_markup=None)

        # Nachricht und Buttons je nach Auswahl
        if group == "bereal":
            text = (
                f"✅ Thank you! You are registered as a BeReal User. Your Participant-ID is: {chat_id} \n\n"
                f"💡 Please answer a few initial questions: https://migroup.qualtrics.com/jfe/form/SV_0wk9mk29bMFlI6G \n\n"
                "💌 After a BeReal moment, you'll get a survey link with short questions.\n\n"
                "📅 Participation ends after 14 active days. A day is 'active' if at least one relevant interaction is reported.\n\n"
                "➕ Use /new to submit additional entries when posting a BeLate."
            )
        elif group == "bystander":
            text = (
                f"✅ Thank you! You are registered as a Bystander. Your Participant-ID is: {chat_id} \n\n"
                f"💡 Please answer a few initial questions: https://migroup.qualtrics.com/jfe/form/SV_0wk9mk29bMFlI6G \n\n"
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

# Command-Handler für neuen Eintrag (/new)
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
                    f"📋 BeReal User Survey Link**:\n{survey_link}\n\n"
                    f"➕ Use /new to submit additional entries when posting a BeLate."
                ),
              
            )
        elif group == "bystander":
            survey_link = f"https://migroup.qualtrics.com/jfe/form/SV_42WjqWWGJnMkj5Q?STUDY_ID={chat_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📋 Bystander Survey Link**:\n{survey_link}\n\n"
                    f"➕ Use /new to submit additional entries if you experience more BeReal interactions."
                ),
             
            )
        else:
            await update.message.reply_text("❌ Unknown group. Please contact support.")
    except FirebaseError as e:
        print(f"Firebase error: {e}")
        await update.message.reply_text("There was an error processing your request. Please try again later.")

def main():
    print("Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_entry))
    application.add_handler(CallbackQueryHandler(group_selection))

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
