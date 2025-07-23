import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import pytz
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import get_table_menu, get_category_menu, get_item_menu_by_category

user_states = {}
logging.basicConfig(level=logging.INFO)

def now_tehran():
    utc_dt = datetime.utcnow()
    tehran_tz = pytz.timezone('Asia/Tehran')
    tehran_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(tehran_tz)
    return tehran_dt.strftime("%Y-%m-%d %H:%M:%S")

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

    # مدیریت حالت‌های اصلی
    if data == "start_game":
        user_states[uid] = {'mode': 'game'}
        await query.message.reply_text("کدام میز؟", reply_markup=get_table_menu())

    elif data == "start_order":
        user_states[uid] = {'mode': 'order', 'orders': []}
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
        if not data_state or 'items' not in data_state or len(data_state['items']) == 0:
            return await query.message.reply_text("❗ سفارشی ثبت نشده.")

        # ذخیره سفارش در حافظه (لیست orders)
        orders = data_state.setdefault('orders', [])
        orders.append(list(data_state['items']))
        data_state['items'].clear()

        # ارسال پیام سفارش در کانال
        items_str = "، ".join(orders[-1])
        msg = (
            f"📦 سفارش جدید:\n🪑 میز: {data_state['table']}\n"
            f"🍽 {items_str}\n👤 @{query.from_user.username or query.from_user.first_name}\n"
            f"⏰ زمان: {now_tehran()}"
        )
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)

        # پیام به کاربر با دکمه ویرایش سفارش‌ها
        keyboard = [
            [InlineKeyboardButton("ادامه سفارش", callback_data="back_to_categories")],
            [InlineKeyboardButton("ویرایش سفارش‌ها", callback_data="show_orders")]
        ]
        await query.message.reply_text("✅ سفارش ثبت شد.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "show_orders":
        state = user_states.get(uid)
        orders = state.get('orders', []) if state else []
        if not orders:
            return await query.message.reply_text("❗ هیچ سفارشی وجود ندارد.")

        buttons = []
        for i, order in enumerate(orders):
            buttons.append([InlineKeyboardButton(f"ویرایش سفارش {i+1}", callback_data=f"edit_order_{i}")])
        buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_categories")])
        await query.message.reply_text("سفارش‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("edit_order_"):
        idx = int(data.split("_")[2])
        state = user_states.get(uid)
        orders = state.get('orders', []) if state else []
        if idx < 0 or idx >= len(orders):
            return await query.message.reply_text("سفارش نامعتبر است.")

        items = orders[idx]
        if not items:
            return await query.message.reply_text("این سفارش خالی است.")

        buttons = []
        for item in items:
            buttons.append([InlineKeyboardButton(f"حذف {item}", callback_data=f"remove_item_{idx}_{item}")])
        buttons.append([InlineKeyboardButton("بازگشت به سفارش‌ها", callback_data="show_orders")])
        await query.message.reply_text("برای حذف آیتم روی آن کلیک کنید:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("remove_item_"):
        parts = data.split("_")
        idx = int(parts[2])
        item = "_".join(parts[3:])
        state = user_states.get(uid)
        orders = state.get('orders', []) if state else []
        if idx < 0 or idx >= len(orders):
            return await query.message.reply_text("سفارش نامعتبر است.")
        if item not in orders[idx]:
            return await query.message.reply_text("آیتم در سفارش موجود نیست.")

        orders[idx].remove(item)
        if not orders[idx]:
            # حذف سفارش خالی
            orders.pop(idx)
            await query.message.reply_text("سفارش خالی حذف شد.")
            # برگشت به منوی سفارش‌ها
            if orders:
                buttons = []
                for i, _ in enumerate(orders):
                    buttons.append([InlineKeyboardButton(f"ویرایش سفارش {i+1}", callback_data=f"edit_order_{i}")])
                buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_categories")])
                await query.message.reply_text("سفارش‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
            else:
                await query.message.reply_text("هیچ سفارشی موجود نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_categories")]]))
        else:
            # نمایش مجدد آیتم‌ها برای ویرایش
            buttons = []
            for itm in orders[idx]:
                buttons.append([InlineKeyboardButton(f"حذف {itm}", callback_data=f"remove_item_{idx}_{itm}")])
            buttons.append([InlineKeyboardButton("بازگشت به سفارش‌ها", callback_data="show_orders")])
            await query.message.reply_text("برای حذف آیتم روی آن کلیک کنید:", reply_markup=InlineKeyboardMarkup(buttons))

    # بازی
    elif data == "end_game":
        state = user_states.get(uid)
        if not state or state.get('mode') != 'game' or 'game_info' not in state:
            return await query.message.reply_text("بازی‌ای برای پایان دادن وجود ندارد.")
        game_info = state['game_info']
        end_time = now_tehran()
        msg = (
            f"🏁 پایان بازی:\n🪑 میز: {game_info['table']}\n"
            f"👥 تعداد نفرات: {game_info['players']}\n"
            f"⏰ شروع: {game_info['start_time']}\n"
            f"⏰ پایان: {end_time}\n"
            f"👤 @{query.from_user.username or query.from_user.first_name}"
        )
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
        user_states.pop(uid)

    else:
        await query.message.reply_text("گزینه نامعتبر است.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_states:
        return
    state = user_states[uid]
    if state['mode'] == 'game' and 'players' not in state:
        try:
            players = int(update.message.text)
            state['players'] = players
            state['game_info'] = {
                'table': state['table'],
                'players': players,
                'start_time': now_tehran()
            }
            now_str = state['game_info']['start_time']
            msg = (
                f"🎲 شروع بازی:\n🪑 میز: {state['table']}\n"
                f"👥 تعداد نفرات: {players}\n⏰ زمان: {now_str}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)

            # دکمه پایان بازی
            keyboard = [[InlineKeyboardButton("پایان بازی", callback_data="end_game")]]
            await update.message.reply_text("✅ بازی ثبت شد.", reply_markup=InlineKeyboardMarkup(keyboard))

            user_states.pop(uid)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
