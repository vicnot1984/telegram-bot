import os
import sqlite3
import time
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==============================
# НАЛАШТУВАННЯ
# ==============================

import os

TOKEN = os.environ.get("TOKEN")

print("DEBUG TOKEN:", TOKEN)

ADMIN_ID = 8007715299

DB_NAME = "applications.db"
SPAM_LIMIT_SECONDS = 60

# ==============================
# СТАНИ ДІАЛОГУ
# ==============================

CHOOSING, MISSING_INFO, APPLICANT_INFO, CONTACT_INFO = range(4)

# ==============================
# БАЗА ДАНИХ
# ==============================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            missing_info TEXT,
            applicant_info TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ==============================
# АНТИСПАМ
# ==============================

user_last_request = {}

def is_spam(user_id):
    now = time.time()
    if user_id in user_last_request:
        if now - user_last_request[user_id] < SPAM_LIMIT_SECONDS:
            return True
    user_last_request[user_id] = now
    return False

# ==============================
# /start
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Пошук родича"],
        ["Контакт з родичем"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Оберіть дію:",
        reply_markup=reply_markup
    )
    return CHOOSING

# ==============================
# ВИБІР
# ==============================

async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if is_spam(update.message.from_user.id):
        await update.message.reply_text(
            "⛔ Ви можете подавати лише 1 заявку на хвилину."
        )
        return ConversationHandler.END

    if text == "Пошук родича":
        context.user_data["type"] = "search"
        await update.message.reply_text(
            "Введіть ПІБ, дату народження, місце та дату останнього контакту:",
            reply_markup=ReplyKeyboardRemove()
        )
        return MISSING_INFO

    elif text == "Контакт з родичем":
        context.user_data["type"] = "contact"
        await update.message.reply_text(
            "Введіть:\n\n"
            "ПІБ\nДата народження\nМісце проживання\n"
            "Місце роботи\nСтупінь спорідненості\n"
            "Номер телефону для Telegram:"
        )
        return CONTACT_INFO

    else:
        await update.message.reply_text("Оберіть кнопку.")
        return CHOOSING

# ==============================
# ДАНІ ПРО ЗНИКЛОГО
# ==============================

async def missing_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["missing_info"] = update.message.text
    await update.message.reply_text(
        "Введіть інформацію про заявника:\n\n"
        "ПІБ\nДата народження\nМісце проживання\n"
        "Місце роботи\nСтупінь спорідненості\n"
        "Телефон для Telegram\nДодаткові відомості:"
    )
    return APPLICANT_INFO

# ==============================
# ЗБЕРЕЖЕННЯ ЗАЯВКИ (ПОШУК)
# ==============================

async def applicant_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    applicant_text = update.message.text

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO applications (type, missing_info, applicant_info, user_id)
        VALUES (?, ?, ?, ?)
    """, (
        context.user_data["type"],
        context.user_data.get("missing_info", ""),
        applicant_text,
        update.message.from_user.id
    ))

    app_id = cursor.lastrowid
    conn.commit()
    conn.close()

    summary = (
        f"🆕 Заявка №{app_id}\n\n"
        f"🔎 Пошук родича\n\n"
        f"📌 Дані про особу:\n"
        f"{context.user_data.get('missing_info')}\n\n"
        f"👤 Дані заявника:\n"
        f"{applicant_text}"
    )

    # Надіслати адміну
    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)

    await update.message.reply_text(
        f"✅ Заявка №{app_id} прийнята. Очікуйте відповіді.",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

# ==============================
# ЗБЕРЕЖЕННЯ ЗАЯВКИ (КОНТАКТ)
# ==============================

async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    applicant_text = update.message.text

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO applications (type, missing_info, applicant_info, user_id)
        VALUES (?, ?, ?, ?)
    """, (
        context.user_data["type"],
        "",
        applicant_text,
        update.message.from_user.id
    ))

    app_id = cursor.lastrowid
    conn.commit()
    conn.close()

    summary = (
        f"🆕 Заявка №{app_id}\n\n"
        f"📞 Контакт з родичем\n\n"
        f"👤 Дані заявника:\n"
        f"{applicant_text}"
    )

    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)

    await update.message.reply_text(
        f"✅ Заявка №{app_id} прийнята. Очікуйте відповіді.",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

# ==============================
# ЗАПУСК
# ==============================

def main():
   
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose)],
            MISSING_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, missing_info)],
            APPLICANT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, applicant_info)],
            CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_info)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
