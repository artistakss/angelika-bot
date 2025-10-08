import os
import logging
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build


# === Настройка логов ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("angelika-bot")

# === Загрузка переменных окружения ===
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# === Настройка OpenAI ===
openai.api_key = OPENAI_API_KEY

# === Настройка Flask (для Render) ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Angelika Bot is running!"

# === Клавиатура ===
MAIN_MENU = [
    [KeyboardButton("💫 FAQ"), KeyboardButton("💰 Реквизиты для оплаты")],
    [KeyboardButton("📤 Отправить чек"), KeyboardButton("📅 Записаться на сессию")],
    [KeyboardButton("🔓 Проверить доступ к RESONANCE")]
]
MARKUP = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

# === Google Sheets ===
def get_sheets_service():
    creds_dict = eval(GOOGLE_CREDS_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def add_to_sheet(data):
    try:
        service = get_sheets_service()
        sheet = service.spreadsheets()
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="A:E",
            valueInputOption="RAW",
            body={"values": [data]},
        ).execute()
        logger.info("✅ Записано в Google Sheets: %s", data)
    except Exception as e:
        logger.error("Ошибка записи в Google Sheets: %s", e)


# === OpenAI-ответ ===
async def ask_ai(question: str) -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Ты помощник Анжелики в сфере духовных практик, эзотерики и саморазвития."},
                      {"role": "user", "content": question}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "⚠️ Ошибка при обращении к AI."


# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Привет! Я нейро-ассистент Анжелики.\n\n"
        "Я помогу тебе:\n"
        "🔹 Узнать реквизиты для оплаты\n"
        "🔹 Проверить доступ к RESONANCE\n"
        "🔹 Записаться на сессию\n"
        "🔹 Отправить чек\n\n"
        "Выбери действие ниже 👇",
        reply_markup=MARKUP
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "💫 FAQ":
        await update.message.reply_text(
            "FAQ:\n- Текущая цена: 11111 ₸\n- Доступ на 30 дней\n- После оплаты пришлите чек."
        )

    elif text == "💰 Реквизиты для оплаты":
        await update.message.reply_text(
            "Реквизиты для оплаты:\n\n"
            "Kaspi: https://pay.kaspi.kz/pay/ymwm8kds\n"
            "Halyk Bank: 4405 6397 3973 4828\n"
            "Tinkoff: 2200 7008 3889 3427\n"
            "USDT (TRC20): TLhAz9G84nAdMvJtb7NoZRqCXfekDxj5rN\n\n"
            "После оплаты нажмите '📤 Отправить чек'."
        )

    elif text == "📅 Записаться на сессию":
        await update.message.reply_text(
            "🧘‍♀️ Для записи на сессию, пожалуйста, укажите:\n"
            "- Формат: онлайн или офлайн\n"
            "- Желаемую дату и время\n"
            "- Примерный запрос (вопрос или тема)\n\n"
            "После этого я передам данные Анжелике 💫"
        )

    elif text == "📤 Отправить чек":
        await update.message.reply_text("📎 Отправьте фото или файл с чеком, я всё зафиксирую.")

    elif text == "🔓 Проверить доступ к RESONANCE":
        await update.message.reply_text("🔍 Введите почту, с которой оформлялась подписка — я проверю доступ.")

    else:
        # если пользователь написал вопрос
        ai_reply = await ask_ai(text)
        await update.message.reply_text(ai_reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_id = update.message.photo[-1].file_id if update.message.photo else None
    caption = update.message.caption or ""
    add_to_sheet([user.username, "Чек", file_id, caption, str(update.message.date)])
    await update.message.reply_text("✅ Чек успешно принят! Ожидайте подтверждения доступа.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_id = update.message.document.file_id
    caption = update.message.caption or ""
    add_to_sheet([user.username, "Файл", file_id, caption, str(update.message.date)])
    await update.message.reply_text("✅ Чек успешно принят! Ожидайте подтверждения доступа.")


# === Запуск бота ===
def run_bot():
    app_tg = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_tg.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_tg.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("🚀 Bot started successfully.")
    app_tg.run_polling()


if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
