import re
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from secrets import TOKEN, ADMIN_GROUP_ID

BANNED_FILE = "banned_users.json"


def load_banned_users():
    if not os.path.exists(BANNED_FILE):
        return set()

    with open(BANNED_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return set(data)


def save_banned_users():
    with open(BANNED_FILE, "w", encoding="utf-8") as file:
        json.dump(list(banned_users), file, ensure_ascii=False, indent=2)


banned_users = load_banned_users()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in banned_users:
        await update.message.reply_text("Доступ к боту ограничен.")
        return

    keyboard = [
        [InlineKeyboardButton("🎓 Подключиться к бесплатному курсу", url="https://russian-legion.ru/#enroll?curs=base")],
        [InlineKeyboardButton("🎯 Купить базовый очный курс", url="https://russian-legion.ru/#enroll?curs=std")],
        [InlineKeyboardButton("🚀 Купить месячный очный курс", url="https://russian-legion.ru/#enroll?curs=pro")],
        [InlineKeyboardButton("🛒 Другие товары", url="https://russian-legion.ru/game/")],
        [InlineKeyboardButton("❓ Часто задаваемые вопросы", url="https://russian-legion.ru/#faq")],
        [InlineKeyboardButton("💬 Связаться с нами", callback_data="contact")],
    ]

    await update.message.reply_text(
        "Добро пожаловать в Школу БПЛА «Русский Легион».\n\n"
        "Выберите нужный раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id in banned_users:
        await query.message.reply_text("Доступ к боту ограничен.")
        return

    context.user_data["waiting_question"] = True

    await query.message.reply_text(
        "Напишите Ваш вопрос одним сообщением.\n\n"
        "Мы получим его и ответим Вам здесь."
    )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    if user.id in banned_users:
        await update.message.reply_text("Доступ к боту ограничен.")
        return

    if context.user_data.get("waiting_question"):
        username = f"@{user.username}" if user.username else "не указан"

        message_to_group = (
            "📩 Новый вопрос через бота\n\n"
            f"Имя: {user.full_name}\n"
            f"Username: {username}\n"
            f"Telegram ID: {user.id}\n\n"
            f"Вопрос:\n{text}\n\n"
            "Чтобы ответить пользователю — нажмите «Ответить» на это сообщение.\n"
            "Чтобы забанить — /ban ID\n"
            "Чтобы разбанить — /unban ID"
        )

        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=message_to_group,
        )

        await update.message.reply_text(
            "Ваш вопрос отправлен.\n\n"
            "Мы ответим Вам в ближайшее время."
        )

        context.user_data["waiting_question"] = False
    else:
        await update.message.reply_text("Нажмите /start и выберите нужный раздел.")


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not update.message.reply_to_message:
        return

    replied_text = update.message.reply_to_message.text or ""
    admin_text = update.message.text

    match = re.search(r"Telegram ID:\s*(\d+)", replied_text)

    if not match:
        await update.message.reply_text(
            "Не нашёл Telegram ID пользователя. Отвечайте именно на сообщение заявки."
        )
        return

    user_id = int(match.group(1))

    if user_id in banned_users:
        await update.message.reply_text("Пользователь заблокирован. Ответ не отправлен.")
        return

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Ответ от команды «Русский Легион»:\n\n{admin_text}"
        )
        await update.message.reply_text("Ответ отправлен пользователю.")
    except Exception as e:
        await update.message.reply_text(f"Не удалось отправить ответ: {e}")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Укажите Telegram ID: /ban 123456789")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    banned_users.add(user_id)
    save_banned_users()

    await update.message.reply_text(f"Пользователь {user_id} заблокирован.")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Укажите Telegram ID: /unban 123456789")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    banned_users.discard(user_id)
    save_banned_users()

    await update.message.reply_text(f"Пользователь {user_id} разблокирован.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CallbackQueryHandler(contact, pattern="contact"))

    app.add_handler(MessageHandler(
        filters.Chat(chat_id=ADMIN_GROUP_ID) & filters.REPLY & filters.TEXT & ~filters.COMMAND,
        handle_admin_reply
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_user_message
    ))

    print("Бот запущен.")
    print(f"Заблокированных пользователей загружено: {len(banned_users)}")

    app.run_polling()


if __name__ == "__main__":
    main()