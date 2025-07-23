import json
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from datetime import datetime
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID

logging.basicConfig(level=logging.INFO)

user_states = {}
orders = {}  # ذخیره سفارش‌ها در حافظه
games = {}   # ذخیره بازی‌ها در حافظه

# بارگذاری دسته‌بندی‌ها و آیتم‌ها از فایل JSON
with open("menu.json", encoding="utf-8") as f:
    menu_data = json.load(f)

CATEGORY_LABELS = menu_data.get("categories", {})
ITEMS = menu_data.get("items", {})

def get_table_menu():
    buttons = [[KeyboardButton(f"میز {i}")] for i in range(1, 17)]
    buttons += [[KeyboardButton(label)] for label in ("میز آزاد", "PS", "فرمون")]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_category_menu():
    buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
    buttons.append([KeyboardButton("ثبت سفارش")])
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_items_by_category(cat_label):
    # پیدا کردن کلید دسته‌بندی از روی مقدار
    key = None
    for k, v in CATEGORY_LABELS.items():
        if v == cat_label:
            key = k
            break
    if key:
        return ITEMS.get(key, [])
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
    user_states.pop(uid, None)  # پاک کردن وضعیت قبلی

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
        user_states[uid] = {'mode': 'game_start'}
        await update.message.reply_text("کدام میز؟", reply_markup=get_table_menu())
        return

    if text == "☕ سفارش کافه":
        user_states[uid] = {'mode': 'order_start'}
        await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_menu())
        return

    if text == "✏️ ویرایش سفارش":
        await update.message.reply_text("این قابلیت هنوز آماده نیست.")
        return

    # انتخاب میز
    if text.startswith("میز") or text in ("میز آزاد", "PS", "فرمون"):
        if not state or 'mode' not in state:
            return await update.message.reply_text("لطفاً ابتدا یکی از گزینه‌های اصلی را انتخاب کنید.")
        state['table'] = text
        user_states[uid] = state

        if state['mode'] == 'game_start':
            await update.message.reply_text("تعداد نفرات؟")
        elif state['mode'] == 'order_start':
            state['items'] = []
            user_states[uid] = state
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
        return

    # ثبت تعداد نفرات بازی
    if state.get('mode') == 'game_start' and 'players' not in state:
        try:
            players = int(text)
            table = state.get('table')
            games[table] = {'players': players}
            username_or_name = update.effective_user.username or update.effective_user.first_name
            now = datetime.now().strftime("%H:%M")
            msg = (
                f"🎲 شروع بازی\n"
                f"🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ زمان: {now}\n"
                f"👤 @{username_or_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.")
            user_states.pop(uid, None)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
        return

    # ثبت سفارش - دسته بندی
    if state.get('mode') == 'order_start':
        if text in CATEGORY_LABELS.values():
            user_states[uid]['current_category'] = text
            items = get_items_by_category(text)
            if not items:
                await update.message.reply_text("آیتمی برای این دسته‌بندی یافت نشد.")
            else:
                await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_item_menu(items))
            return
        elif text == "ثبت سفارش":
            items_list = state.get('items', [])
            if not items_list:
                await update.message.reply_text("❗ هیچ آیتمی انتخاب نشده است.")
                return
            table = state.get('table', 'میز نامشخص')
            items_str = "، ".join(items_list)
            username_or_name = update.effective_user.username or update.effective_user.first_name
            msg = (
                f"📦 سفارش جدید\n"
                f"🪑 میز: {table}\n"
                f"🍽 {items_str}\n"
                f"👤 @{username_or_name}"
            )
            # ذخیره سفارش در حافظه (می‌تونی اینجا سفارش‌ها رو در دیتابیس ذخیره کنی)
            orders[table] = items_list
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ سفارش ارسال شد.")
            user_states.pop(uid, None)
            return
        else:
            await update.message.reply_text("لطفاً از منو استفاده کنید یا بازگشت بزنید.")
            return

    # ثبت سفارش - انتخاب آیتم
    if state.get('mode') == 'order_start' and 'current_category' in state:
        category = state['current_category']
        items = get_items_by_category(category)
        if text in items:
            user_states[uid].setdefault('items', []).append(text)
            await update.message.reply_text(f"«{text}» اضافه شد.\nدسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            return
        elif text == "بازگشت":
            user_states[uid].pop('current_category', None)
            await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu())
            return
        else:
            await update.message.reply_text("لطفاً از منو استفاده کنید یا بازگشت بزنید.")
            return

    await update.message.reply_text("لطفاً از منو استفاده کنید یا بازگشت بزنید.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()