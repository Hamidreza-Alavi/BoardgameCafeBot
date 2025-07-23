import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import get_table_menu, get_category_menu, get_item_menu_by_category

logging.basicConfig(level=logging.INFO)

user_states = {}

# ------------- HELPER FUNCTIONS -------------

def format_orders(orders):
    lines = []
    for i, items in enumerate(orders, 1):
        lines.append(f"{i}. " + "، ".join(items))
    return "\n".join(lines) if lines else "هیچ سفارشی ثبت نشده."

def format_players(players):
    lines = []
    for num, time in players:
        lines.append(f"بازیکن {num} - ساعت ورود: {time}")
    return "\n".join(lines) if players else "هیچ بازیکنی ثبت نشده."

# ------------- HANDLERS -------------

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

    # حالت شروع بازی
    if data == "start_game":
        user_states[uid] = {'mode': 'game'}
        await query.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        return

    # حالت سفارش
    if data == "start_order":
        user_states[uid] = {'mode': 'order'}
        await query.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        return

    # انتخاب میز
    if data.startswith("table_"):
        table_key = data.split("_", 1)[1]
        table = {"free": "میز آزاد", "ps": "PS", "wheel": "فرمون"}.get(table_key, f"میز {table_key}")
        state = user_states.setdefault(uid, {})
        state['table'] = table

        if state.get('mode') == 'game':
            # اگر بازی قبلی وجود دارد، گزینه ادامه یا پایان بازی بده
            if 'game' in state:
                keyboard = [
                    [InlineKeyboardButton("افزودن بازیکن جدید", callback_data="add_player")],
                    [InlineKeyboardButton("حذف بازیکن", callback_data="remove_player")],
                    [InlineKeyboardButton("پایان بازی", callback_data="end_game")]
                ]
                await query.message.reply_text(f"بازی قبلی روی {table} وجود دارد.\nبازیکنان:\n{format_players(state['game']['players'])}\nچه کاری می‌خواهید انجام دهید؟",
                                               reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.message.reply_text("تعداد نفرات؟")
        else:
            # سفارش جدید
            state['items'] = []
            state.setdefault('orders', [])
            await query.message.reply_text("🍽 دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    # دسته‌بندی سفارش
    if data.startswith("cat_"):
        cat_key = data.split("_", 1)[1]
        user_states[uid]['current_category'] = cat_key
        await query.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu_by_category(cat_key))
        return

    # انتخاب آیتم سفارش
    if data.startswith("item_"):
        item = data.split("_", 1)[1]
        user_states[uid].setdefault('items', []).append(item)
        await query.message.reply_text(f"«{item}» اضافه شد.\nدسته بعدی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    if data == "back_to_categories":
        await query.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    # اتمام سفارش - ذخیره سفارش جدید
    if data == "done_order":
        state = user_states.get(uid)
        if not state or 'items' not in state or not state['items']:
            return await query.message.reply_text("❗ سفارشی ثبت نشده.")
        # افزودن سفارش جدید
        state.setdefault('orders', []).append(state['items'])
        items_str = "، ".join(state['items'])
        await query.message.reply_text(f"✅ سفارش جدید به میز «{state['table']}» اضافه شد:\n🍽 {items_str}")
        # پاک کردن آیتم‌ها برای سفارش بعدی
        state['items'] = []
        return

    # نمایش و ویرایش سفارش‌ها
    if data == "show_orders":
        state = user_states.get(uid)
        if not state or 'orders' not in state or not state['orders']:
            return await query.message.reply_text("هیچ سفارشی برای ویرایش وجود ندارد.")
        buttons = []
        for i, order in enumerate(state['orders']):
            buttons.append([InlineKeyboardButton(f"ویرایش سفارش {i+1}", callback_data=f"edit_order_{i}")])
        buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_categories")])
        await query.message.reply_text("سفار‌ش‌ها را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # شروع ویرایش یک سفارش
    if data.startswith("edit_order_"):
        idx = int(data.split("_")[2])
        state = user_states.get(uid)
        if not state or 'orders' not in state or idx >= len(state['orders']):
            return await query.message.reply_text("سفارش نامعتبر است.")
        order = state['orders'][idx]
        buttons = []
        for i, item in enumerate(order):
            buttons.append([InlineKeyboardButton(f"حذف {item}", callback_data=f"remove_item_{idx}_{i}")])
        buttons.append([InlineKeyboardButton("بازگشت به سفارش‌ها", callback_data="show_orders")])
        await query.message.reply_text(f"آیتم‌های سفارش {idx+1}:\n" + "، ".join(order), reply_markup=InlineKeyboardMarkup(buttons))
        return

    # حذف آیتم از سفارش
    if data.startswith("remove_item_"):
        parts = data.split("_")
        order_idx, item_idx = int(parts[2]), int(parts[3])
        state = user_states.get(uid)
        if not state or 'orders' not in state or order_idx >= len(state['orders']):
            return await query.message.reply_text("سفارش نامعتبر است.")
        order = state['orders'][order_idx]
        if item_idx >= len(order):
            return await query.message.reply_text("آیتم نامعتبر است.")
        removed_item = order.pop(item_idx)
        if not order:
            # اگر سفارش خالی شد، حذفش کن
            state['orders'].pop(order_idx)
        await query.message.reply_text(f"«{removed_item}» از سفارش حذف شد.")
        return

    # بازی: افزودن بازیکن جدید
    if data == "add_player":
        state = user_states.get(uid)
        if not state or 'game' not in state:
            state['game'] = {'players': []}
        players = state['game']['players']
        new_num = (players[-1][0] + 1) if players else 1
        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        players.append((new_num, join_time))
        await query.message.reply_text(f"بازیکن شماره {new_num} اضافه شد (ساعت {join_time}).")
        return

    # بازی: حذف بازیکن
    if data == "remove_player":
        state = user_states.get(uid)
        if not state or 'game' not in state or not state['game']['players']:
            return await query.message.reply_text("هیچ بازیکنی برای حذف وجود ندارد.")
        buttons = []
        for num, _ in state['game']['players']:
            buttons.append([InlineKeyboardButton(f"حذف بازیکن {num}", callback_data=f"del_player_{num}")])
        buttons.append([InlineKeyboardButton("انصراف", callback_data="start_game")])
        await query.message.reply_text("بازیکنی که می‌خواهید حذف کنید را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("del_player_"):
        num = int(data.split("_")[2])
        state = user_states.get(uid)
        players = state['game']['players']
        new_players = [p for p in players if p[0] != num]
        state['game']['players'] = new_players
        await query.message.reply_text(f"بازیکن شماره {num} حذف شد.")
        return

    # پایان بازی و ارسال پیام در کانال
    if data == "end_game":
        state = user_states.get(uid)
        if not state or 'game' not in state:
            return await query.message.reply_text("بازی در حال اجرا وجود ندارد.")
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        players = state['game']['players']
        table = state['table']
        player_lines = "\n".join([f"بازیکن {num} - ساعت ورود: {time}" for num, time in players])
        msg = (
            f"🎲 بازی پایان یافت:\n"
            f"🪑 میز: {table}\n"
            f"👥 بازیکنان:\n{player_lines}\n"
            f"⏰ ساعت پایان: {end_time}\n"
            f"👤 @{query.from_user.username or query.from_user.first_name}"
        )
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
        # حذف اطلاعات بازی
        del state['game']
        await query.message.reply_text("✅ بازی با موفقیت پایان یافت و پیام ارسال شد.")
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_states:
        return
    state = user_states[uid]

    # ثبت تعداد نفرات برای شروع بازی
    if state.get('mode') == 'game' and 'game' not in state:
        try:
            players_count = int(update.message.text)
            join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state['game'] = {'players': [(i+1, join_time) for i in range(players_count)]}
            await update.message.reply_text(f"✅ بازی با {players_count} نفر شروع شد.")
            msg = (
                f"🎲 بازی شروع شد:\n"
                f"🪑 میز: {state['table']}\n"
                f"👥 تعداد نفرات: {players_count}\n"
                f"⏰ ساعت شروع: {join_time}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
    # ثبت سفارش، به صورت نرمال با دکمه‌ها انجام می‌شود

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()