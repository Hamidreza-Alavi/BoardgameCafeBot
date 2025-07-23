import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
import json

logging.basicConfig(level=logging.INFO)

user_states = {}  # برای ذخیره وضعیت کاربر
orders = {}       # key: میز، value: list آیتم‌ها
games = {}        # key: میز، value: dict {players, start_time}

CATEGORY_LABELS = {
    "COFFEE_HOT": "☕ قهوه داغ",
    "COFFEE_COLD": "🧊 قهوه سرد",
    "HOT_DRINKS_NON_COFFEE": "🍫 نوشیدنی گرم غیرقهوه‌ای",
    "TEA": "🫖 چای",
    "HERBAL_TEA": "🌿 دمنوش",
    "MILKSHAKE": "🥤 میلک‌شیک",
    "JUICE": "🍹 آبمیوه",
    "MOCKTAIL": "🧃 ماکتیل",
    "ICE_CREAM": "🍨 بستنی",
    "CAKE": "🍰 کیک",
    "FOOD": "🍕 غذا",
    "ADDITIVES": "➕ افزودنی‌ها"
}

def get_table_list():
    # همه میزهای ممکن که در سفارش یا بازی استفاده شده اند (ترکیب keys از orders و games)
    all_tables = set(list(orders.keys()) + list(games.keys()))
    if not all_tables:
        return []
    buttons = [[KeyboardButton(table)] for table in sorted(all_tables)]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_table_menu():
    buttons = [[KeyboardButton(f"میز {i}")] for i in range(1, 17)]
    buttons += [
        [KeyboardButton("میز آزاد")],
        [KeyboardButton("PS")],
        [KeyboardButton("فرمون")]
    ]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_category_menu():
    buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
    buttons.append([KeyboardButton("ثبت سفارش")])
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_items_by_category(cat_label):
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
    # پیدا کردن کلید دسته بر اساس مقدار label
    key = None
    for k, v in CATEGORY_LABELS.items():
        if v == cat_label:
            key = k
            break
    if key:
        return items.get(key, [])
    return []

