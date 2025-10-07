import logging
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

# ------------------ ЛОГИ ------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("angelika-bot")

# ------------------ НАСТРОЙКИ ------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------ GOOGLE SHEETS ------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(eval(GOOGLE_CREDS_JSON), scopes=SCOPES)
gc = gspread.authorize(creds)

SHEET_NAME = "AngelikaBot"
try:
    sh = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sh = gc.create(SHEET_NAME)
    sh.share(None, perm_type='anyone', role='writer')

try:
    worksheet = sh.worksheet("Data")
except gspread.WorksheetNotFound:
    worksheet = sh.add_worksheet(title="Data", rows=1000, cols=10)
    worksheet.append_row(["Имя", "Username", "Тип", "Комментарий/Данные"])

# ------------------ КНОПКИ ------------------
main_menu = ReplyKeyboardMarkup(
    [
        ["📅 Записаться на сессию", "📤 Отправить чек"],
        ["💳 Реквизиты для оплаты", "💡 FAQ"],
        ["🔓 Проверить доступ к RESONANCE"]
    ],
    resize_keyboard=True
)

# ------------------ КОМАНДЫ ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        "✨ Привет! Я нейро-ассистент Анжелики.\n\n"
        "Я помогу тебе:\n"
        "🔹 Войти в сообщество RESONANCE\n"
        "🔹 Узнать реквизиты для оплаты\n"
        "🔹 Проверить доступ\n"
        "🔹 Задать вопрос\n\n"
        "Выбери действие ниже 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu)

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FAQ:\n- Текущая цена: 11111 ₸\n- Доступ на 30 дней\n- После оплаты пришлите чек."
    )

async def payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 Реквизиты для оплаты:\n\n"
        "Kaspi: https://pay.kaspi.kz/pay/ymwm8kds\n"
        "Halyk Bank: 4405 6397 3973 4828\n"
        "Tinkoff: 2200 7008 3889 3427\n"
        "USDT (TRC20): TLhAz9G84nAdMvJtb7NoZRqCXfekDxj5rN\n\n"
        "После оплаты нажмите '📤 Отправить чек'."
    )

# ------------------ ОТПРАВКА ЧЕКА ------------------
async def send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте фото или файл с чеком.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        worksheet.append_row([user.first_name, user.username, "Чек", "Получен файл/фото"])
        await update.message.reply_text("✅ Чек получен! Мы проверим его и подтвердим доступ.")
    except Exception as e:
        logger.error(f"Ошибка записи чека: {e}")
        await update.message.reply_text("❌ Ошибка записи чека. Попробуйте снова позже.")

# ------------------ ЗАПИСЬ НА СЕССИЮ ------------------
ASK_SESSION = range(1)

async def ask_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 Для записи укажите:\n1️⃣ Онлайн или офлайн\n2️⃣ Удобную дату и время\n3️⃣ Примерный запрос или вопрос"
    )
    return ASK_SESSION

async def save_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text
    try:
        worksheet.append_row([user.first_name, user.username, "Заявка на сессию", user_text])
        await update.message.reply_text("✅ Спасибо! Заявка записана. Мы свяжемся с вами для подтверждения.")
    except Exception as e:
        logger.error(f"Ошибка записи заявки: {e}")
        await update.message.reply_text("❌ Ошибка записи в таблицу.")
    return ConversationHandler.END

# ------------------ ПРОВЕРКА ДОСТУПА ------------------
async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔓 Проверить доступ к RESONANCE:\n\n"
        "Введите ваш Telegram username (без @), и я проверю, есть ли у вас активный доступ."
    )

# ------------------ AI-ОТВЕТЫ ------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user = update.effective_user
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты ассистент Анжелики, помогаешь клиентам по подписке RESONANCE."},
                {"role": "user", "content": user_message},
            ],
        )
        ai_text = response.choices[0].message.content.strip()
        worksheet.append_row([user.first_name, user.username, "Вопрос", user_message])
        await update.message.reply_text(ai_text)
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        await update.message.reply_text("⚠️ Ошибка при обращении к AI.")

# ------------------ ОСНОВНОЙ БЛОК ------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    session_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📅 Записаться на сессию"), ask_session)],
        states={ASK_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_session)]},
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("💡 FAQ"), faq))
    app.add_handler(MessageHandler(filters.Regex("💳 Реквизиты для оплаты"), payment_details))
    app.add_handler(MessageHandler(filters.Regex("📤 Отправить чек"), send_receipt))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_photo))
    app.add_handler(session_conv)
    app.add_handler(MessageHandler(filters.Regex("🔓 Проверить доступ к RESONANCE"), check_access))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
