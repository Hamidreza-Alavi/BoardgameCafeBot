import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import pytz

from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID

# دسته‌بندی‌ها و منوها
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

user_states = {}
logging.basicConfig(level=logging.INFO)

# تابع برای گرفتن زمان ایران به صورت ساعت و دقیقه
def iran_time_now():
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz).strftime("%H:%M")

# کیبوردها
def main_menu_keyboard():
    buttons = [
        [KeyboardButton("🎲 شروع بازی")],
        [KeyboardButton("☕ سفارش کافه")],
        [KeyboardButton("✏️ ویرایش سفارش‌ها")],
        [KeyboardButton("📨 ثبت سفارش")]
    ]
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
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_item_menu_by_category(cat_key):
    import json
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
    buttons = [[KeyboardButton(item)] for item in items.get(cat_key, [])]
    buttons.append([
        KeyboardButton("✅ پایان سفارش"),
        KeyboardButton("بازگشت")
    ])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# هندل شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ دسترسی ندارید.")
    await update.message.reply_text("به ربات خوش آمدید! گزینه‌ای انتخاب کنید:", reply_markup=main_menu_keyboard())

# ثبت سفارش
async def handle_order_submission(update, context, uid):
    state = user_states.get(uid)
    if not state or state.get('mode') != 'order' or not state.get('items'):
        await update.message.reply_text("❗ سفارشی برای ثبت وجود ندارد.", reply_markup=main_menu_keyboard())
        return
    items_str = "، ".join(state['items'])
    time_str = iran_time_now()
    msg = (
        f"📦 سفارش جدید:\n🪑 میز: {state['table']}\n"
        f"🍽 {items_str}\n⏰ ساعت سفارش: {time_str}\n"
        f"👤 @{update.effective_user.username or update.effective_user.first_name}"
    )
    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
    await update.message.reply_text("✅ سفارش ثبت و ارسال شد.", reply_markup=main_menu_keyboard())
    user_states.pop(uid)

# هندل پیام‌های متنی
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    if uid not in ALLOWED_USER_IDS:
        return

    state = user_states.get(uid)

    # اگر در حالت خاص نیستیم (شروع بازی یا سفارش)
    if not state:
        if text == "🎲 شروع بازی":
            user_states[uid] = {'mode': 'game'}
            await update.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        elif text == "☕ سفارش کافه":
            user_states[uid] = {'mode': 'order'}
            await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        elif text == "✏️ ویرایش سفارش‌ها":
            await update.message.reply_text("⚠️ قابلیت ویرایش هنوز فعال نشده.", reply_markup=main_menu_keyboard())
        elif text == "📨 ثبت سفارش":
            await handle_order_submission(update, context, uid)
        else:
            await update.message.reply_text("لطفا از منو گزینه‌ای انتخاب کنید.", reply_markup=main_menu_keyboard())
        return

    # در حالت انتخاب میز
    if text.startswith("میز") or text in ["میز آزاد", "PS", "فرمون"]:
        user_states[uid]['table'] = text
        if state['mode'] == 'game':
            await update.message.reply_text("تعداد نفرات؟", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
        else:
            user_states[uid]['items'] = []
            await update.message.reply_text("🍽 دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    # در حالت انتخاب دسته‌بندی
    if state['mode'] == 'order' and text in CATEGORY_LABELS.values():
        # برگردوندن کلید دسته‌بندی از روی مقدار
        cat_key = None
        for k, v in CATEGORY_LABELS.items():
            if v == text:
                cat_key = k
                break
        if cat_key:
            user_states[uid]['current_category'] = cat_key
            await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu_by_category(cat_key))
        return

    # در حالت انتخاب آیتم
    if state['mode'] == 'order' and 'current_category' in state:
        import json
        with open("items.json", encoding="utf-8") as f:
            items = json.load(f)
        cat_key = state['current_category']
        if text in items.get(cat_key, []):
            user_states[uid].setdefault('items', []).append(text)
            await update.message.reply_text(f"«{text}» اضافه شد.\nدسته بعدی را انتخاب کنید:", reply_markup=get_category_menu())
            return
        elif text == "✅ پایان سفارش":
            await handle_order_submission(update, context, uid)
            return
        elif text == "بازگشت":
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            return

    # حالت تعداد نفرات بازی
    if state['mode'] == 'game' and 'players' not in state:
        if text == "بازگشت":
            user_states.pop(uid)
            await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=main_menu_keyboard())
            return
        try:
            players = int(text)
            state['players'] = players
            time_str = iran_time_now()
            msg = (
                f"🎲 شروع بازی:\n🪑 میز: {state['table']}\n"
                f"👥 تعداد نفرات: {players}\n⏰ ساعت شروع: {time_str}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.", reply_markup=main_menu_keyboard())
            user_states.pop(uid)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
        return

    # دکمه بازگشت کلی
    if text == "بازگشت":
        user_states.pop(uid, None)
        await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=main_menu_keyboard())
        return

    # اگر ورودی نامفهوم بود
    await update.message.reply_text("لطفا از منو گزینه‌ای انتخاب کنید.", reply_markup=main_menu_keyboard())

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()