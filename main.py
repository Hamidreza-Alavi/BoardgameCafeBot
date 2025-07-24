import json
import logging
import pytz
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from config import BOT_TOKEN, ALLOWED_USER_IDS, CHANNEL_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CafeBot:
    def __init__(self):
        self.load_menu()
        self.user_states = {}
        self.active_orders = {}  # Store active orders for editing/adding
        self.active_games = {}   # Store active games for ending
        self.category_labels = {
            "COFFEE_HOT": "☕ قهوه داغ",
            "COFFEE_COLD": "🧊 قهوه سرد",
            "HOT_DRINKS_NON_COFFEE": "🍵 نوشیدنی داغ بدون قهوه",
            "TEA": "🍃 چای",
            "HERBAL_TEA": "🌿 دمنوش",
            "MILKSHAKE": "🥤 میلک‌شیک",
            "JUICE": "🍹 آب‌میوه",
            "MOCKTAIL": "🍸 ماکتیل",
            "ICE_CREAM": "🍨 بستنی",
            "CAKE": "🍰 کیک",
            "FOOD": "🍕 غذا",
            "ADDITIVES": "🧂 افزودنی",
            "WATER": "💧 آب"
        }

    def load_menu(self):
        try:
            with open("items.json", encoding="utf-8") as f:
                self.items = json.load(f)
            logger.info("Menu loaded successfully")
        except FileNotFoundError:
            logger.error("items.json not found")
            self.items = {}
        except json.JSONDecodeError:
            logger.error("Invalid JSON format in items.json")
            self.items = {}

    def check_user_access(self, user_id: int) -> bool:
        return user_id in ALLOWED_USER_IDS

    def get_iran_time(self) -> str:
        return datetime.now(pytz.timezone("Asia/Tehran")).strftime("%H:%M")

    def get_user_info(self, user) -> str:
        return user.username or user.first_name or "ناشناس"

    def create_main_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("🎲 شروع بازی"), KeyboardButton("🏁 پایان بازی")],
            [KeyboardButton("☕ سفارش کافه"), KeyboardButton("📝 مدیریت سفارش")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_order_management_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("➕ افزودن به سفارش"), KeyboardButton("✏️ ویرایش سفارش")],
            [KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_table_menu(self) -> ReplyKeyboardMarkup:
        buttons = []
        for i in range(1, 17, 4):
            row = [KeyboardButton(f"میز {j}") for j in range(i, min(i+4, 17))]
            buttons.append(row)
        
        buttons.extend([
            [KeyboardButton("میز آزاد"), KeyboardButton("PS")],
            [KeyboardButton("فرمون")],
            [KeyboardButton("بازگشت")]
        ])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_active_tables_menu(self, table_type: str) -> ReplyKeyboardMarkup:
        """Create menu showing only tables with active orders/games"""
        buttons = []
        active_tables = []
        
        if table_type == "order":
            active_tables = list(self.active_orders.keys())
        elif table_type == "game":
            active_tables = list(self.active_games.keys())
        
        if not active_tables:
            buttons.append([KeyboardButton("هیچ میز فعالی موجود نیست")])
        else:
            for i in range(0, len(active_tables), 2):
                row = active_tables[i:i+2]
                buttons.append([KeyboardButton(table) for table in row])
        
        buttons.append([KeyboardButton("بازگشت")])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_category_menu(self) -> ReplyKeyboardMarkup:
        buttons = []
        categories = list(self.category_labels.values())
        
        for i in range(0, len(categories), 2):
            row = categories[i:i+2]
            buttons.append([KeyboardButton(cat) for cat in row])
        
        buttons.extend([
            [KeyboardButton("ثبت سفارش")],
            [KeyboardButton("بازگشت")]
        ])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_items_menu(self, items: list) -> ReplyKeyboardMarkup:
        buttons = []
        
        for i in range(0, len(items), 2):
            row = items[i:i+2]
            buttons.append([KeyboardButton(item) for item in row])
        
        buttons.append([KeyboardButton("بازگشت")])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_edit_order_menu(self, items: list) -> ReplyKeyboardMarkup:
        """Create menu for editing existing order items"""
        buttons = []
        
        for i, item in enumerate(items, 1):
            buttons.append([KeyboardButton(f"حذف: {item}")])
        
        buttons.extend([
            [KeyboardButton("➕ افزودن آیتم جدید")],
            [KeyboardButton("✅ تایید تغییرات"), KeyboardButton("❌ لغو")],
            [KeyboardButton("بازگشت")]
        ])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def get_items_by_category(self, category_label: str) -> list:
        for key, label in self.category_labels.items():
            if label == category_label:
                return self.items.get(key, [])
        return []

    def clear_user_state(self, user_id: int):
        self.user_states.pop(user_id, None)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.check_user_access(user_id):
            await update.message.reply_text("⛔ دسترسی ندارید.")
            return

        self.clear_user_state(user_id)
        await update.message.reply_text(
            "🎮 خوش آمدید!\nگزینه‌ای را انتخاب کنید:", 
            reply_markup=self.create_main_menu()
        )

    async def handle_game_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if 'table' not in state:
            return await update.message.reply_text("لطفاً ابتدا میز را انتخاب کنید.")
        
        if 'players' in state:
            return
        
        try:
            players = int(text)
            if players <= 0:
                raise ValueError("تعداد نفرات باید مثبت باشد")
            
            table = state['table']
            iran_time = self.get_iran_time()
            username = self.get_user_info(update.effective_user)
            
            # Store active game
            self.active_games[table] = {
                'players': players,
                'start_time': iran_time,
                'username': username
            }
            
            message = (
                f"🎲 شروع بازی\n"
                f"🪑 میز: {table}\n"
                f"👥 تعداد نفرات: {players}\n"
                f"⏰ زمان شروع: {iran_time}\n"
                f"👤 @{username}"
            )
            
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            self.clear_user_state(user_id)
            await update.message.reply_text(
                "✅ بازی با موفقیت ثبت شد.\n"
                "💡 برای ثبت پایان بازی از گزینه 'پایان بازی' استفاده کنید.",
                reply_markup=self.create_main_menu()
            )
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد صحیح و مثبت وارد کنید.")

    async def handle_game_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "هیچ میز فعالی موجود نیست":
            await update.message.reply_text("❗ هیچ بازی فعالی برای پایان دادن موجود نیست.")
            return

        if text in self.active_games:
            game_info = self.active_games[text]
            iran_time = self.get_iran_time()
            username = self.get_user_info(update.effective_user)
            
            message = (
                f"🏁 پایان بازی\n"
                f"🪑 میز: {text}\n"
                f"👥 تعداد نفرات: {game_info['players']}\n"
                f"⏰ زمان شروع: {game_info['start_time']}\n"
                f"🏁 زمان پایان: {iran_time}\n"
                f"👤 پایان دهنده: @{username}"
            )
            
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            
            # Remove from active games
            del self.active_games[text]
            self.clear_user_state(user_id)
            
            await update.message.reply_text(
                "✅ پایان بازی با موفقیت ثبت شد.",
                reply_markup=self.create_main_menu()
            )
        else:
            await update.message.reply_text("❌ میز انتخابی معتبر نیست.")

    async def handle_order_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text in self.category_labels.values():
            items = self.get_items_by_category(text)
            if items:
                state['current_category'] = text
                self.user_states[user_id] = state
                await update.message.reply_text(
                    f"📋 {text}\nآیتم مورد نظر را انتخاب کنید:",
                    reply_markup=self.create_items_menu(items)
                )
            else:
                await update.message.reply_text("⛔ آیتمی برای این دسته‌بندی موجود نیست.")
                
        elif text == "ثبت سفارش":
            await self.submit_order(update, context, user_id, state)
            
        elif state.get("current_category"):
            await self.add_item_to_order(update, user_id, text, state)
            
        else:
            await update.message.reply_text("⛔ لطفاً از منو استفاده کنید.")

    async def handle_add_to_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "هیچ میز فعالی موجود نیست":
            await update.message.reply_text("❗ هیچ سفارش فعالی برای افزودن موجود نیست.")
            return

        if text in self.active_orders and 'selected_table' not in state:
            state['selected_table'] = text
            state['items'] = self.active_orders[text]['items'].copy()
            self.user_states[user_id] = state
            
            await update.message.reply_text(
                f"📦 سفارش فعلی میز {text}:\n"
                f"🍽 آیتم‌ها: {', '.join(state['items'])}\n\n"
                f"دسته‌بندی جدید را برای افزودن انتخاب کنید:",
                reply_markup=self.create_category_menu()
            )
        elif 'selected_table' in state:
            # Handle category/item selection for adding
            await self.handle_order_flow(update, context, user_id, text, state)

    async def handle_edit_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "هیچ میز فعالی موجود نیست":
            await update.message.reply_text("❗ هیچ سفارش فعالی برای ویرایش موجود نیست.")
            return

        if text in self.active_orders and 'editing_table' not in state:
            state['editing_table'] = text
            state['original_items'] = self.active_orders[text]['items'].copy()
            state['items'] = self.active_orders[text]['items'].copy()
            self.user_states[user_id] = state
            
            await update.message.reply_text(
                f"✏️ ویرایش سفارش میز {text}:\n"
                f"آیتم‌های فعلی: {', '.join(state['items'])}\n\n"
                f"گزینه مورد نظر را انتخاب کنید:",
                reply_markup=self.create_edit_order_menu(state['items'])
            )
        elif 'editing_table' in state:
            if text.startswith("حذف: "):
                item_to_remove = text[5:]  # Remove "حذف: " prefix
                if item_to_remove in state['items']:
                    state['items'].remove(item_to_remove)
                    self.user_states[user_id] = state
                    
                    await update.message.reply_text(
                        f"❌ «{item_to_remove}» حذف شد.\n"
                        f"آیتم‌های باقی‌مانده: {', '.join(state['items']) if state['items'] else 'هیچ آیتمی باقی نمانده'}\n\n"
                        f"گزینه مورد نظر را انتخاب کنید:",
                        reply_markup=self.create_edit_order_menu(state['items'])
                    )
            elif text == "➕ افزودن آیتم جدید":
                await update.message.reply_text(
                    "📋 دسته‌بندی را برای افزودن آیتم جدید انتخاب کنید:",
                    reply_markup=self.create_category_menu()
                )
            elif text == "✅ تایید تغییرات":
                await self.update_existing_order(update, context, user_id, state)
            elif text == "❌ لغو":
                self.clear_user_state(user_id)
                await update.message.reply_text(
                    "❌ ویرایش لغو شد.",
                    reply_markup=self.create_main_menu()
                )
            elif text in self.category_labels.values():
                # Handle adding new items during edit
                await self.handle_order_flow(update, context, user_id, text, state)

    async def add_item_to_order(self, update: Update, user_id: int, text: str, state: dict):
        items = self.get_items_by_category(state["current_category"])
        
        if text in items:
            state['items'].append(text)
            state.pop('current_category', None)
            self.user_states[user_id] = state
            
            items_count = len(state['items'])
            
            # Different responses based on mode
            if 'editing_table' in state:
                await update.message.reply_text(
                    f"✅ «{text}» اضافه شد.\n"
                    f"📦 تعداد آیتم‌ها: {items_count}\n\n"
                    f"گزینه مورد نظر را انتخاب کنید:",
                    reply_markup=self.create_edit_order_menu(state['items'])
                )
            else:
                await update.message.reply_text(
                    f"✅ «{text}» اضافه شد.\n"
                    f"📦 تعداد آیتم‌ها: {items_count}\n\n"
                    f"دسته‌بندی جدید را انتخاب کنید یا سفارش را ثبت کنید:",
                    reply_markup=self.create_category_menu()
                )
        else:
            await update.message.reply_text("⛔ لطفاً از لیست آیتم‌ها انتخاب کنید.")

    async def submit_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, state: dict):
        table = state.get('table') or state.get('selected_table', 'نامشخص')
        items_list = state.get('items', [])
        
        if not items_list:
            await update.message.reply_text("❗ هیچ آیتمی انتخاب نشده است.")
            return
        
        items_str = "، ".join(items_list)
        username = self.get_user_info(update.effective_user)
        iran_time = self.get_iran_time()
        
        # Check if this is adding to existing order
        if 'selected_table' in state:
            message = (
                f"➕ افزودن به سفارش\n"
                f"🪑 میز: {table}\n"
                f"🍽 آیتم‌های جدید ({len(items_list)}): {items_str}\n"
                f"⏰ زمان: {iran_time}\n"
                f"👤 @{username}"
            )
        else:
            message = (
                f"📦 سفارش جدید\n"
                f"🪑 میز: {table}\n"
                f"🍽 آیتم‌ها ({len(items_list)}): {items_str}\n"
                f"⏰ زمان: {iran_time}\n"
                f"👤 @{username}"
            )
        
        try:
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            
            # Store/update active order
            self.active_orders[table] = {
                'items': items_list,
                'last_update': iran_time,
                'username': username
            }
            
            self.clear_user_state(user_id)
            await update.message.reply_text(
                "✅ سفارش با موفقیت ثبت شد.",
                reply_markup=self.create_main_menu()
            )
        except Exception as e:
            logger.error(f"Error sending order: {e}")
            await update.message.reply_text("❌ خطا در ثبت سفارش. لطفاً دوباره تلاش کنید.")

    async def update_existing_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, state: dict):
        table = state['editing_table']
        new_items = state['items']
        original_items = state['original_items']
        
        if new_items == original_items:
            await update.message.reply_text("❗ هیچ تغییری اعمال نشده است.")
            return
        
        items_str = "، ".join(new_items) if new_items else "هیچ آیتمی باقی نمانده"
        username = self.get_user_info(update.effective_user)
        iran_time = self.get_iran_time()
        
        message = (
            f"✏️ ویرایش سفارش\n"
            f"🪑 میز: {table}\n"
            f"🍽 آیتم‌های جدید ({len(new_items)}): {items_str}\n"
            f"⏰ زمان ویرایش: {iran_time}\n"
            f"👤 @{username}"
        )
        
        try:
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            
            # Update active order
            if new_items:
                self.active_orders[table] = {
                    'items': new_items,
                    'last_update': iran_time,
                    'username': username
                }
            else:
                # Remove order if no items left
                self.active_orders.pop(table, None)
            
            self.clear_user_state(user_id)
            await update.message.reply_text(
                "✅ سفارش با موفقیت ویرایش شد.",
                reply_markup=self.create_main_menu()
            )
        except Exception as e:
            logger.error(f"Error updating order: {e}")
            await update.message.reply_text("❌ خطا در ویرایش سفارش. لطفاً دوباره تلاش کنید.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if not self.check_user_access(user_id):
            await update.message.reply_text("⛔ دسترسی ندارید.")
            return

        state = self.user_states.get(user_id, {})

        if text == "بازگشت":
            self.clear_user_state(user_id)
            return await self.start_command(update, context)

        # Main menu options
        if text == "🎲 شروع بازی":
            self.user_states[user_id] = {'mode': 'game'}
            await update.message.reply_text(
                "🎮 میز بازی را انتخاب کنید:",
                reply_markup=self.create_table_menu()
            )
            return

        if text == "🏁 پایان بازی":
            self.user_states[user_id] = {'mode': 'game_end'}
            await update.message.reply_text(
                "🏁 میز بازی را برای پایان انتخاب کنید:",
                reply_markup=self.create_active_tables_menu("game")
            )
            return

        if text == "☕ سفارش کافه":
            self.user_states[user_id] = {'mode': 'order', 'items': []}
            await update.message.reply_text(
                "🍽 میز سفارش را انتخاب کنید:",
                reply_markup=self.create_table_menu()
            )
            return

        if text == "📝 مدیریت سفارش":
            await update.message.reply_text(
                "📝 عملیات مورد نظر را انتخاب کنید:",
                reply_markup=self.create_order_management_menu()
            )
            return

        if text == "➕ افزودن به سفارش":
            self.user_states[user_id] = {'mode': 'add_to_order'}
            await update.message.reply_text(
                "➕ میز سفارش را برای افزودن انتخاب کنید:",
                reply_markup=self.create_active_tables_menu("order")
            )
            return

        if text == "✏️ ویرایش سفارش":
            self.user_states[user_id] = {'mode': 'edit_order'}
            await update.message.reply_text(
                "✏️ میز سفارش را برای ویرایش انتخاب کنید:",
                reply_markup=self.create_active_tables_menu("order")
            )
            return

        # Table selection
        if text.startswith("میز") or text in ("میز آزاد", "PS", "فرمون"):
            if 'mode' not in state:
                await update.message.reply_text("لطفاً ابتدا از منوی اصلی گزینه‌ای را انتخاب کنید.")
                return
            
            state['table'] = text
            self.user_states[user_id] = state
            
            if state['mode'] == 'game':
                await update.message.reply_text("👥 تعداد بازیکنان را وارد کنید:")
            else:
                await update.message.reply_text(
                    "📋 دسته‌بندی را انتخاب کنید:",
                    reply_markup=self.create_category_menu()
                )
            return

        # Handle different modes
        if state.get('mode') == 'game' and 'table' in state and 'players' not in state:
            await self.handle_game_flow(update, context, user_id, text, state)
            return

        if state.get('mode') == 'game_end':
            await self.handle_game_end(update, context, user_id, text, state)
            return

        if state.get('mode') == 'order':
            await self.handle_order_flow(update, context, user_id, text, state)
            return

        if state.get('mode') == 'add_to_order':
            await self.handle_add_to_order(update, context, user_id, text, state)
            return

        if state.get('mode') == 'edit_order':
            await self.handle_edit_order(update, context, user_id, text, state)
            return

        await update.message.reply_text("⛔ لطفاً از منو استفاده کنید یا دکمه بازگشت را بزنید.")

def main():
    try:
        bot = CafeBot()
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", bot.start_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        
        logger.info("Bot started successfully")
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()