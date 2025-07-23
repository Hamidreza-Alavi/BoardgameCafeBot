import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timezone, timedelta
import json
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID

logging.basicConfig(level=logging.INFO)

user_states = {}

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

TABLES = [f"میز {i}" for i in range(1, 17)] + ["میز آزاد", "PS", "فرمون"]

def get_table_menu():
    buttons = [[KeyboardButton(t)] for t in TABLES]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_category_menu():
    buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_item_menu_by_category(cat_key):
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
    buttons = [[KeyboardButton(item)] for item in items.get(cat_key, [])]
    buttons.append([
        KeyboardButton("✅ پایان سفارش"),
        KeyboardButton("بازگشت")
    ])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def iran_time_now():
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    iran_offset = timedelta(hours=3, minutes=30)
    iran_time = utc_now + iran_offset
    return iran_time.strftime("%H:%M")

def main_menu_keyboard():
    buttons = [
        [KeyboardButton("🎲 شروع بازی")],
        [KeyboardButton("☕ سفارش کافه")],
        [KeyboardButton("✏️ ویرایش سفارش‌ها")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    await update.message.reply_text(
        "لطفاً از منوی پایین گزینه‌ای انتخاب کنید.",
        reply_markup=main_menu_keyboard()
    )
    user_states.pop(uid, None)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = user_states.get(uid)

    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return

    if text == "بازگشت":
        user_states.pop(uid, None)
        await update.message.reply_text(
            "به منوی اصلی برگشتی.",
            reply_markup=main_menu_keyboard()
        )
        return

    if not state:
        if text == "🎲 شروع بازی":
            user_states[uid] = {'mode': 'game'}
            await update.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        elif text == "☕ سفارش کافه":
            user_states[uid] = {'mode': 'order'}
            await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        elif text == "✏️ ویرایش سفارش‌ها":
            await update.message.reply_text("⚠️ قابلیت ویرایش هنوز فعال نشده.", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("لطفا از منو گزینه‌ای انتخاب کنید.", reply_markup=main_menu_keyboard())
        return

    if state['mode'] == 'order':
        if 'table' not in state:
            if text in TABLES:
                state['table'] = text
                state['items'] = []
                await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            else:
                await update.message.reply_text("لطفاً یک میز معتبر انتخاب کنید.", reply_markup=get_table_menu())
            return

        if 'current_category' not in state:
            if text in CATEGORY_LABELS.values():
                # پیدا کردن کلید دسته بر اساس مقدار
                cat_key = next((k for k,v in CATEGORY_LABELS.items() if v == text), None)
                if cat_key:
                    state['current_category'] = cat_key
                    await update.message.reply_text(f"آیتم‌ها را انتخاب کنید ({text}):", reply_markup=get_item_menu_by_category(cat_key))
                else:
                    await update.message.reply_text("دسته‌بندی نامعتبر است.", reply_markup=get_category_menu())
            else:
                await update.message.reply_text("لطفاً یک دسته‌بندی معتبر انتخاب کنید.", reply_markup=get_category_menu())
            return

        if text == "✅ پایان سفارش":
            if not state['items']:
                await update.message.reply_text("❗ سفارش شما خالی است.", reply_markup=get_category_menu())
                return
            items_str = "، ".join(state['items'])
            iran_time = iran_time_now()
            msg = (
                f"📦 سفارش جدید:\n🪑 میز: {state['table']}\n"
                f"🍽 {items_str}\n⏰ ساعت سفارش: {iran_time}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ سفارش ثبت و ارسال شد.", reply_markup=main_menu_keyboard())
            user_states.pop(uid)
            return

        if text == "بازگشت":
            state.pop('current_category', None)
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            return

        if 'current_category' in state:
            state['items'].append(text)
            await update.message.reply_text(f"«{text}» اضافه شد.\nدسته‌بندی بعدی را انتخاب کنید:", reply_markup=get_category_menu())
            return

    if state['mode'] == 'game':
        if 'table' not in state:
            if text in TABLES:
                state['table'] = text
                await update.message.reply_text("تعداد نفرات؟ (عدد وارد کنید)", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
            else:
                await update.message.reply_text("لطفاً یک میز معتبر انتخاب کنید.", reply_markup=get_table_menu())
            return
        else:
            try:
                players = int(text)
                state['players'] = players
                iran_time = iran_time_now()
                msg = (
                    f"🎲 شروع بازی:\n🪑 میز: {state['table']}\n"
                    f"👥 تعداد نفرات: {players}\n⏰ ساعت شروع: {iran_time}\n"
                    f"👤 @{update.effective_user.username or update.effective_user.first_name}"
                )
                await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
                await update.message.reply_text("✅ بازی ثبت شد.", reply_markup=main_menu_keyboard())
                user_states.pop(uid)
            except ValueError:
                await update.message.reply_text("لطفا فقط عدد وارد کنید.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
            return

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()