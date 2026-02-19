import sqlite3
import time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters

# -------------------------- НАЛАШТУВАННЯ --------------------------
TOKEN = "8345565233:AAGkpG_0fFRYrdy8j0uS-pKsUApUW6IDAFY"
ADMIN_ID = 8007715299  # Вставити свій Telegram ID
SPAM_LIMIT = 60  # 1 заявка на хвилину

# -------------------------- СТАНИ --------------------------
CHOOSE, MISSING_INFO, APPLICANT_INFO, CONTACT_INFO = range(4)

# -------------------------- БАЗА ДАНИХ --------------------------
conn = sqlite3.connect("applications.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    missing_info TEXT,
    applicant_info TEXT,
    timestamp INTEGER
)
""")
conn.commit()

# -------------------------- START --------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔎 Пошук родича"], ["📩 Контакт з родичем"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Оберіть дію:", reply_markup=reply_markup)
    return CHOOSE

# -------------------------- ВИБІР --------------------------
async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # -------------------------- АНТИСПАМ --------------------------
    cursor.execute(
        "SELECT timestamp FROM applications WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    last = cursor.fetchone()
    if last and time.time() - last[0] < SPAM_LIMIT:
        await update.message.reply_text("⏳ Ви можете подати нову заявку через 1 хвилину.")
        return ConversationHandler.END

    choice = update.message.text
    context.user_data["mode"] = choice

    if "Пошук" in choice:
        await update.message.reply_text(
            "Введіть дані про особу:\n\n"
            "ПІБ:\n"
            "Дата народження:\n"
            "Місце та дата останнього контакту:",
            reply_markup=ReplyKeyboardRemove()
        )
        return MISSING_INFO
    else:
        await update.message.reply_text(
            "Введіть інформацію про себе:\n\n"
            "ПІБ:\n"
            "Дата народження:\n"
            "Місце проживання:\n"
            "Місце роботи:\n"
            "Ступінь спорідненості:\n"
            "Telegram-контакт:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CONTACT_INFO

# -------------------------- ПОШУК --------------------------
async def missing_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["missing"] = update.message.text

    await update.message.reply_text(
        "Тепер введіть інформацію про себе:\n\n"
        "ПІБ:\n"
        "Дата народження:\n"
        "Місце проживання:\n"
        "Місце роботи:\n"
        "Ступінь спорідненості:\n"
        "Telegram-контакт:\n"
        "Додаткові відомості:"
    )
    return APPLICANT_INFO

async def applicant_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    timestamp = int(time.time())

    cursor.execute("""
    INSERT INTO applications (user_id, type, missing_info, applicant_info, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, "search", context.user_data["missing"], update.message.text, timestamp))
    conn.commit()

    app_id = cursor.lastrowid

    summary = f"""
🆕 Заявка №{app_id}

🔎 Пошук родича

📌 Дані про особу:
{context.user_data['missing']}

👤 Дані заявника:
{update.message.text}
"""

    # Надсилаємо адміну підсумок
    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)

    # Пересилаємо адміну оригінальне повідомлення користувача (щоб можна було натиснути "Відповісти")
    await context.bot.forward_message(chat_id=ADMIN_ID,
                                      from_chat_id=update.message.chat_id,
                                      message_id=update.message.message_id)

    # Підтвердження користувачу
    await update.message.reply_text(f"✅ Заявка №{app_id} прийнята. Очікуйте відповіді.")
    return ConversationHandler.END

# -------------------------- КОНТАКТ --------------------------
async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    timestamp = int(time.time())

    cursor.execute("""
    INSERT INTO applications (user_id, type, missing_info, applicant_info, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, "contact", "", update.message.text, timestamp))
    conn.commit()

    app_id = cursor.lastrowid

    summary = f"""
🆕 Заявка №{app_id}

📩 Контакт з родичем

👤 Дані заявника:
{update.message.text}
"""
    # Надсилаємо адміну підсумок
    await context.bot.send_message(chat_id=ADMIN_ID, text=summary)

    # Пересилаємо адміну оригінальне повідомлення користувача
    await context.bot.forward_message(chat_id=ADMIN_ID,
                                      from_chat_id=update.message.chat_id,
                                      message_id=update.message.message_id)

    await update.message.reply_text(f"✅ Заявка №{app_id} прийнята. Очікуйте відповіді.")
    return ConversationHandler.END

# -------------------------- ЗАПУСК --------------------------
app = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose)],
        MISSING_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, missing_info)],
        APPLICANT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, applicant_info)],
        CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_info)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.run_polling()
