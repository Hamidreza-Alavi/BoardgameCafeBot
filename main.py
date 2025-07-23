import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import get_table_menu, get_category_menu, get_item_menu_by_category
from db import init_db, add_table_if_not_exists, save_order, save_game

user_states = {}
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ دسترسی ندارید.")
    keyboard = [
        [InlineKeyboardButton("🎲 شروع بازی", callback_data="start_game")],
        [InlineKeyboardButton("☕ سفارش کافه", callback_data="start_order")]
    ]
    await update.message.reply_text("گزینه‌ای را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    if uid not in ALLOWED_USER_IDS:
        return await query.message.reply_text("⛔ دسترسی ندارید.")
    data = query.data

    if data == "start_game":
        user_states[uid] = {'mode': 'game'}
        await query.message.reply_text("کدام میز؟", reply_markup=get_table_menu())

    elif data == "start_order":
        user_states[uid] = {'mode': 'order'}
        await query.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())

    elif data.startswith("table_"):
        table_key = data.split("_", 1)[1]
        table = {"free": "میز آزاد", "ps": "PS", "wheel": "فرمون"}.get(table_key, f"میز {table_key}")
        user_states[uid]['table'] = table

        if user_states[uid]['mode'] == 'game':
            await query.message.reply_text("تعداد نفرات؟")
        else:
            user_states[uid]['items'] = []
            await query.message.reply_text("🍽 دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())

    elif data.startswith("cat_"):
        cat_key = data.split("_", 1)[1]
        user_states[uid]['current_category'] = cat_key
        await query.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu_by_category(cat_key))

    elif data.startswith("item_"):
        item = data.split("_", 1)[1]
        user_states[uid].setdefault('items', []).append(item)
        await query.message.reply_text(f"«{item}» اضافه شد.\nدسته بعدی را انتخاب کنید:", reply_markup=get_category_menu())

    elif data == "back_to_categories":
        await query.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())

    elif data == "done_order":
        data_state = user_states.get(uid)
        if not data_state or 'items' not in data_state:
            return await query.message.reply_text("❗ سفارشی ثبت نشده.")
        items = data_state['items']
        # ذخیره سفارش در دیتابیس
        save_order(uid, data_state['table'], items)

        items_str = "، ".join(items)
        msg = (
            f"📦 سفارش جدید:\n🪑 میز: {data_state['table']}\n"
            f"🍽 {items_str}\n👤 @{query.from_user.username or query.from_user.first_name}"
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
            # ذخیره بازی در دیتابیس
            save_game(uid, state['table'], players)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                f"🎲 شروع بازی:\n🪑 میز: {state['table']}\n"
                f"👥 تعداد نفرات: {players}\n⏰ زمان: {now}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.")
            user_states.pop(uid)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")

def main():
    init_db()
    # مقداردهی اولیه میزها
    for i in range(1, 17):
        add_table_if_not_exists(f"میز {i}")
    add_table_if_not_exists("میز آزاد")
    add_table_if_not_exists("PS")
    add_table_if_not_exists("فرمون")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()