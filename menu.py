from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json

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
    buttons = [[InlineKeyboardButton(f"میز {i}", callback_data=f"table_{i}")] for i in range(1, 17)]
    buttons += [
        [InlineKeyboardButton("میز آزاد", callback_data="table_free")],
        [InlineKeyboardButton("PS", callback_data="table_ps")],
        [InlineKeyboardButton("فرمون", callback_data="table_wheel")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_category_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"cat_{key}")]
        for key, label in CATEGORY_LABELS.items()
    ])

def get_item_menu_by_category(cat_key):
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
    buttons = [[InlineKeyboardButton(item, callback_data=f"item_{item}")] for item in items.get(cat_key, [])]
    buttons.append([
        InlineKeyboardButton("✅ پایان سفارش", callback_data="done_order"),
        InlineKeyboardButton("↩ بازگشت به دسته‌ها", callback_data="back_to_categories")
    ])
    return InlineKeyboardMarkup(buttons)