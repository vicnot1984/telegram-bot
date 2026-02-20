import sqlite3
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
)

# ================== НАЛАШТУВАННЯ ==================
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = 8007715299
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DB_NAME = "applications.db"

# ================== БАЗА ДАНИХ ==================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            relative_info TEXT,
            applicant_info TEXT
        )
    """)
    conn.commit()
    conn.close()

# ================== СТАНИ ==================
START, RELATIVE, APPLICANT = range(3)

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Кнопку показуємо ТІЛЬКИ користувачу, не адміну
    if update.message.from_user.id == ADMIN_ID:
        await update.message.reply_text("Панель адміністратора активна.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Запит на пошук", callback_data="search")]
    ]

    await update.message.reply_text(
        "Натисніть кнопку для подачі запиту:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return START

# ================== КНОПКА ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Введіть дані про особу, яку розшукуєте:\n\n"
        "ПІБ\n"
        "Дата народження\n"
        "Місце перебування\n"
        "Дата та місце останнього контакту"
    )
    return RELATIVE

# ================== ДАНІ ПРО ОСОБУ ==================
async def relative_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["relative_info"] = update.message.text

    await update.message.reply_text(
        "Введіть ваші дані:\n\n"
        "ПІБ\n"
        "Дата народження\n"
        "Місце проживання\n"
        "Місце роботи\n"
        "Ступінь спорідненості\n"
        "Контакт у Telegram\n"
        "Додаткові відомості"
    )
    return APPLICANT

# ================== ДАНІ ЗАЯВНИКА ==================
async def applicant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name
    applicant_text = update.message.text
    relative_text = context.user_data.get("relative_info", "")

    # Збереження в базу
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(""
