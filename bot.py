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

    # Видаляємо кнопки після натискання
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
        f"--- ДАНІ ЗАЯВНИКА ---\n{applicant_text}"
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
    else:
        c.execute(
            "SELECT user_id, id FROM applications ORDER BY id DESC LIMIT 1"
        )
        row = c.fetchone()
        if row:
            user_id, app_id = row
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Відповідь по заявці #{app_id}:\n{text}"
            )

    conn.close()

# ================== MAIN ==================
def main():
    init_db()

    if not TOKEN:
        raise ValueError("TOKEN не встановлений у змінних середовища")

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [CallbackQueryHandler(button_handler)],
            RELATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, relative_handler)],
            APPLICANT: [MessageHandler(filters.TEXT & ~filters.COMMAND, applicant_handler)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_messages))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
