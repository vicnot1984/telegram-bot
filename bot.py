import sqlite3
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

# ====================== Налаштування ======================
TOKEN = os.environ.get("TOKEN")  # Ваш Telegram Token
ADMIN_ID = 8007715299

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_NAME = "applications.db"

# ====================== Ініціалізація бази =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            relative_info TEXT,
            user_info TEXT,
            admin_chat_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

# ====================== Conversation states =================
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
        await query.message.reply_text(
            "Введіть дані про особу, яку шукаєте (ПІБ, дата народження, місце, останній контакт):"
        )
        return RELATIVE_INFO
    elif query.data == 'contact':
        await query.message.reply_text(
            "Введіть ваші дані для контакту (ПІБ, дата народження, місце проживання, місце роботи, ступінь спорідненості, Telegram, додаткові відомості):"
        )
        return USER_INFO

# ====================== Обробка даних про родича =================
async def relative_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['relative_info'] = update.message.text
    await update.message.reply_text(
        "Введіть свої дані для контакту (ПІБ, дата народження, місце проживання, місце роботи, ступінь спорідненості, Telegram, додаткові відомості):"
    )
    return USER_INFO

# ====================== Обробка даних користувача =================
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.full_name
    user_text = update.message.text
    relative_text = context.user_data.get('relative_info', '') if context.user_data.get('choice') == 'search' else ''

    # Створюємо окремий чат для адміна (через бота)
    admin_message = f"Нова заявка #{user_id} від {user_name}:\n\n--- Дані про особу ---\n{relative_text}\n\n--- Дані про заявника ---\n{user_text}"

    # Надсилаємо адміну та зберігаємо chat_id повідомлення
    msg = await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    admin_chat_id = msg.chat.id  # чат для цього повідомлення (один для адміна)

    # Збереження заявки в базу
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO applications (user_id, user_name, relative_info, user_info, admin_chat_id)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, user_name, relative_text, user_text, admin_chat_id))
    app_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text("Заявка прийнята. Очікуйте відповіді.")
    return ConversationHandler.END

# ====================== Двосторонній чат ====================
async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.message.from_user.id
    text = update.message.text

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Якщо повідомлення від користувача
    if sender_id != ADMIN_ID:
        c.execute("SELECT id, admin_chat_id FROM applications WHERE user_id=? ORDER BY id DESC LIMIT 1", (sender_id,))
        row = c.fetchone()
        if row:
            app_id, admin_chat_id = row
            await context.bot.send_message(chat_id=admin_chat_id,
                                           text=f"[Заявка #{app_id}] {update.message.from_user.full_name}:\n{text}")
    # Якщо повідомлення від адміністратора
    else:
        # Знаходимо останню заявку, щоб відправити відповідь користувачу
        c.execute("SELECT user_id, id FROM applications ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if row:
            user_id, app_id = row
            await context.bot.send_message(chat_id=user_id, text=f"Відповідь на вашу заявку #{app_id}:\n{text}")
    conn.close()

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_messages))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
