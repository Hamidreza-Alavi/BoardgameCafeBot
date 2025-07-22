import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import get_table_menu, get_item_menu

# وضعیت‌ها
user_states = {}  # user_id: {'mode': 'game' or 'order', 'table': ..., 'players': int, 'items': [...]}

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ شما اجازه استفاده از ربات را ندارید.")
    
    keyboard = [
        [InlineKeyboardButton("🎲 شروع بازی", callback_data="start_game")],
        [InlineKeyboardButton("☕ سفارش کافه", callback_data="start_order")]
    ]
    await update.message.reply_text("یکی از گزینه‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if uid not in ALLOWED_USER_IDS:
        return await query.message.reply_text("⛔ شما اجازه استفاده ندارید.")

    data = query.data

    if data == "start_game":
        user_states[uid] = {'mode': 'game'}
        await query.message.reply_text("📍 کدام میز؟", reply_markup=get_table_menu())

    elif data == "start_order":
        user_states[uid] = {'mode': 'order'}
        await query.message.reply_text("📍 سفارش برای کدام میز؟", reply_markup=get_table_menu())

    elif data.startswith("table_"):
        table_key = data.split("_", 1)[1]
        table = {"ps": "PS", "wheel": "فرمون"}.get(table_key, table_key)
        user_states[uid]['table'] = table

        if user_states[uid]['mode'] == 'game':
            await query.message.reply_text("👥 تعداد نفرات بازی را وارد کنید:")
        else:
            user_states[uid]['items'] = []
            await query.message.reply_text("🍽 چه آیتم‌هایی سفارش می‌دهید؟", reply_markup=get_item_menu())

    elif data.startswith("item_"):
        item = data.split("_", 1)[1]
        user_states[uid]['items'].append(item)
        await query.message.reply_text(f"➕ «{item}» اضافه شد.")

    elif data == "done_order":
        data = user_states.get(uid)
        if not data or 'items' not in data:
            return await query.message.reply_text("❌ سفارشی ثبت نشده.")
        
        table = data['table']
        items = "، ".join(data['items'])
        msg = (
            f"📦 سفارش کافه\n"
            f"🪑 میز: {table}\n"
            f"🍽 سفارش: {items}\n"
            f"👤 توسط: @{query.from_user.username or query.from_user.first_name}"
        )
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
        await query.message.reply_text("✅ سفارش ارسال شد.")
        user_states.pop(uid)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_states:
        return

    state = user_states[uid]
    if state['mode'] == 'game' and 'players' not in state:
        try:
            players = int(update.message.text)
            state['players'] = players
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                f"🎲 شروع بازی\n"
                f"🪑 میز: {state['table']}\n"
                f"👥 نفرات: {players}\n"
                f"⏰ ساعت: {start_time}\n"
                f"👤 توسط: @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ شروع بازی ثبت شد.")
            user_states.pop(uid)
        except ValueError:
            await update.message.reply_text("❗ لطفاً عدد وارد کنید.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()