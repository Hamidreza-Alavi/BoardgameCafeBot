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
    filters,
    ContextTypes,
)
from datetime import datetime
import pytz
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID
from menu import CATEGORY_LABELS, ITEMS_BY_CATEGORY  # فرض بر این که این دیکشنری‌ها داری

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
        [KeyboardButton("✏️ ویرایش سفارش‌ها")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True)

def get_table_keyboard():
    # ۱ تا ۱۶ + میز آزاد و PS و فرمون
    buttons = [ [KeyboardButton(f"میز {i}")] for i in range(1, 17) ]
    buttons += [[KeyboardButton("میز آزاد")], [KeyboardButton("PS")], [KeyboardButton("فرمون")]]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_category_keyboard():
    buttons = [[KeyboardButton(label)] for label in CATEGORY_LABELS.values()]
    buttons.append([KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_items_keyboard(category_key, user_items):
    items = ITEMS_BY_CATEGORY.get(category_key, [])
    buttons = [[KeyboardButton(item)] for item in items]
    # دکمه‌های پایان و بازگشت
    buttons.append([KeyboardButton("✅ پایان سفارش"), KeyboardButton("بازگشت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    await update.message.reply_text(
        "گزینه‌ای را انتخاب کنید:", reply_markup=main_menu_keyboard()
    )
    # پاک کردن هر state قبلی
    if uid in user_states:
        user_states.pop(uid)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return

    # اگر کاربر در حال انجام کاری است:
    if uid in user_states:
        state = user_states[uid]

        if text == "بازگشت":
            # برگرد به منوی اصلی
            user_states.pop(uid)
            await update.message.reply_text("بازگشت به منوی اصلی:", reply_markup=main_menu_keyboard())
            return

        mode = state.get("mode")

        # حالت شروع بازی
        if mode == "game":
            if "table" not in state:
                # انتظار میز
                if text.startswith("میز "):
                    state["table"] = text
                    await update.message.reply_text("تعداد نفرات؟", reply_markup=back_keyboard())
                else:
                    await update.message.reply_text("لطفا یک میز معتبر انتخاب کنید.", reply_markup=get_table_keyboard())
                return
            if "players" not in state:
                # انتظار تعداد نفرات
                try:
                    players = int(text)
                    state["players"] = players
                    now = now_tehran()
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
                    await update.message.reply_text("لطفاً عدد وارد کنید.", reply_markup=back_keyboard())
                return

        # حالت سفارش کافه
        elif mode == "order":
            if "table" not in state:
                # انتظار میز
                valid_tables = [f"میز {i}" for i in range(1,17)] + ["میز آزاد", "PS", "فرمون"]
                if text in valid_tables:
                    state["table"] = text
                    state.setdefault("orders", [])
                    state["items"] = []
                    await update.message.reply_text("🍽 دسته‌بندی را انتخاب کنید:", reply_markup=get_category_keyboard())
                else:
                    await update.message.reply_text("لطفاً یک میز معتبر انتخاب کنید.", reply_markup=get_table_keyboard())
                return

            if "current_category" not in state:
                # انتظار انتخاب دسته‌بندی
                if text in CATEGORY_LABELS.values():
                    # پیدا کردن کلید دسته‌بندی از روی مقدار
                    cat_key = [k for k,v in CATEGORY_LABELS.items() if v == text][0]
                    state["current_category"] = cat_key
                    await update.message.reply_text("آیتم را انتخاب کنید:", reply_markup=get_items_keyboard(cat_key, state["items"]))
                else:
                    await update.message.reply_text("لطفاً دسته‌بندی را انتخاب کنید.", reply_markup=get_category_keyboard())
                return

            else:
                # انتظار انتخاب آیتم یا پایان یا بازگشت
                if text == "بازگشت":
                    # حذف دسته‌بندی انتخاب شده و بازگشت به دسته‌ها
                    state.pop("current_category", None)
                    await update.message.reply_text("دسته‌بندی را انتخاب کنید:", reply_markup=get_category_keyboard())
                    return
                elif text == "✅ پایان سفارش":
                    if len(state["items"]) == 0:
                        await update.message.reply_text("❗ سفارشی ثبت نشده.", reply_markup=get_category_keyboard())
                        return
                    # اضافه کردن سفارش جدید
                    state["orders"].append(state["items"][:])
                    state["items"].clear()

                    orders_text = "\n\n".join(
                        [f"سفارش {i+1}:\n" + "، ".join(order) for i, order in enumerate(state["orders"])]
                    )
                    msg = (
                        f"📦 سفارش‌های میز {state['table']}:\n\n"
                        f"{orders_text}\n\n"
                        f"👤 @{update.message.from_user.username or update.message.from_user.first_name}\n"
                        f"⏰ ساعت: {now_tehran()}"
                    )
                    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg)

                    await update.message.reply_text(
                        "✅ سفارش ثبت شد.",
                        reply_markup=ReplyKeyboardMarkup(
                            [
                                [KeyboardButton("ادامه سفارش")],
                                [KeyboardButton("بازگشت")],
                            ],
                            resize_keyboard=True,
                        ),
                    )
                    return
                else:
                    # انتخاب آیتم
                    items = ITEMS_BY_CATEGORY.get(state["current_category"], [])
                    if text in items:
                        state["items"].append(text)
                        await update.message.reply_text(
                            f"«{text}» اضافه شد.\nدسته بعدی را انتخاب کنید:",
                            reply_markup=get_category_keyboard(),
                        )
                    else:
                        await update.message.reply_text(
                            "لطفاً آیتم معتبر انتخاب کنید.", reply_markup=get_items_keyboard(state["current_category"], state["items"])
                        )
                    return

        # حالت ویرایش سفارش‌ها
        elif mode == "edit":
            orders = state.get("orders", [])
            if text == "بازگشت":
                user_states.pop(uid)
                await update.message.reply_text("بازگشت به منوی اصلی:", reply_markup=main_menu_keyboard())
                return
            elif text == "نمایش سفارش‌ها":
                if not orders:
                    await update.message.reply_text("❗ سفارشی وجود ندارد.", reply_markup=main_menu_keyboard())
                    return
                text_orders = "\n\n".join(
                    [f"{i+1}. " + "، ".join(order) for i, order in enumerate(orders)]
                )
                await update.message.reply_text(f"📋 سفارش‌های میز:\n\n{text_orders}", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
                return
            elif text == "حذف آخرین سفارش":
                if not orders:
                    await update.message.reply_text("❗ سفارشی برای حذف وجود ندارد.", reply_markup=main_menu_keyboard())
                    return
                removed = orders.pop()
                await update.message.reply_text(f"سفارش حذف شد:\n" + "، ".join(removed), reply_markup=ReplyKeyboardMarkup([[KeyboardButton("بازگشت")]], resize_keyboard=True))
                return
            elif text == "ادامه سفارش":
                state["mode"] = "order"
                state["items"] = []
                await update.message.reply_text("میز را انتخاب کنید:", reply_markup=get_table_keyboard())
                return
            else:
                await update.message.reply_text("گزینه نامعتبر است.", reply_markup=main_menu_keyboard())
                return

    else:
        # کاربر تازه وارد یا خارج از حالت
        if text == "🎲 شروع بازی":
            user_states[uid] = {"mode": "game"}
            await update.message.reply_text("میز را انتخاب کنید:", reply_markup=get_table_keyboard())
            return
        elif text == "☕ سفارش کافه":
            user_states[uid] = {"mode": "order"}
            await update.message.reply_text("میز سفارش را انتخاب کنید:", reply_markup=get_table_keyboard())
            return
        elif text == "✏️ ویرایش سفارش‌ها":
            user_states[uid] = {"mode": "edit"}
            await update.message.reply_text(
                "گزینه را انتخاب کنید:",
                reply_markup=ReplyKeyboardMarkup(
                    [
                        [KeyboardButton("نمایش سفارش‌ها")],
                        [KeyboardButton("حذف آخرین سفارش")],
                        [KeyboardButton("ادامه سفارش")],
                        [KeyboardButton("بازگشت")],
                    ],
                    resize_keyboard=True,
                ),
            )
            return
        else:
            await update.message.reply_text(
                "لطفاً از منوی پایین گزینه‌ای انتخاب کنید.", reply_markup=main_menu_keyboard()
            )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()