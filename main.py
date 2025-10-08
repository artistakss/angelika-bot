import os
import logging
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -------------------- CONFIG --------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Render automatically provides this port
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = f"https://angelika-bot.onrender.com/{TOKEN}"

# -------------------- LOGGING --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("angelika-bot")

# -------------------- INIT CLIENTS --------------------
client = OpenAI(api_key=OPENAI_API_KEY)

gc = None
try:
    import json
    creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc = gspread.authorize(creds)
    logger.info("✅ Google Sheets connected successfully.")
except Exception as e:
    logger.error(f"❌ Google Sheets error: {e}")

# -------------------- FLASK SETUP --------------------
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "🤖 Angelika bot is running!", 200

# -------------------- TELEGRAM HANDLERS --------------------
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("📅 Записаться на сессию", callback_data="session")],
        [InlineKeyboardButton("📤 Отправить чек", callback_data="check")],
        [InlineKeyboardButton("💳 Реквизиты для оплаты", callback_data="requisites")],
        [InlineKeyboardButton("📘 FAQ", callback_data="faq")],
        [InlineKeyboardButton("🔓 Проверить доступ к RESONANCE", callback_data="access")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "✨ Привет! Я нейро-ассистент Анжелики.\n\n"
        "Я помогу тебе:\n"
        "🔹 Войти в сообщество RESONANCE\n"
        "🔹 Узнать реквизиты для оплаты\n"
        "🔹 Проверить доступ\n"
        "🔹 Записаться на сессию\n\n"
        "Выбери действие ниже 👇"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_buttons(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "faq":
        text = "FAQ:\n- Текущая цена: 11 111 ₸\n- Доступ на 30 дней\n- После оплаты пришлите чек."
    elif query.data == "requisites":
        text = (
            "💳 Реквизиты для оплаты:\n\n"
            "Kaspi: https://pay.kaspi.kz/pay/ymwm8kds\n"
            "Halyk Bank: 4405 6397 3973 4828\n"
            "Tinkoff: 2200 7008 3889 3427\n"
            "USDT (TRC20): TLhAz9G84nAdMvJtb7NoZRqCXfekDxj5rN\n\n"
            "После оплаты нажмите '📤 Отправить чек'."
        )
    elif query.data == "session":
        text = (
            "📅 Для записи на сессию пришлите, пожалуйста:\n"
            "- Формат: онлайн или оффлайн\n"
            "- Желаемую дату и время\n"
            "- Примерный запрос или тему встречи\n\n"
            "Эти данные будут переданы Анжелике ❤️"
        )
    elif query.data == "check":
        text = "📤 Отправьте фото или файл с чеком, чтобы подтвердить оплату."
    elif query.data == "access":
        text = (
            "🔓 Проверка доступа к RESONANCE:\n"
            "Пожалуйста, отправьте свой email или имя в Telegram, "
            "на которое оформлялась подписка."
        )
    else:
        text = "Неизвестная команда."

    await query.edit_message_text(text)

async def handle_message(update: Update, context):
    user_text = update.message.text or ""

    # Попытка ответа через OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты — помощник Анжелики, объясняй спокойно и коротко."},
                {"role": "user", "content": user_text},
            ]
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        await update.message.reply_text("⚠️ Ошибка при обращении к AI. Попробуйте позже.")

async def handle_photo(update: Update, context):
    try:
        file = await update.message.photo[-1].get_file()
        file_url = file.file_path
        user = update.message.from_user

        if gc:
            sh = gc.open("AngelikaBot").sheet1
            sh.append_row([str(user.id), user.username or "", file_url, "Чек загружен"])
            await update.message.reply_text("✅ Чек получен и сохранён. Проверим оплату.")
        else:
            await update.message.reply_text("⚠️ Ошибка Google Sheets. Чек не записан.")
    except Exception as e:
        logger.error(f"Ошибка при записи чека: {e}")
        await update.message.reply_text("❌ Ошибка записи чека.")

# -------------------- START APP --------------------
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_buttons))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

if __name__ == "__main__":
    logger.info("🚀 Bot starting via webhook...")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL,
    )