def get_item_menu(items):
    buttons = [[KeyboardButton(item)] for item in items]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ دسترسی ندارید.")
    buttons = [
        [KeyboardButton("🎲 شروع بازی")],
        [KeyboardButton("☕ سفارش کافه")],
        [KeyboardButton(✏️ ویرایش سفارش")],
        [KeyboardButton("⏹️ پایان بازی")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    user_states.pop(uid, None)
    await update.message.reply_text("گزینه‌ای را انتخاب کنید:", reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ دسترسی ندارید.")

    state = user_states.get(uid, {})

    # دکمه بازگشت
    if text == "بازگشت":
        user_states.pop(uid, None)
        await start(update, context)
        return

    # منوی اصلی
    if text == "🎲 شروع بازی":
        user_states[uid] = {'mode': 'game_start'}
        await update.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        return

    if text == "☕ سفارش کافه":
        user_states[uid] = {'mode': 'order_start'}
        await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        return

    if text == "✏️ ویرایش سفارش":
        # منوی انتخاب ویرایش: ویرایش سفارش یا تعداد بازیکنان
        buttons = [
            [KeyboardButton("ویرایش سفارشات")],
            [KeyboardButton("ویرایش تعداد بازیکنان")],
            [KeyboardButton("بازگشت")]
        ]
        user_states[uid] = {'mode': 'edit_menu'}
        await update.message.reply_text("کدام را می‌خواهید ویرایش کنید؟", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return

    if text == "⏹️ پایان بازی":
        # نمایش میزهایی که بازی دارند
        if not games:
            await update.message.reply_text("هیچ بازی فعالی وجود ندارد.")
            return
        user_states[uid] = {'mode': 'end_game_select_table'}
        await update.message.reply_text("برای پایان بازی میز را انتخاب کنید:", reply_markup=get_table_list())
        return

    # ویرایش منو
    if state.get('mode') == 'edit_menu':
        if text == "ویرایش سفارشات":
            if not orders:
                await update.message.reply_text("هیچ سفارشی وجود ندارد.")
                user_states.pop(uid, None)
                await start(update, context)
                return
            user_states[uid] = {'mode': 'edit_order_select_table'}
            await update.message.reply_text("میز را انتخاب کنید:", reply_markup=get_table_list())
            return

        if text == "ویرایش تعداد بازیکنان":
            if not games:
                await update.message.reply_text("هیچ بازی فعالی وجود ندارد.")
                user_states.pop(uid, None)
                await start(update, context)
                return
            user_states[uid] = {'mode': 'edit_game_select_table'}
            await update.message.reply_text("میز را انتخاب کنید:", reply_markup=get_table_list())
            return

        if text == "بازگشت":
            user_states.pop(uid, None)
            await start(update, context)
            return

    # انتخاب میز برای ویرایش سفارش
    if state.get('mode') == 'edit_order_select_table':
        if text in orders:
            user_states[uid] = {
                'mode': 'edit_order',
                'table': text,
                'items': orders[text].copy()
            }
            await update.message.reply_text(
                f"سفارش فعلی برای {text}:\n" + "، ".join(orders[text]) + 
                "\n\nآیتم جدید انتخاب کنید یا یکی را برای حذف بنویسید.\nبرای پایان و ثبت سفارش 'ثبت' را بزنید.\nبرای لغو 'بازگشت'."
            )
        else:
            await update.message.reply_text("میز نامعتبر است. دوباره تلاش کنید.")
        return

    # ویرایش سفارش: افزودن یا حذف آیتم
    if state.get('mode') == 'edit_order':
        if text == 'ثبت':
            orders[state['table']] = state['items']
            # ارسال پیام به کانال
            items_str = "، ".join(state['items']) if state['items'] else "(بدون آیتم)"
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"✏️ سفارش ویرایش شد:\n🪑 میز: {state['table']}\n"
                f"🍽 {items_str}\n👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ سفارش ثبت شد.")
            user_states.pop(uid, None)
            return
        # حذف آیتم اگر متن برابر نام آیتم باشد
        if text in state['items']:
            state['items'].remove(text)
            user_states[uid] = state
            await update.message.reply_text(f"آیتم «{text}» حذف شد.\nآیتم جدید انتخاب کنید یا 'ثبت' را بزنید.")
            return
        else:
            # افزودن آیتم جدید
            # برای افزودن آیتم‌ها باید دسته‌بندی‌ها را نمایش دهیم
            # ساده‌ترین راه: بازگشت به دسته‌بندی‌ها برای افزودن
            buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
            buttons.append([KeyboardButton("بازگشت")])
            user_states[uid]['mode'] = 'edit_order_add_items'
            user_states[uid]['items'] = state['items']
            await update.message.reply_text(
                f"آیتم «{text}» در سفارش وجود ندارد.\nبرای افزودن آیتم دسته‌بندی را انتخاب کنید:",
                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            )
            return

    # افزودن آیتم در ویرایش سفارش (نمایش دسته‌بندی‌ها و انتخاب آیتم)
    if state.get('mode') == 'edit_order_add_items':
        if text == "بازگشت":
            # بازگشت به حالت ویرایش سفارش اصلی
            user_states[uid]['mode'] = 'edit_order'
            await update.message.reply_text(
                "برای پایان و ثبت سفارش 'ثبت' را بزنید.\nآیتم جدید انتخاب کنید یا یکی را برای حذف بنویسید."
            )
            return
        if text in CATEGORY_LABELS.values():
            items = get_items_by_category(text)
            if not items:
                await update.message.reply_text("آیتمی برای این دسته‌بندی یافت نشد.")
            else:
                user_states[uid]['mode'] = 'edit_order_add_items_select'
                user_states[uid]['current_category'] = text
                await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu(items))
            return
        await update.message.reply_text("لطفاً از منو استفاده کنید یا بازگشت بزنید.")
        return

    if state.get('mode') == 'edit_order_add_items_select':
        if text == "بازگشت":
            user_states[uid]['mode'] = 'edit_order_add_items'
            buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
            buttons.append([KeyboardButton("بازگشت")])
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
            return
        # افزودن آیتم به لیست
        if 'items' not in user_states[uid]:
            user_states[uid]['items'] = []
        user_states[uid]['items'].append(text)
        user_states[uid]['mode'] = 'edit_order_add_items'
        await update.message.reply_text(f"«{text}» اضافه شد.\nدسته‌بندی را انتخاب کنید یا 'بازگشت'.")
        return

    # انتخاب میز برای ویرایش تعداد بازیکنان
    if state.get('mode') == 'edit_game_select_table':
        if text in games:
            game = games[text]
            user_states[uid] = {
                'mode': 'edit_game',
                'table': text,
                'players': game['players'],
                'start_time': game['start_time']
            }
            await update.message.reply_text(f"تعداد بازیکنان فعلی برای {text}: {game['players']}\nعدد جدید را وارد کنید یا 'بازگشت'.")
        else:
            await update.message.reply_text("میز نامعتبر است. دوباره تلاش کنید.")
        return

    # ویرایش تعداد بازیکنان بازی
    if state.get('mode') == 'edit_game':
        if text == "بازگشت":
            user_states.pop(uid, None)
            await start(update, context)
            return
        try:
            players = int(text)
            table = state['table']
            games[table]['players'] = players
            username_or_name = update.effective_user.username or update.effective_user.first_name
            start_time = games[table]['start_time']
            now = datetime.now().strftime("%H:%M")
            msg = (
                f"✏️ تعداد بازیکنان بازی ویرایش شد:\n🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ شروع بازی: {start_time}\n"
                f"⏰ ویرایش در: {now}\n"
                f"👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ تعداد بازیکنان بازی ویرایش شد.")
            user_states.pop(uid, None)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
        return

    # انتخاب میز برای پایان بازی
    if state.get('mode') == 'end_game_select_table':
        if text in games:
            now = datetime.now().strftime("%H:%M")
            table = text
            players = games[table]['players']
            start_time = games[table]['start_time']
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"⏹️ بازی پایان یافت:\n🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ شروع بازی: {start_time}\n"
                f"⏰ پایان بازی: {now}\n"
                f"👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            # حذف بازی از لیست فعال
            del games[table]
            await update.message.reply_text("✅ بازی با موفقیت پایان یافت.")
            user_states.pop(uid, None)
        else:
            await update.message.reply_text("میز نامعتبر است. دوباره تلاش کنید.")
        return

    # ثبت بازی جدید
    if state.get('mode') == 'game_start':
        if text.startswith("میز"):
            user_states[uid]['table'] = text
            await update.message.reply_text("تعداد نفرات؟")
            return
        try:
            players = int(text)
            table = state.get('table')
            if not table:
                await update.message.reply_text("لطفاً ابتدا میز را انتخاب کنید.")
                return
            now = datetime.now().strftime("%H:%M")
            games[table] = {
                'players': players,
                'start_time': now
            }
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"🎲 شروع بازی:\n🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ زمان: {now}\n"
                f"👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.")
            user_states.pop(uid, None)
            return
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
            return

    # ثبت سفارش جدید
    if state.get('mode') == 'order_start':
        if text.startswith("میز"):
            user_states[uid]['table'] = text
            user_states[uid]['items'] = []
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            return
        else:
            await update.message.reply_text("لطفاً یک میز معتبر انتخاب کنید.")
            return

    # انتخاب دسته‌بندی برای سفارش جدید
    if state.get('mode') == 'order_start' or state.get('mode') == 'order_select_category':
        if text in CATEGORY_LABELS.values():
            user_states[uid]['mode'] = 'order_select_item'
            user_states[uid]['current_category'] = text
            items = get_items_by_category(text)
            await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu(items))
            return

    # انتخاب آیتم برای سفارش جدید
    if state.get('mode') == 'order_select_item':
        if text == "ثبت سفارش":
            items_list = user_states[uid].get('items', [])
            if not items_list:
                await update.message.reply_text("❗ هیچ آیتمی انتخاب نشده است.")
                return
            table = user_states[uid].get('table', 'میز نامشخص')
            items_str = "، ".join(items_list)
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"📦 سفارش جدید:\n🪑 میز: {table}\n"
                f"🍽 {items_str}\n"
                f"👤 @{username_or_name}"
            )
            # ذخیره سفارش در حافظه
            orders[table] = items_list
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ سفارش ارسال شد.")
            user_states.pop(uid, None)
            return
        elif text == "بازگشت":
            user_states[uid]['mode'] = 'order_start'
            await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
            return
        else:
            # افزودن آیتم به لیست
            user_states[uid].setdefault('items', []).append(text)
            await update.message.reply_text(f"«{text}» اضافه شد.\nدسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            user_states[uid]['mode'] = 'order_start'
            return

    await update.message.reply_text("لطفاً از منو استفاده کنید یا 'بازگشت' بزنید.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()