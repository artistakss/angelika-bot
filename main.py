import os
import json
import logging
import datetime
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from openai import OpenAI

# ---------------------- #
# 🔧 Настройки окружения
# ---------------------- #
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# ---------------------- #
# 🧾 Настройки Google Sheets
# ---------------------- #
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

SPREADSHEET_ID = "ТУТ_ВСТАВЬ_ID_ТВОЕЙ_ТАБЛИЦЫ"  # ⚠️ Замени на свой ID
SHEET_CHEQUES = "Cheques"
SHEET_SESSIONS = "Sessions"

# ---------------------- #
# 🧠 Инициализация OpenAI
# ---------------------- #
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------- #
# ⚙️ Логирование
# ---------------------- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("angelika-bot")

# ---------------------- #
# 🌐 Flask сервер
# ---------------------- #
app = Flask(__name__)


@app.route("/")
def index():
    return "Angelika Resonance Bot is alive 🌸"


# ---------------------- #
# 🧩 Кнопки меню
# ---------------------- #
def main_menu():
    buttons = [
        [KeyboardButton("📋 Реквизиты для оплаты")],
        [KeyboardButton("📤 Отправить чек")],
        [KeyboardButton("🔓 Проверить доступ к RESONANCE")],
        [KeyboardButton("📅 Записаться на сессию")],
        [KeyboardButton("ℹ️ FAQ")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# ---------------------- #
# 🚀 Старт
# ---------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Привет! Я нейро-ассистент Анжелики.\n\n"
        "Я помогу тебе:\n"
        "🔹 Войти в сообщество RESONANCE\n"
        "🔹 Узнать реквизиты для оплаты\n"
        "🔹 Проверить доступ\n"
        "🔹 Записаться на сессию\n"
        "🔹 Задать вопрос\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu(),
    )


# ---------------------- #
# 📋 Реквизиты
# ---------------------- #
async def show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💳 *Реквизиты для оплаты:*\n\n"
        "Kaspi: https://pay.kaspi.kz/pay/ymwm8kds\n"
        "Halyk Bank: 4405 6397 3973 4828\n"
        "Tinkoff: 2200 7008 3889 3427\n"
        "USDT (TRC20): TLhAz9G84nAdMvJtb7NoZRqCXfekDxj5rN\n\n"
        "После оплаты нажмите 📤 *Отправить чек*."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ---------------------- #
# ℹ️ FAQ
# ---------------------- #
async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📘 *FAQ:*\n"
        "- Текущая цена: 11 111 ₸\n"
        "- Доступ на 30 дней\n"
        "- После оплаты пришлите чек для подтверждения."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ---------------------- #
# 📤 Отправка чека
# ---------------------- #
async def receive_cheque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_id = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("📎 Пожалуйста, отправьте фото или файл с чеком.")
        return

    try:
        sheet = service.spreadsheets()
        values = [
            [
                user.username or "",
                str(user.id),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                file_id,
                "Ожидает",
            ]
        ]
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_CHEQUES}!A:E",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
        await update.message.reply_text("✅ Чек успешно получен. Проверка занимает до 24 часов.")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Ошибка при сохранении чека.")


# ---------------------- #
# 🔓 Проверка доступа
# ---------------------- #
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    try:
        sheet = service.spreadsheets()
        data = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_CHEQUES}!A:E")
            .execute()
        )
        rows = data.get("values", [])
        for row in rows:
            if len(row) >= 5 and (row[0] == user.username or row[1] == str(user.id)):
                if row[4].lower() == "подтвержден":
                    await update.message.reply_text(
                        "✅ Доступ подтверждён!\nДобро пожаловать в сообщество RESONANCE 💫\n"
                        "🔗 [Перейти в канал](https://t.me/your_channel_invite_link)",
                        parse_mode="Markdown",
                    )
                    return
        await update.message.reply_text(
            "🚫 Доступ не найден.\nПожалуйста, оплатите участие и отправьте чек через 📤 Отправить чек."
        )
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("⚠️ Ошибка при проверке доступа.")


# ---------------------- #
# 📅 Запись на сессию
# ---------------------- #
async def start_session_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 Напишите, пожалуйста:\n"
        "- Онлайн или оффлайн формат;\n"
        "- Удобное число и время;\n"
        "- Ваш вопрос или цель встречи."
    )
    context.user_data["waiting_for_session_info"] = True


async def save_session_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for_session_info"):
        user = update.message.from_user
        text = update.message.text
        try:
            sheet = service.spreadsheets()
            values = [
                [
                    user.username or "",
                    str(user.id),
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text,
                    "Новая",
                ]
            ]
            sheet.values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_SESSIONS}!A:E",
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
            await update.message.reply_text("✅ Ваша заявка на сессию сохранена. Анжелика свяжется с вами.")
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("❌ Ошибка при записи в таблицу.")
        context.user_data["waiting_for_session_info"] = False


# ---------------------- #
# 💬 AI-ответы (общие вопросы)
# ---------------------- #
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты ассистент Анжелики, которая занимается духовным развитием, эзотерикой и самопознанием."},
                {"role": "user", "content": user_text},
            ],
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("⚠️ Ошибка при обращении к AI.")


# ---------------------- #
# 🚀 Запуск бота
# ---------------------- #
def run_bot():
    app_tg = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(MessageHandler(filters.Regex("📋"), show_payment))
    app_tg.add_handler(MessageHandler(filters.Regex("ℹ️"), faq))
    app_tg.add_handler(MessageHandler(filters.Regex("📤"), receive_cheque))
    app_tg.add_handler(MessageHandler(filters.Regex("🔓"), check_access))
    app_tg.add_handler(MessageHandler(filters.Regex("📅"), start_session_request))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_session_request))
    app_tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))

    logger.info("🚀 Bot started successfully.")
    app_tg.run_polling()


def run_flask():
    app.run(host="0.0.0.0", port=10000)


if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
