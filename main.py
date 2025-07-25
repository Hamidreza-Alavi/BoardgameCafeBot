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
        self.active_games = {}   # Store active games with detailed player info
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
            [KeyboardButton("👥 مدیریت بازیکنان"), KeyboardButton("☕ سفارش کافه")],
            [KeyboardButton("📝 مدیریت سفارش"), KeyboardButton("🔄 جابه‌جایی میز")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_player_management_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("➕ افزودن بازیکن"), KeyboardButton("➖ کاهش بازیکن")],
            [KeyboardButton("📊 وضعیت میزها"), KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_order_management_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("➕ افزودن به سفارش"), KeyboardButton("✏️ ویرایش سفارش")],
            [KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_move_table_menu(self) -> ReplyKeyboardMarkup:
        buttons = [
            [KeyboardButton("انتخاب میز مبدأ"), KeyboardButton("انتخاب میز مقصد")],
            [KeyboardButton("بازگشت")]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def is_game_active_on_table(self, table_name: str) -> bool:
        """Helper function to check if a game is active on a table."""
        return table_name in self.active_games

    def create_table_menu(self, lock_for_games=False) -> ReplyKeyboardMarkup:
        """
        Creates the table menu.
        If 'lock_for_games' is True, it will show a lock icon for tables with active games.
        """
        try:
            buttons = []
            all_tables = [f"میز {i}" for i in range(1, 17)] + ["میز آزاد", "PS", "فرمون"]
            
            table_rows = [all_tables[i:i+4] for i in range(0, 16, 4)]
            table_rows.append(all_tables[16:18]) # میز آزاد, PS
            table_rows.append([all_tables[18]])  # فرمون

            for row_items in table_rows:
                row = []
                for table_name in row_items:
                    if lock_for_games and self.is_game_active_on_table(table_name):
                        row.append(KeyboardButton(f"🔒 {table_name}"))
                    else:
                        row.append(KeyboardButton(table_name))
                buttons.append(row)
            
            buttons.append([KeyboardButton("بازگشت")])
            return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        except Exception as e:
            logger.error(f"Error creating table menu: {e}")
            buttons = [
                [KeyboardButton("میز 1"), KeyboardButton("میز 2"), KeyboardButton("میز 3"), KeyboardButton("میز 4")],
                [KeyboardButton("بازگشت")]
            ]
            return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def create_active_tables_menu(self, table_type: str) -> ReplyKeyboardMarkup:
        buttons = []
        active_tables = []
        
        if table_type == "order":
            active_tables = list(self.active_orders.keys())
        elif table_type == "game":
            active_tables = list(self.active_games.keys())
        elif table_type == "both":
            active_tables = list(set(list(self.active_orders.keys()) + list(self.active_games.keys())))
        
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
        buttons = []
        
        for item in items:
            buttons.append([KeyboardButton(f"حذف: {item}")])
        
        buttons.extend([
            [KeyboardButton("➕ افزودن آیتم جدید")],
            [KeyboardButton("✅ تایید تغییرات"), KeyboardButton("❌ لغو")],
            [KeyboardButton("بازگشت")]
        ])
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def format_player_history(self, player_groups: list) -> str:
        """Format player history for display"""
        if not player_groups:
            return "نامشخص"
        
        if len(player_groups) == 1:
            return str(player_groups[0]['count'])
        
        # Multiple groups - show as additions
        result = str(player_groups[0]['count'])
        for i in range(1, len(player_groups)):
            result += f"+{player_groups[i]['count']}"
        return result

    def format_time_history(self, player_groups: list) -> str:
        """Format time history for display"""
        if not player_groups:
            return "نامشخص"
        
        if len(player_groups) == 1:
            return player_groups[0]['start_time']
        
        # Multiple groups - show time ranges
        result = player_groups[0]['start_time']
        for i in range(1, len(player_groups)):
            result += f"-{player_groups[i]['start_time']}"
        return result

    def get_table_status(self, table_name: str) -> str:
        try:
            if table_name in self.active_games:
                game_info = self.active_games[table_name]
                player_groups = game_info.get('player_groups', [])
                total_players = sum(group['count'] for group in player_groups)
                player_display = self.format_player_history(player_groups)
                time_display = self.format_time_history(player_groups)
                return f"🎲 در حال بازی ({player_display} نفر) - شروع: {time_display}"
            elif table_name in self.active_orders:
                order_info = self.active_orders[table_name]
                items_count = len(order_info.get('items', []))
                return f"☕ سفارش فعال ({items_count} آیتم) - آخرین بروزرسانی: {order_info.get('last_update', '?')}"
            else:
                return "🟢 آزاد"
        except Exception as e:
            logger.error(f"Error getting table status: {e}")
            return "❓ نامشخص"

    def get_items_by_category(self, category_label: str) -> list:
        """
        بازگردادن لیست نام آیتم‌ها بدون قیمت برای نمایش در منو
        """
        for key, label in self.category_labels.items():
            if label == category_label:
                items_data = self.items.get(key, [])
                # اگر آیتم‌ها dictionary هستند، فقط نام را برمی‌گردانیم
                if items_data and isinstance(items_data[0], dict):
                    return [item["name"] for item in items_data]
                # اگر آیتم‌ها string هستند، همان‌طور که هستند برمی‌گردانیم
                else:
                    return items_data
        return []

    def get_item_price(self, category_label: str, item_name: str) -> int:
        """
        بازگردانی قیمت یک آیتم خاص (برای استفاده آینده)
        """
        for key, label in self.category_labels.items():
            if label == category_label:
                items_data = self.items.get(key, [])
                for item in items_data:
                    if isinstance(item, dict) and item["name"] == item_name:
                        return item["price"]
        return 0

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
            
            # Initialize game with detailed player tracking
            self.active_games[table] = {
                'player_groups': [
                    {
                        'count': players,
                        'start_time': iran_time,
                        'username': username
                    }
                ],
                'total_players': players,
                'game_start': iran_time,
                'creator': username
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
                f"✅ بازی با موفقیت ثبت شد.\n"
                f"🔒 میز «{table}» برای شروع بازی جدید قفل شد.\n"
                f"💡 برای مدیریت بازیکنان از گزینه 'مدیریت بازیکنان' استفاده کنید.",
                reply_markup=self.create_main_menu()
            )
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد صحیح و مثبت وارد کنید.")

    async def handle_player_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "📊 وضعیت میزها":
            await self.show_table_status(update)
            return
        
        mode = state.get('player_mode')
        
        if text == "هیچ میز فعالی موجود نیست":
            await update.message.reply_text(
                "❗ هیچ بازی فعالی برای مدیریت موجود نیست.",
                reply_markup=self.create_player_management_menu()
            )
            return
        
        if mode and text in self.active_games and 'selected_table' not in state:
            # Table selected
            state['selected_table'] = text
            self.user_states[user_id] = state
            
            game_info = self.active_games[text]
            current_total = game_info['total_players']
            
            if mode == 'add':
                await update.message.reply_text(
                    f"➕ افزودن بازیکن به میز {text}\n"
                    f"👥 تعداد فعلی: {current_total} نفر\n\n"
                    f"تعداد بازیکنان جدید را وارد کنید:"
                )
            elif mode == 'remove':
                await update.message.reply_text(
                    f"➖ کاهش بازیکن از میز {text}\n"
                    f"👥 تعداد فعلی: {current_total} نفر\n\n"
                    f"تعداد بازیکنانی که خارج شده‌اند را وارد کنید:"
                )
        
        elif mode and 'selected_table' in state and text.isdigit():
            # Number entered
            await self.process_player_change(update, context, user_id, int(text), state)

    async def process_player_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, count: int, state: dict):
        table = state['selected_table']
        mode = state['player_mode']
        
        if table not in self.active_games:
            await update.message.reply_text("❌ بازی دیگر فعال نیست.")
            return
        
        game_info = self.active_games[table]
        current_total = game_info['total_players']
        iran_time = self.get_iran_time()
        username = self.get_user_info(update.effective_user)
        
        if mode == 'add':
            if count <= 0:
                await update.message.reply_text("❌ تعداد باید مثبت باشد.")
                return
            
            # Add new player group
            game_info['player_groups'].append({
                'count': count,
                'start_time': iran_time,
                'username': username
            })
            game_info['total_players'] += count
            
            message = (
                f"➕ افزودن بازیکن\n"
                f"🪑 میز: {table}\n"
                f"👥 تعداد اضافه شده: +{count} نفر\n"
                f"👥 تعداد کل: {game_info['total_players']} نفر\n"
                f"⏰ زمان ورود: {iran_time}\n"
                f"👤 @{username}"
            )
            
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            success_msg = f"✅ {count} بازیکن به میز {table} اضافه شد."
            
        elif mode == 'remove':
            if count <= 0:
                await update.message.reply_text("❌ تعداد باید مثبت باشد.")
                return
            
            if count >= current_total:
                await update.message.reply_text(
                    f"❌ نمی‌توان {count} نفر را حذف کرد.\n"
                    f"تعداد فعلی: {current_total} نفر"
                )
                return
            
            # Add removal record (negative count)
            game_info['player_groups'].append({
                'count': -count,
                'start_time': iran_time,
                'username': username
            })
            game_info['total_players'] -= count
            
            message = (
                f"➖ خروج بازیکن\n"
                f"🪑 میز: {table}\n"
                f"👥 تعداد خارج شده: -{count} نفر\n"
                f"👥 تعداد باقی‌مانده: {game_info['total_players']} نفر\n"
                f"⏰ زمان خروج: {iran_time}\n"
                f"👤 @{username}"
            )
            
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            success_msg = f"✅ {count} بازیکن از میز {table} خارج شد."
        
        self.clear_user_state(user_id)
        await update.message.reply_text(
            success_msg,
            reply_markup=self.create_main_menu()
        )

    async def show_table_status(self, update: Update):
        """Show status of all tables"""
        active_games = len(self.active_games)
        active_orders = len(self.active_orders)
        
        status_text = f"📊 وضعیت میزها\n\n"
        status_text += f"🎲 بازی‌های فعال: {active_games}\n"
        status_text += f"☕ سفارش‌های فعال: {active_orders}\n\n"
        
        if self.active_games:
            status_text += "🎮 میزهای در حال بازی:\n"
            for table, info in self.active_games.items():
                player_display = self.format_player_history(info['player_groups'])
                time_display = self.format_time_history(info['player_groups'])
                status_text += f"• {table}: {player_display} نفر ({time_display})\n"
            status_text += "\n"
        
        if self.active_orders:
            status_text += "🍽 میزهای دارای سفارش:\n"
            for table, info in self.active_orders.items():
                items_count = len(info.get('items', []))
                status_text += f"• {table}: {items_count} آیتم\n"
        
        await update.message.reply_text(
            status_text,
            reply_markup=self.create_player_management_menu()
        )

    async def handle_game_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "هیچ میز فعالی موجود نیست":
            await update.message.reply_text(
                "❗ هیچ بازی فعالی برای پایان دادن موجود نیست.",
                reply_markup=self.create_main_menu()
            )
            return

        if text in self.active_games:
            game_info = self.active_games[text]
            iran_time = self.get_iran_time()

            # Get order information for the table
            order_string = "🍽 سفارشات: ثبت نشده است"
            if text in self.active_orders:
                order_info = self.active_orders[text]
                items_list = order_info.get('items', [])
                if items_list:
                    order_string = f"🍽 سفارشات: {', '.join(items_list)}"
            
            # Format player and time information
            player_display = self.format_player_history(game_info['player_groups'])
            time_display = self.format_time_history(game_info['player_groups'])
            
            # Construct the message with enhanced formatting
            message = (
                f"🏁 پایان بازی و تسویه میز\n"
                f"➖➖➖➖➖➖➖➖\n"
                f"🪑 میز: {text}\n"
                f"👥 تعداد نفرات: {player_display}\n"
                f"⏰ زمان شروع: {time_display}\n"
                f"🏁 زمان پایان: {iran_time}\n"
                f"➖➖➖➖➖➖➖➖\n"
                f"{order_string}"
            )
            
            try:
                await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
                
                # Remove both game and order from active lists
                del self.active_games[text]
                self.active_orders.pop(text, None)
                self.clear_user_state(user_id)
                
                await update.message.reply_text(
                    "✅ پایان بازی و تسویه میز با موفقیت ثبت شد.",
                    reply_markup=self.create_main_menu()
                )
            except Exception as e:
                logger.error(f"Error sending game end message: {e}")
                await update.message.reply_text(
                    "❌ خطا در ثبت پایان بازی. لطفاً دوباره تلاش کنید.",
                    reply_markup=self.create_main_menu()
                )
        else:
            await update.message.reply_text(
                "❌ میز انتخابی معتبر نیست یا بازی فعالی ندارد.",
                reply_markup=self.create_active_tables_menu("game")
            )

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
                item_to_remove = text[5:]
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
                state['adding_item'] = True
                self.user_states[user_id] = state
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
            elif text in self.category_labels.values() and state.get('adding_item'):
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
            elif text == "ثبت سفارش" and 'editing_table' in state:
                await update.message.reply_text(
                    "✏️ در حال ویرایش هستید. از گزینه 'تایید تغییرات' استفاده کنید:",
                    reply_markup=self.create_edit_order_menu(state['items'])
                )

    async def add_item_to_order(self, update: Update, user_id: int, text: str, state: dict):
        items = self.get_items_by_category(state["current_category"])
        
        if text in items:
            state['items'].append(text)
            state.pop('current_category', None)
            
            if 'adding_item' in state:
                state.pop('adding_item', None)
            
            self.user_states[user_id] = state
            
            items_count = len(state['items'])
            
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
            
            self.active_orders[table] = {
                'items': items_list,
                'last_update': iran_time,
                'username': username
            }
            
            self.clear_user_state(user_id)
            success_message = "✅ سفارش با موفقیت ثبت شد."
            
            await update.message.reply_text(
                success_message,
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
            
            if new_items:
                self.active_orders[table] = {
                    'items': new_items,
                    'last_update': iran_time,
                    'username': username
                }
            else:
                self.active_orders.pop(table, None)
            
            self.clear_user_state(user_id)
            await update.message.reply_text(
                "✅ سفارش با موفقیت ویرایش شد.",
                reply_markup=self.create_main_menu()
            )
        except Exception as e:
            logger.error(f"Error updating order: {e}")
            await update.message.reply_text("❌ خطا در ویرایش سفارش. لطفاً دوباره تلاش کنید.")

    async def handle_move_table(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, state: dict):
        if text == "🔄 جابه‌جایی میز":
            self.user_states[user_id] = {'mode': 'move_table'}
            await update.message.reply_text(
                "🔄 فرآیند جابه‌جایی میز\nلطفاً عملیات مورد نظر را انتخاب کنید:",
                reply_markup=self.create_move_table_menu()
            )
            return
        
        if text == "انتخاب میز مبدأ":
            state['move_step'] = 'select_source'
            self.user_states[user_id] = state
            await update.message.reply_text(
                "میز مبدأ (منبع) را انتخاب کنید:",
                reply_markup=self.create_active_tables_menu("both")
            )
            return
            
        if text == "انتخاب میز مقصد":
            state['move_step'] = 'select_target'
            self.user_states[user_id] = state
            await update.message.reply_text(
                "میز مقصد را انتخاب کنید:",
                reply_markup=self.create_table_menu(lock_for_games=True)
            )
            return
            
        if 'move_step' in state and (text.startswith("میز") or text in ("میز آزاد", "PS", "فرمون")):
            clean_table_name = text.replace("🔒 ", "")
            
            if state['move_step'] == 'select_source':
                # بررسی وجود میز مبدأ
                if clean_table_name not in self.active_games and clean_table_name not in self.active_orders:
                    await update.message.reply_text("❌ میز انتخابی هیچ فعالیت فعالی ندارد!")
                    return
                    
                state['source_table'] = clean_table_name
                state['move_step'] = 'select_target'
                self.user_states[user_id] = state
                await update.message.reply_text(
                    f"میز مبدأ: {clean_table_name}\n"
                    "حالا میز مقصد را انتخاب کنید:",
                    reply_markup=self.create_table_menu(lock_for_games=True)
                )
                return
                
            elif state['move_step'] == 'select_target':
                if 'source_table' not in state:
                    await update.message.reply_text("❌ لطفاً ابتدا میز مبدأ را انتخاب کنید.")
                    return
                    
                source_table = state['source_table']
                
                # بررسی میز مقصد
                if clean_table_name == source_table:
                    await update.message.reply_text("❌ میز مبدأ و مقصد نمی‌توانند یکسان باشند!")
                    return
                    
                if self.is_game_active_on_table(clean_table_name):
                    await update.message.reply_text("❌ میز مقصد در حال حاضر بازی فعال دارد!")
                    return
                    
                # انجام جابه‌جایی
                await self.process_table_move(update, context, user_id, source_table, clean_table_name)
                return
                
        await update.message.reply_text("⛔ لطفاً از منو استفاده کنید.")

    async def process_table_move(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, source_table: str, target_table: str):
        username = self.get_user_info(update.effective_user)
        iran_time = self.get_iran_time()
        
        # جمع‌آوری اطلاعات قبل از جابه‌جایی
        had_game = source_table in self.active_games
        had_order = source_table in self.active_orders
        
        # انجام جابه‌جایی
        if had_game:
            self.active_games[target_table] = self.active_games.pop(source_table)
            game_info = self.active_games[target_table]
            player_display = self.format_player_history(game_info['player_groups'])
            
        if had_order:
            self.active_orders[target_table] = self.active_orders.pop(source_table)
            order_info = self.active_orders[target_table]
            items_count = len(order_info.get('items', []))
        
        # ارسال پیام به کانال
        message = (
            f"🔄 جابه‌جایی میز\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🔀 از میز {source_table} به میز {target_table}\n"
        )
        
        if had_game:
            message += (
                f"🎲 بازی منتقل شده: {player_display} نفر\n"
            )
            
        if had_order:
            message += (
                f"☕ سفارش منتقل شده: {items_count} آیتم\n"
            )
            
        message += (
            f"⏰ زمان: {iran_time}\n"
            f"👤 @{username}"
        )
        
        try:
            await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            
            self.clear_user_state(user_id)
            await update.message.reply_text(
                f"✅ جابه‌جایی میز با موفقیت انجام شد.\n"
                f"میز {source_table} آزاد شد و میز {target_table} قفل شد.",
                reply_markup=self.create_main_menu()
            )
        except Exception as e:
            logger.error(f"Error in table move: {e}")
            await update.message.reply_text(
                "❌ خطا در انجام جابه‌جایی. لطفاً دوباره تلاش کنید.",
                reply_markup=self.create_main_menu()
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
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
                    "🎮 میز بازی را انتخاب کنید:\n"
                    "🔒 = فقط برای بازی جدید اشغال است",
                    reply_markup=self.create_table_menu(lock_for_games=True)
                )
                return

            if text == "🏁 پایان بازی":
                self.user_states[user_id] = {'mode': 'game_end'}
                await update.message.reply_text(
                    "🏁 میز بازی را برای پایان انتخاب کنید:",
                    reply_markup=self.create_active_tables_menu("game")
                )
                return

            if text == "👥 مدیریت بازیکنان":
                await update.message.reply_text(
                    "👥 عملیات مورد نظر را انتخاب کنید:",
                    reply_markup=self.create_player_management_menu()
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

            if text == "🔄 جابه‌جایی میز":
                await self.handle_move_table(update, context, user_id, text, state)
                return

            # Player management options
            if text == "➕ افزودن بازیکن":
                self.user_states[user_id] = {'mode': 'player_management', 'player_mode': 'add'}
                await update.message.reply_text(
                    "➕ میز بازی را برای افزودن بازیکن انتخاب کنید:",
                    reply_markup=self.create_active_tables_menu("game")
                )
                return

            if text == "➖ کاهش بازیکن":
                self.user_states[user_id] = {'mode': 'player_management', 'player_mode': 'remove'}
                await update.message.reply_text(
                    "➖ میز بازی را برای کاهش بازیکن انتخاب کنید:",
                    reply_markup=self.create_active_tables_menu("game")
                )
                return

            # Order management options
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

            # Handle table selection
            if text.startswith("میز") or text in ("میز آزاد", "PS", "فرمون"):
                try:
                    clean_table_name = text.replace("🔒 ", "")
                    
                    if 'mode' not in state:
                        await update.message.reply_text("لطفاً ابتدا از منوی اصلی گزینه‌ای را انتخاب کنید.")
                        return
                    
                    if state['mode'] == 'game':
                        if self.is_game_active_on_table(clean_table_name):
                            table_status = self.get_table_status(clean_table_name)
                            await update.message.reply_text(
                                f"❌ میز «{clean_table_name}» در حال حاضر بازی فعال دارد!\n"
                                f"📊 وضعیت: {table_status}\n\n"
                                f"لطفاً میز دیگری انتخاب کنید.",
                                reply_markup=self.create_table_menu(lock_for_games=True)
                            )
                        else:
                            state['table'] = clean_table_name
                            self.user_states[user_id] = state
                            await update.message.reply_text("👥 تعداد بازیکنان را وارد کنید:")
                        return
                        
                    elif state['mode'] == 'order':
                        state['table'] = clean_table_name
                        self.user_states[user_id] = state
                        await update.message.reply_text(
                            "📋 دسته‌بندی را انتخاب کنید:",
                            reply_markup=self.create_category_menu()
                        )
                        return
                        
                    elif state['mode'] == 'game_end':
                        await self.handle_game_end(update, context, user_id, clean_table_name, state)
                        return
                        
                    elif state['mode'] == 'add_to_order':
                        await self.handle_add_to_order(update, context, user_id, clean_table_name, state)
                        return
                        
                    elif state['mode'] == 'edit_order':
                        await self.handle_edit_order(update, context, user_id, clean_table_name, state)
                        return

                    elif state['mode'] == 'player_management':
                        await self.handle_player_management(update, context, user_id, clean_table_name, state)
                        return
                        
                    elif state['mode'] == 'move_table':
                        await self.handle_move_table(update, context, user_id, clean_table_name, state)
                        return
                        
                    else:
                        await update.message.reply_text("⛔ حالت نامعتبر.")
                        return
                        
                except Exception as e:
                    logger.error(f"Error handling table selection: {e}")
                    await update.message.reply_text(
                        "❌ خطا در پردازش انتخاب میز. لطفاً دوباره تلاش کنید.",
                        reply_markup=self.create_main_menu()
                    )
                return

            # Handle specific mode flows
            if state.get('mode') == 'game' and 'table' in state and 'players' not in state:
                await self.handle_game_flow(update, context, user_id, text, state)
                return

            if state.get('mode') == 'player_management':
                await self.handle_player_management(update, context, user_id, text, state)
                return

            if state.get('mode') == 'order':
                await self.handle_order_flow(update, context, user_id, text, state)
                return

            if state.get('mode') == 'add_to_order':
                await self.handle_add_to_order(update, context, user_id, text, state)
                return

            if state.get('mode') == 'edit_order':
                if state.get('current_category') and text not in self.category_labels.values():
                    await self.add_item_to_order(update, user_id, text, state)
                else:
                    await self.handle_edit_order(update, context, user_id, text, state)
                return

            if state.get('mode') == 'move_table':
                await self.handle_move_table(update, context, user_id, text, state)
                return

            await update.message.reply_text("⛔ لطفاً از منو استفاده کنید یا دکمه بازگشت را بزنید.")
            
        except Exception as e:
            logger.error(f"Critical error in handle_message: {e}")
            try:
                await update.message.reply_text(
                    "❌ خطای غیرمنتظره رخ داد. لطفاً /start را بزنید.",
                    reply_markup=self.create_main_menu()
                )
            except:
                pass


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