from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json

def get_table_menu():
    buttons = []

    for i in range(1, 16):
        buttons.append([InlineKeyboardButton(f"میز {i}", callback_data=f"table_{i}")])

    buttons.append([InlineKeyboardButton("PS", callback_data="table_ps")])
    buttons.append([InlineKeyboardButton("فرمون", callback_data="table_wheel")])

    return InlineKeyboardMarkup(buttons)

def get_item_menu():
    with open("items.json", encoding="utf-8") as f:
        items = json.load(f)

    buttons = []
    for category in items.values():
        for item in category:
            buttons.append([InlineKeyboardButton(item, callback_data=f"item_{item}")])

    buttons.append([InlineKeyboardButton("✅ پایان سفارش", callback_data="done_order")])
    return InlineKeyboardMarkup(buttons)
