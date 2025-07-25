import json
import logging
import pytz
import re
import math
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID

# --- Basic Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Bot Class ---
class CafeBot:
    def __init__(self):
        self.user_states = {}
        self.active_orders = {}
        self.active_games = {}
        self.category_labels = {
            "COFFEE_HOT": "☕ قهوه داغ", "COFFEE_COLD": "🧊 قهوه سرد", "HOT_DRINKS_NON_COFFEE": "🍵 نوشیدنی داغ بدون قهوه",
            "TEA": "🍃 چای", "HERBAL_TEA": "🌿 دمنوش", "MILKSHAKE": "🥤 میلک‌شیک", "JUICE": "🍹 آب‌میوه",
            "MOCKTAIL": "🍸 ماکتیل", "ICE_CREAM": "🍨 بستنی", "CAKE": "🍰 کیک", "FOOD": "🍕 غذا",
            "ADDITIVES": "🧂 افزودنی", "WATER": "💧 آب"
        }
        self.load_menu()

    def load_menu(self):
        """Loads menu items and prices from items.json."""
        try:
            with open("items.json", encoding="utf-8") as f:
                data = json.load(f)
            self.items = {}
            self.prices = {}
            for category, item_list in data.items():
                self.items[category] = [item['name'] for item in item_list]
                for item in item_list:
                    self.prices[item['name']] = item['price']
            logger.info("Menu and prices loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading items.json: {e}")
            self.items, self.prices = {}, {}

    def check_user_access(self, user_id: int) -> bool:
        return user_id in ALLOWED_USER_IDS

    def get_iran_time(self) -> str:
        return datetime.now(pytz.timezone("Asia/Tehran")).strftime("%H:%M")

    def get_user_info(self, user) -> str:
        return user.username or user.first_name or "ناشناس"

    def clean_item_name(self, item_name: str) -> str:
        return re.sub(r'\s+', ' ', item_name).strip()

    # --- Menu Creation ---
    def create_main_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("🎲 شروع بازی"), KeyboardButton("🏁 پایان بازی")],
            [KeyboardButton("👥 مدیریت بازیکنان"), KeyboardButton("☕ سفارش کافه")],
            [KeyboardButton("📝 مدیریت سفارش"), KeyboardButton("💰 تسویه حساب")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_player_management_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("➕ افزودن بازیکن"), KeyboardButton("➖ کاهش بازیکن")],
            [KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_order_management_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("➕ افزودن به سفارش"), KeyboardButton("✏️ ویرایش سفارش")],
            [KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_table_menu(self, lock_for_games=False) -> ReplyKeyboardMarkup:
        buttons = []
        all_tables = [f"میز {i}" for i in range(1, 17)] + ["میز آزاد", "PS", "فرمون"]
        table_rows = [all_tables[i:i+4] for i in range(0, 16, 4)]
        table_rows.append(all_tables[16:18])
        table_rows.append([all_tables[18]])
        for row_items in table_rows:
            row = [KeyboardButton(f"🔒 {name}" if lock_for_games and name in self.active_games else name) for name in row_items]
            buttons.append(row)
        buttons.append([KeyboardButton("بازگشت")])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_active_tables_menu(self, table_type: str) -> ReplyKeyboardMarkup:
        active_tables = []
        if table_type == "order":
            active_tables = list(self.active_orders.keys())
        elif table_type == "game":
            active_tables = [tbl for tbl, info in self.active_games.items() if 'end_time' not in info]
        elif table_type == "player_management":
             active_tables = [tbl for tbl, info in self.active_games.items() if 'end_time' not in info]
        elif table_type == "checkout":
            active_tables = [tbl for tbl, info in self.active_games.items() if 'end_time' in info]

        if not active_tables:
            return ReplyKeyboardMarkup([[KeyboardButton("هیچ میز فعالی موجود نیست")], [KeyboardButton("بازگشت")]], resize_keyboard=True)
        
        buttons = [active_tables[i:i+2] for i in range(0, len(active_tables), 2)]
        buttons.append([KeyboardButton("بازگشت")])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_category_menu(self) -> ReplyKeyboardMarkup:
        categories = list(self.category_labels.values())
        buttons = [categories[i:i+2] for i in range(0, len(categories), 2)]
        buttons.extend([[KeyboardButton("ثبت سفارش")], [KeyboardButton("بازگشت")]])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_items_menu(self, items: list) -> ReplyKeyboardMarkup:
        buttons = [items[i:i+2] for i in range(0, len(items), 2)]
        buttons.append([KeyboardButton("بازگشت")])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    # --- Core Logic Functions ---
    def get_items_by_category(self, category_label: str) -> list:
        for key, label in self.category_labels.items():
            if label == category_label:
                return self.items.get(key, [])
        return []

    def clear_user_state(self, user_id: int):
        self.user_states.pop(user_id, None)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_user_access(update.effective_user.id):
            await update.message.reply_text("⛔ دسترسی ندارید.")
            return
        self.clear_user_state(update.effective_user.id)
        await update.message.reply_text("🎮 خوش آمدید!\nگزینه‌ای را انتخاب کنید:", reply_markup=self.create_main_menu())

    def calculate_bill(self, table_name: str) -> dict:
        game_info = self.active_games.get(table_name, {})
        order_info = self.active_orders.get(table_name, {})
        
        game_cost, total_players, duration_minutes, chargeable_multiplier = 0, 0, 0, 0.0

        if game_info and 'end_time' in game_info:
            start_dt = datetime.strptime(game_info['game_start'], "%H:%M")
            end_dt = datetime.strptime(game_info['end_time'], "%H:%M")
            if end_dt < start_dt: end_dt += timedelta(days=1)
            duration = end_dt - start_dt
            duration_minutes = duration.total_seconds() / 60
            total_players = sum(g['count'] for g in game_info['player_groups'] if g['count'] > 0)

            if duration_minutes > 0:
                effective_minutes = max(0, duration_minutes - 10)
                chargeable_half_hours = math.ceil(effective_minutes / 30)
                chargeable_multiplier = max(1.0, chargeable_half_hours * 0.5)
            
            game_cost = chargeable_multiplier * 75000 * total_players

        order_cost = 0
        order_items_summary = {}
        if order_info:
            for item in order_info.get('items', []):
                price = self.prices.get(self.clean_item_name(item), 0)
                if price > 0:
                    order_cost += price
                    order_items_summary[item] = order_items_summary.get(item, 0) + 1
        
        return {"game_cost": game_cost, "order_cost": order_cost, "total_cost": game_cost + order_cost, "total_players": total_players,
                "duration": int(duration_minutes), "order_summary": order_items_summary, "chargeable_hours": chargeable_multiplier}
    
    # --- Callback and Flow Handlers ---
    async def handle_settlement_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        table_name = query.data.split('_')[1]
        self.active_games.pop(table_name, None)
        self.active_orders.pop(table_name, None)
        logger.info(f"Table {table_name} settled by {self.get_user_info(query.from_user)}.")
        await query.edit_message_text(text=f"{query.message.text}\n\n---\n✅ **تسویه شد.** میز {table_name} اکنون آزاد است.", parse_mode='Markdown')
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ تسویه میز {table_name} انجام و میز خالی شد.", reply_markup=self.create_main_menu())

    # --- Main Message Handler ---
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            if not self.check_user_access(user_id):
                await update.message.reply_text("⛔ دسترسی ندارید."); return

            text = update.message.text.strip()
            state = self.user_states.get(user_id, {})
            mode = state.get('mode')

            if text == "بازگشت":
                self.clear_user_state(user_id); await self.start_command(update, context); return
            if text == "هیچ میز فعالی موجود نیست":
                await update.message.reply_text("❗ عملیات امکان‌پذیر نیست.", reply_markup=self.create_main_menu()); self.clear_user_state(user_id); return

            # --- Main Menu Router ---
            if not mode:
                if text == "🎲 شروع بازی": self.user_states[user_id] = {'mode': 'game_start_table'}; await update.message.reply_text("🎮 میز بازی را انتخاب کنید (🔒=اشغال):", reply_markup=self.create_table_menu(lock_for_games=True))
                elif text == "🏁 پایان بازی": self.user_states[user_id] = {'mode': 'game_end'}; await update.message.reply_text("🏁 میز را برای پایان بازی انتخاب کنید:", reply_markup=self.create_active_tables_menu("game"))
                elif text == "💰 تسویه حساب": self.user_states[user_id] = {'mode': 'checkout'}; await update.message.reply_text("💰 میز آماده تسویه را انتخاب کنید:", reply_markup=self.create_active_tables_menu("checkout"))
                elif text == "👥 مدیریت بازیکنان": self.user_states[user_id] = {'mode': 'player_management'}; await update.message.reply_text("submenu:", reply_markup=self.create_player_management_menu())
                elif text == "☕ سفارش کافه": self.user_states[user_id] = {'mode': 'order_start_table', 'items':[]}; await update.message.reply_text("🍽️ میز سفارش را انتخاب کنید:", reply_markup=self.create_table_menu())
                elif text == "📝 مدیریت سفارش": self.user_states[user_id] = {'mode': 'order_management'}; await update.message.reply_text("submenu:", reply_markup=self.create_order_management_menu())
                return

            # --- State-based Router ---
            clean_table_name = text.replace("🔒 ", "")
            
            # GAME START
            if mode == 'game_start_table':
                if clean_table_name in self.active_games: await update.message.reply_text(f"❌ میز «{clean_table_name}» بازی فعال دارد!")
                else: state['table'] = clean_table_name; state['mode'] = 'game_start_players'; self.user_states[user_id] = state; await update.message.reply_text("👥 تعداد بازیکنان را وارد کنید:")
            elif mode == 'game_start_players':
                if text.isdigit() and int(text) > 0:
                    table = state['table']; players = int(text); iran_time = self.get_iran_time(); username = self.get_user_info(update.effective_user)
                    self.active_games[table] = {'player_groups': [{'count': players, 'start_time': iran_time, 'username': username}], 'game_start': iran_time}
                    message = f"🎲 شروع بازی\n🪑 میز: {table}\n👥 نفرات: {players}\n⏰ شروع: {iran_time}\n👤 @{username}"
                    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
                    self.clear_user_state(user_id); await update.message.reply_text(f"✅ بازی برای میز {table} ثبت شد.", reply_markup=self.create_main_menu())
                else: await update.message.reply_text("❌ لطفاً یک عدد صحیح و مثبت وارد کنید.")
            
            # GAME END / CHECKOUT
            elif mode == 'game_end':
                game_info = self.active_games.get(clean_table_name);
                if game_info and 'end_time' not in game_info:
                    game_info['end_time'] = self.get_iran_time()
                    player_display = sum(g['count'] for g in game_info['player_groups'] if g['count'] > 0)
                    message = f"🏁 پایان بازی (منتظر تسویه)\n🪑 میز: {clean_table_name}\n👥 نفرات: {player_display}\n⏰ شروع: {game_info['game_start']} | 🏁 پایان: {game_info['end_time']}\n👤 @{self.get_user_info(update.effective_user)}"
                    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
                    self.clear_user_state(user_id); await update.message.reply_text(f"✅ پایان بازی میز {clean_table_name} ثبت شد.", reply_markup=self.create_main_menu())
                else: await update.message.reply_text("❌ میز بازی فعال ندارد یا قبلا تمام شده.")
            elif mode == 'checkout':
                bill = self.calculate_bill(clean_table_name); username = self.get_user_info(update.effective_user)
                order_details = "\n".join([f"  - {name} (x{count})" for name, count in bill['order_summary'].items()]) or "  ندارد"
                bill_message = (f"💰 **صورتحساب میز: {clean_table_name}**\n" f"➖➖➖➖➖➖➖➖\n" f"🎮 **اطلاعات بازی**\n" f"  - زمان بازی: {bill['duration']} دقیقه\n" f"  - ساعت محاسبه شده: {bill['chargeable_hours']} ساعت\n" f"  - تعداد بازیکنان: {bill['total_players']} نفر\n" f"  - **هزینه بازی**: **{int(bill['game_cost']):,} تومان**\n" f"➖➖➖➖➖➖➖➖\n" f"☕ **سفارشات کافه**\n{order_details}\n" f"  - **هزینه سفارشات**: **{int(bill['order_cost']):,} تومان**\n" f"➖➖➖➖➖➖➖➖\n" f"💳 **مبلغ نهایی**: **{int(bill['total_cost']):,} تومان**\n\n" f"👤 مسئول: @{username}")
                await update.message.reply_text(bill_message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تسویه انجام شد", callback_data=f"settle_{clean_table_name}")]]), parse_mode='Markdown')
                self.clear_user_state(user_id)

            # PLAYER MANAGEMENT
            elif mode == 'player_management':
                if text == "➕ افزودن بازیکن": state['mode'] = 'player_add_table'; await update.message.reply_text("میز را برای افزودن بازیکن انتخاب کنید:", reply_markup=self.create_active_tables_menu("player_management"))
                elif text == "➖ کاهش بازیکن": state['mode'] = 'player_remove_table'; await update.message.reply_text("میز را برای کاهش بازیکن انتخاب کنید:", reply_markup=self.create_active_tables_menu("player_management"))
                self.user_states[user_id] = state
            elif mode == 'player_add_table':
                if clean_table_name in self.active_games: state['table'] = clean_table_name; state['mode'] = 'player_add_count'; self.user_states[user_id] = state; await update.message.reply_text(f"تعداد بازیکنان جدید برای میز {clean_table_name} را وارد کنید:")
                else: await update.message.reply_text("میز نامعتبر است.")
            elif mode == 'player_remove_table':
                 if clean_table_name in self.active_games: state['table'] = clean_table_name; state['mode'] = 'player_remove_count'; self.user_states[user_id] = state; await update.message.reply_text(f"تعداد بازیکنان خروجی از میز {clean_table_name} را وارد کنید:")
                 else: await update.message.reply_text("میز نامعتبر است.")
            elif mode in ('player_add_count', 'player_remove_count'):
                if text.isdigit() and int(text) > 0:
                    table, count = state['table'], int(text)
                    game_info = self.active_games[table]
                    total_players = sum(g['count'] for g in game_info['player_groups'])
                    iran_time, username = self.get_iran_time(), self.get_user_info(update.effective_user)
                    if mode == 'player_add_count':
                        game_info['player_groups'].append({'count': count, 'start_time': iran_time, 'username': username})
                        message = f"➕ افزودن بازیکن\n🪑 میز: {table}\n👥 اضافه شده: +{count} نفر\n👥 تعداد کل: {total_players + count} نفر\n⏰ زمان: {iran_time}\n👤 @{username}"
                    else: # player_remove_count
                        if count >= total_players: await update.message.reply_text(f"❌ تعداد کاهش ({count}) بیشتر یا مساوی کل بازیکنان ({total_players}) است!"); return
                        game_info['player_groups'].append({'count': -count, 'start_time': iran_time, 'username': username})
                        message = f"➖ خروج بازیکن\n🪑 میز: {table}\n👥 خارج شده: -{count} نفر\n👥 باقی‌مانده: {total_players - count} نفر\n⏰ زمان: {iran_time}\n👤 @{username}"
                    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
                    self.clear_user_state(user_id); await update.message.reply_text("✅ تغییرات ثبت شد.", reply_markup=self.create_main_menu())
                else: await update.message.reply_text("❌ لطفاً یک عدد صحیح و مثبت وارد کنید.")

            # ORDER FLOW (New Order)
            elif mode == 'order_start_table':
                state['table'] = clean_table_name; state['mode'] = 'order_category'; self.user_states[user_id] = state; await update.message.reply_text("📋 دسته‌بندی را انتخاب کنید:", reply_markup=self.create_category_menu())
            elif mode in ('order_category', 'order_item'):
                if text in self.category_labels.values():
                    items = self.get_items_by_category(text)
                    if items: state['current_category'] = text; self.user_states[user_id] = state; await update.message.reply_text(f"آیتم را از دسته‌بندی {text} انتخاب کنید:", reply_markup=self.create_items_menu(items))
                    else: await update.message.reply_text("⛔ آیتمی در این دسته‌بندی نیست.")
                elif text == 'ثبت سفارش':
                    table, items_list = state['table'], state['items']
                    if not items_list: await update.message.reply_text("❗ هیچ آیتمی انتخاب نشده."); return
                    iran_time, username = self.get_iran_time(), self.get_user_info(update.effective_user)
                    
                    if table in self.active_orders: # Appending to existing order
                        self.active_orders[table]['items'].extend(items_list)
                        message = f"➕ افزودن به سفارش\n🪑 میز: {table}\n🍽 آیتم‌های جدید: {', '.join(items_list)}\n⏰ زمان: {iran_time}\n👤 @{username}"
                    else: # New order
                        self.active_orders[table] = {'items': items_list, 'last_update': iran_time, 'username': username}
                        message = f"📦 سفارش جدید\n🪑 میز: {table}\n🍽 آیتم‌ها: {', '.join(items_list)}\n⏰ زمان: {iran_time}\n👤 @{username}"
                    
                    await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
                    self.clear_user_state(user_id); await update.message.reply_text("✅ سفارش ثبت شد.", reply_markup=self.create_main_menu())
                else: # An item was selected
                    state.get('items', []).append(text)
                    self.user_states[user_id] = state
                    await update.message.reply_text(f"✅ «{text}» اضافه شد.\nآیتم بعدی را انتخاب یا سفارش را ثبت کنید:", reply_markup=self.create_category_menu())

            # ORDER MANAGEMENT (Existing Orders)
            elif mode == 'order_management':
                if text == "➕ افزودن به سفارش": state['mode'] = 'order_add_table'; await update.message.reply_text("میزی را برای افزودن سفارش انتخاب کنید:", reply_markup=self.create_active_tables_menu("order"))
                # elif text == "✏️ ویرایش سفارش": ... (To be implemented if needed)
                self.user_states[user_id] = state
            elif mode == 'order_add_table': # This flow merges with the new order flow
                if clean_table_name in self.active_orders:
                    state['table'] = clean_table_name; state['mode'] = 'order_category'; self.user_states[user_id] = state
                    await update.message.reply_text(f"سفارش فعلی: {', '.join(self.active_orders[clean_table_name]['items'])}\n\nافزودن آیتم جدید:", reply_markup=self.create_category_menu())
                else: await update.message.reply_text("میز سفارش فعال ندارد.")


        except Exception as e:
            logger.error(f"Critical error in handle_message: {e}", exc_info=True)
            await update.message.reply_text("❌ خطای غیرمنتظره. با /start مجددا شروع کنید.", reply_markup=self.create_main_menu())


def main():
    try:
        bot = CafeBot()
        if not bot.items or not bot.prices:
            logger.critical("Bot cannot start: menu data failed to load from items.json."); return
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", bot.start_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        app.add_handler(CallbackQueryHandler(bot.handle_settlement_callback, pattern="^settle_"))
        logger.info("Bot started successfully (Final Version).")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()