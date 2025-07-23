import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from datetime import datetime
import pytz
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import get_table_menu, get_category_menu, get_item_menu_by_category

logging.basicConfig(level=logging.INFO)
user_states = {}

def now_tehran():
    utc_dt = datetime.utcnow()
    tehran_tz = pytz.timezone("Asia/Tehran")
    tehran_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(tehran_tz)
    return tehran_dt.strftime("%H:%M")  # فقط ساعت و دقیقه

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🎲 شروع بازی")],
        [KeyboardButton("☕ سفارش کافه")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    await update.message.reply_text(
        "گزینه‌ای را انتخاب کنید:", reply_markup=main_menu_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return

    if text == "🎲 شروع بازی":
        user_states[uid] = {"mode": "game"}
        await update.message.reply_text(
            "کدام میز؟", reply_markup=get_table_menu()
        )
        return

    if text == "☕ سفارش کافه":
        user_states[uid] = {"mode": "order"}
        await update.message.reply_text(
            "میز سفارش را انتخاب کنید:", reply_markup=get_table_menu()
        )
        return

    # اگر در حالت بازی هستیم و منتظر تعداد نفرات هستیم
    if uid in user_states and user_states[uid]["mode"] == "game" and "players" not in user_states[uid]:
        try:
            players = int(text)
            user_states[uid]["players"] = players
            now = now_tehran()
            state = user_states[uid]

            msg = (
                f"🎲 شروع بازی:\n"
                f"🪑 میز: {state['table']}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ ساعت شروع: {now}\n"
                f"👤 @{update.effective_user.username or update.effective_user.first_name}"
            )
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)
            await update.message.reply_text("✅ بازی ثبت شد.", reply_markup=main_menu_keyboard())
            user_states.pop(uid)
        except ValueError:
            await update.message.reply_text("لطفاً عدد وارد کنید.")
        return

    await update.message.reply_text("لطفاً از منوی پایین گزینه‌ای انتخاب کنید.")

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if uid not in ALLOWED_USER_IDS:
        await query.message.reply_text("⛔ دسترسی ندارید.")
        return

    data = query.data
    state = user_states.setdefault(uid, {})

    if data.startswith("table_"):
        table_key = data.split("_", 1)[1]
        table_name = {
            "free": "میز آزاد",
            "ps": "PS",
            "wheel": "فرمون",
        }.get(table_key, f"میز {table_key}")
        state["table"] = table_name

        if state["mode"] == "game":
            await query.message.reply_text("تعداد نفرات؟")
        else:
            state["items"] = []
            state.setdefault("orders", [])
            await query.message.reply_text(
                "🍽 دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu()
            )
        return

    elif data.startswith("cat_"):
        cat_key = data.split("_", 1)[1]
        state["current_category"] = cat_key
        await query.message.reply_text(
            "آیتم را انتخاب کنید:", reply_markup=get_item_menu_by_category(cat_key)
        )
        return

    elif data.startswith("item_"):
        item_name = data.split("_", 1)[1]
        state.setdefault("items", []).append(item_name)
        await query.message.reply_text(
            f"«{item_name}» اضافه شد.\nدسته بعدی را انتخاب کنید:",
            reply_markup=get_category_menu(),
        )
        return

    elif data == "back_to_categories":
        await query.message.reply_text(
            "دسته‌بندی را انتخاب کنید:", reply_markup=get_category_menu()
        )
        return

    elif data == "done_order":
        if "items" not in state or len(state["items"]) == 0:
            await query.message.reply_text("❗ سفارشی ثبت نشده.")
            return

        # اضافه کردن سفارش جدید به لیست سفارشات میز
        orders = state.setdefault("orders", [])
        orders.append(state["items"][:])  # کپی آیتم‌ها
        state["items"].clear()

        # ساخت پیام با تمام سفارش‌های میز
        orders_text = "\n\n".join(
            [f"سفارش {i+1}:\n" + "، ".join(order) for i, order in enumerate(orders)]
        )
        msg = (
            f"📦 سفارش‌های میز {state['table']}:\n\n"
            f"{orders_text}\n\n"
            f"👤 @{query.from_user.username or query.from_user.first_name}\n"
            f"⏰ ساعت: {now_tehran()}"
        )
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)

        # منوی ویرایش سفارش‌ها یا ادامه سفارش جدید
        keyboard = [
            [InlineKeyboardButton("ادامه سفارش", callback_data="back_to_categories")],
            [InlineKeyboardButton("نمایش سفارش‌ها", callback_data="show_orders")],
            [InlineKeyboardButton("حذف سفارش", callback_data="delete_order")],
        ]
        await query.message.reply_text(
            "✅ سفارش ثبت شد.", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data == "show_orders":
        orders = state.get("orders", [])
        if not orders:
            await query.message.reply_text("❗ سفارشی وجود ندارد.")
            return
        text = "\n\n".join(
            [f"{i+1}. " + "، ".join(order) for i, order in enumerate(orders)]
        )
        await query.message.reply_text(f"📋 سفارش‌های میز {state['table']}:\n\n{text}")
        return

    elif data == "delete_order":
        orders = state.get("orders", [])
        if not orders:
            await query.message.reply_text("❗ سفارشی برای حذف وجود ندارد.")
            return
        # حذف آخرین سفارش
        removed = orders.pop()
        await query.message.reply_text(
            f"سفارش زیر حذف شد:\n" + "، ".join(removed)
        )
        return

    else:
        await query.message.reply_text("گزینه نامعتبر است.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_menu))
    app.run_polling()

if __name__ == "__main__":
    main()