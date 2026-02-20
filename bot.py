import sqlite3
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

# ====================== Налаштування ======================
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = 8007715299

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================== База даних =========================
DB_NAME = "applications.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            relative_name TEXT,
            relative_birth TEXT,
            last_contact TEXT,
            additional_info TEXT
        )
    """)
    conn.commit()
    conn.close()

# ====================== Константи для ConversationHandler =========
CHOOSING, RELATIVE_INFO, USER_INFO = range(3)

# ====================== Старт =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Пошук родича", callback_data='search')],
        [InlineKeyboardButton("Контакт з родичем", callback_data='contact')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть дію:", reply_markup=reply_markup)
    return CHOOSING

# ====================== Callback кнопок ====================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['choice'] = query.data
    if query.data == 'search':
        await query.message.reply_text("Введіть дані про особу, яку шукаєте (ПІБ, дата народження, місце, останній контакт):")
        return RELATIVE_INFO
    elif query.data == 'contact':
        await query.message.reply_text("Введіть ваші дані для контакту (ПІБ, дата народження, місце проживання, місце роботи, ступінь спорідненості, Telegram, додаткові відомості):")
        return USER_INFO

# ====================== Обробка даних про родича =================
async def relative_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['relative_info'] = update.message.text
    await update.message.reply_text("Введіть свої дані для контакту (ПІБ, дата народження, місце проживання, місце роботи, ступінь спорідненості, Telegram, додаткові відомості):")
    return USER_INFO

# ====================== Обробка даних користувача =================
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name
    user_text = update.message.text
    relative_text = context.user_data.get('relative_info', '') if context.user_data.get('choice') == 'search' else ''

    # Збереження в базу
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO applications (user_id, user_name, relative_name, relative_birth, last_contact, additional_info) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, user_name, relative_text, '', '', user_text))
    app_id = c.lastrowid
    conn.commit()
    conn.close()

    # Надсилання адміну
    msg = f"Нова заявка #{app_id} від {user_name}:\n{user_text}\n{relative_text}"
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg)

    await update.message.reply_text("Заявка прийнята. Очікуйте відповіді.")
    return ConversationHandler.END

# ====================== Команда відповіді адміну ===================
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Ви не маєте доступу.")
        return

    try:
        app_id = int(context.args[0])
        reply_text = " ".join(context.args[1:])
    except (IndexError, ValueError):
        await update.message.reply_text("Використання: /reply <application_id> <текст відповіді>")
        return

    # Отримання user_id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM applications WHERE id=?", (app_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("Заявка не знайдена.")
        return

    user_id = row[0]
    # Надсилаємо повідомлення користувачу
    await context.bot.send_message(chat_id=user_id, text=f"Відповідь на вашу заявку #{app_id}:\n{reply_text}")
    await update.message.reply_text("Відповідь надіслана.")

# ====================== Основна функція =====================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [CallbackQueryHandler(button)],
            RELATIVE_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, relative_info)],
            USER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_info)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("reply", reply_command))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
