import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
import json

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
    buttons.append([KeyboardButton("✅ثبت سفارش")])
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_items_by_category(cat_label):
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
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
        [KeyboardButton("✏️ ویرایش سفارش")]
    ]
    keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("گزینه‌ای را انتخاب کنید:", reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    if uid not in ALLOWED_USER_IDS:
        return await update.message.reply_text("⛔ دسترسی ندارید.")

    state = user_states.get(uid, {})

    if text == "بازگشت":
        user_states.pop(uid, None)
        await start(update, context)
        return

    if text == "🎲 شروع بازی":
        user_states[uid] = {'mode': 'game'}
        await update.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        return

    if text == "☕ سفارش کافه":
        user_states[uid] = {'mode': 'order'}
        await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        return

    if text == "✏️ ویرایش سفارش":
        await update.message.reply_text("این قابلیت هنوز آماده نیست.")
        return

    if text.startswith("میز"):
        if not state or 'mode' not in state:
            return await update.message.reply_text("لطفاً ابتدا یکی از گزینه‌های اصلی را انتخاب کنید.")
        state['table'] = text
        user_states[uid] = state

        if state['mode'] == 'game':
            await update.message.reply_text("تعداد نفرات؟")
        else:
            state['items'] = []
            user_states[uid] = state
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    if state.get('mode') == 'order':
        if text == "ثبت سفارش":
            if 'items' not in state or not state['items']:
                return await update.message.reply_text("❗ هیچ آیتمی انتخاب نشده است.")
            items_str = "، ".join(state['items'])
            table = state.get('table', 'میز نامشخص')
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"📦 سفارش جدید\n🪑 میز: {table}\n"
                f"🍽 {items_str}\n👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ سفارش ارسال شد.")
            user_states.pop(uid, None)
            return

        if text in CATEGORY_LABELS.values():
            items = get_items_by_category(text)
            if not items:
                await update.message.reply_text("آیتمی برای این دسته‌بندی یافت نشد.")
            else:
                user_states[uid]['current_category'] = text
                await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu(items))
            return

        if 'current_category' in state:
            items = get_items_by_category(state['current_category'])
            if text in items:
                user_states[uid].setdefault('items', []).append(text)
                await update.message.reply_text(f"«{text}» اضافه شد.\nدسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
                return

    if state.get('mode') == 'game' and 'players' not in state:
        try:
            players = int(text)
            state['players'] = players
            user_states[uid] = state

            now = datetime.now().strftime("%H:%M")
            table = state.get('table', 'میز نامشخص')
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"🎲 شروع بازی\n🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n⏰ زمان: {now}\n"
                f"👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.")
            user_states.pop(uid, None)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
        return
    await update.message.reply_text("لطفاً از منو استفاده کنید یا بازگشت بزنید.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()