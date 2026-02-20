import sqlite3
import logging
import os
import re
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
    if update.message.from_user.id == ADMIN_ID:
        await update.message.reply_text("Адмін панель активна.")
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

    # Прибираємо кнопку після натискання
    await query.edit_message_reply_markup(reply_markup=None)

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

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO applications (user_id, user_name, relative_info, applicant_info) VALUES (?, ?, ?, ?)",
        (user_id, user_name, relative_text, applicant_text)
    )
    app_id = c.lastrowid
    conn.commit()
    conn.close()

    admin_message = (
        f"🔔 Нова заявка #{app_id}\n"
        f"Від: {user_name}\n\n"
        f"--- ДАНІ ПРО ОСОБУ ---\n{relative_text}\n\n"
        f"--- ДАНІ ЗАЯВНИКА ---\n{applicant_text}\n\n"
        f"📌 Відповідь через Reply або напишіть:\n"
        f"#{app_id} текст повідомлення"
    )

    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    await update.message.reply_text("✅ Заявка прийнята. Очікуйте відповіді.")

    return ConversationHandler.END

# ================== ДВОСТОРОННІЙ ЧАТ ==================
async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.message.from_user.id
    text = update.message.text

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # ---------------- КОРИСТУВАЧ ----------------
    if sender_id != ADMIN_ID:
        c.execute(
            "SELECT id FROM applications WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (sender_id,)
        )
        row = c.fetchone()
        if row:
            app_id = row[0]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"[Заявка #{app_id}] {update.message.from_user.full_name}:\n{text}"
            )

    # ---------------- АДМІН ----------------
    else:
        app_id = None

        # 1️⃣ Якщо відповідь через Reply
        if update.message.reply_to_message:
            match = re.search(r"#(\d+)", update.message.reply_to_message.text)
            if match:
                app_id = int(match.group(1))

        # 2️⃣ Якщо написано #ID текст
        if not app_id:
            match = re.match(r"#(\d+)\s+(.*)", text)
            if match:
                app_id = int(match.group(1))
                text = match.group(2)

        if app_id:
            c.execute(
                "SELECT user_id FROM applications WHERE id=?",
                (app_id,)
            )
            row = c.fetchone()
            if row:
                user_id = row[0]
                await conte
