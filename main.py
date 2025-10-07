# main.py — Telegram-bot для платного доступа + Google Sheets фиксация чеков
import os
import openai
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("angelika-bot")

# ---------------- Flask Keepalive ----------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot is running", 200

def run_flask():
    port = int(os.getenv("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# ---------------- Environment Variables ----------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID      = os.getenv("ADMIN_CHAT_ID")
SPREADSHEET_URL    = os.getenv("SPREADSHEET_URL")
GOOGLE_CREDS_JSON  = os.getenv("GOOGLE_CREDS_JSON")

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
if not SPREADSHEET_URL:
    logger.warning("⚠️ SPREADSHEET_URL not set. Google Sheets disabled.")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# ---------------- Google Sheets ----------------
worksheet = None
if GOOGLE_CREDS_JSON and SPREADSHEET_URL:
    try:
        import json
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        worksheet = client.open_by_url(SPREADSHEET_URL).sheet1
        logger.info("✅ Connected to Google Sheets.")
    except Exception as e:
        logger.error(f"❌ Error connecting to Google Sheets: {e}")

# ---------------- Business Logic ----------------
CURRENT_PRICE = 11111
SUBSCRIPTION_DAYS = 30
CHANNEL_INVITE_LINK = "https://t.me/+MlsulyVeuGZlZDJi"

PROMPT = (
    "Ты — нейро-ассистент Анжелики, тренера по вниманию и пробуждению. "
    "Помогай клиенту мягко и вдохновляюще. "
    f"Текущая стоимость доступа: {CURRENT_PRICE} тенге, "
    "цена фиксируется при оплате и растёт каждый месяц."
)

expect_receipt = {}

# ---------------- Helpers ----------------
def record_payment(nick, user_id, date_paid, amount, method, comment, receipt_file_id=None):
    if not worksheet:
        logger.warning("⚠️ Worksheet not available, skipping record.")
        return False
    try:
        row = [nick, str(user_id), date_paid, str(amount), method, comment or "", receipt_file_id or ""]
        worksheet.append_row(row)
        logger.info(f"✅ Recorded payment: {row}")
        return True
    except Exception as e:
        logger.error(f"❌ Error writing to Google Sheets: {e}")
        return False

def get_last_payment_info(user_id):
    if not worksheet:
        return None
    try:
        all_values = worksheet.get_all_values()
        rows = [r for r in all_values[1:] if len(r) > 1 and r[1] == str(user_id)]
        if not rows:
            return None
        last = rows[-1]
        return {"date_paid": last[2]}
    except Exception as e:
        logger.error(f"Error reading sheet: {e}")
        return None

def is_subscription_active(user_id):
    info = get_last_payment_info(user_id)
    if not info:
        return False, None
    try:
        paid_date = datetime.strptime(info["date_paid"], "%Y-%m-%d")
        expires = paid_date + timedelta(days=SUBSCRIPTION_DAYS)
        return datetime.utcnow() <= expires, expires
    except Exception as e:
        logger.error(f"Date parse error: {e}")
        return False, None

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📌 Оплатить доступ"), KeyboardButton("📋 Реквизиты")],
            [KeyboardButton("📤 Отправить чек"), KeyboardButton("🔓 Проверить доступ")],
            [KeyboardButton("🔮 Вход в сообщество RESONANSE"), KeyboardButton("📅 Записаться на сессию")],
            [KeyboardButton("ℹ️ FAQ")]
        ],
        resize_keyboard=True
    )

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Привет! Я нейро-ассистент Анжелики.\n\n"
        "Я помогу тебе:\n"
        "🔹 Войти в сообщество RESONANCE\n"
        "🔹 Узнать реквизиты для оплаты\n"
        "🔹 Проверить доступ\n"
        "🔹 Задать вопрос\n\n"
        "Выбери действие ниже 👇",
        reply_markup=main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = user.id
    nick = user.username or user.full_name

    if text == "📋 Реквизиты" or text == "📌 Оплатить доступ":
        await update.message.reply_text(
            "Реквизиты для оплаты:\n\n"
            "Kaspi: https://pay.kaspi.kz/pay/ymwm8kds\n"
            "Halyk Bank: 4405 6397 3973 4828\n"
            "Tinkoff: 2200 7008 3889 3427\n"
            "USDT (TRC20): TLhAz9G84nAdMvJtb7NoZRqCXfekDxj5rN\n\n"
            "После оплаты нажмите '📤 Отправить чек'."
        )
        return

    if text == "📤 Отправить чек":
        expect_receipt[user_id] = True
        await update.message.reply_text("Отправьте фото/файл с чеком.")
        return

    if text == "🔓 Проверить доступ":
        active, expires = is_subscription_active(user_id)
        if active:
            await update.message.reply_text(f"✅ Подписка активна до {expires.date()}. Ссылка: {CHANNEL_INVITE_LINK}")
        else:
            await update.message.reply_text("❌ Подписка не найдена. Оплатите доступ и пришлите чек.")
        return

    if text == "ℹ️ FAQ":
        await update.message.reply_text(
            f"FAQ:\n- Текущая цена: {CURRENT_PRICE} ₸\n- Доступ на {SUBSCRIPTION_DAYS} дней\n- После оплаты пришлите чек."
        )
        return

    if OPENAI_API_KEY:
        try:
            resp = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
                max_tokens=300,
                temperature=0.8
            )
            answer = resp.choices[0].message.content
            await update.message.reply_text(answer)
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            await update.message.reply_text("Ошибка при обращении к AI.")
    else:
        await update.message.reply_text("Я пока без AI-ответов, но помогу с оплатой и доступом ❤️")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nick = update.effective_user.username or update.effective_user.full_name

    if not expect_receipt.get(user_id):
        await update.message.reply_text("Сначала нажмите '📤 Отправить чек'.")
        return

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if not file_id:
        await update.message.reply_text("Не удалось распознать файл.")
        return

    date_paid = datetime.utcnow().strftime("%Y-%m-%d")
    success = record_payment(nick, user_id, date_paid, "unknown", "manual", "Оплата", file_id)
    expect_receipt[user_id] = False

    if success:
        await update.message.reply_text("✅ Чек получен. Админ скоро проверит.")
        if ADMIN_CHAT_ID:
            await context.bot.send_message(ADMIN_CHAT_ID, f"Новый чек от {nick} ({user_id})")
    else:
        await update.message.reply_text("❌ Ошибка записи чека.")

# ---------------- Run ----------------
def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🚀 Bot started successfully.")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()

