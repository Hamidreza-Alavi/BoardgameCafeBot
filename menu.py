from telegram import ReplyKeyboardMarkup, KeyboardButton
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
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)
    buttons = [[KeyboardButton(item)] for item in items.get(cat_key, [])]
    buttons.append([
        KeyboardButton("✅ پایان سفارش"),
        KeyboardButton("بازگشت")
    ])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)