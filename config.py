import os
from dotenv import load_dotenv

load_dotenv()

# Конфігурація бота - справжні дані
BOT_TOKEN = "8418124569:AAHX5mo5yxoKGqTqpdh2BEmLWURB6TstQS8"
ADMIN_IDS = [709990491]

# Назва магазину
SHOP_NAME = "🏀 Hoop Mania 🏀"
SHOP_DESCRIPTION = "Ваш надійний партнер у світі баскетболу! 🎯"

# Повідомлення
WELCOME_MESSAGE = f"""
🎉 Вітаємо у {SHOP_NAME}! 🎉

{SHOP_DESCRIPTION}

Оберіть, що вас цікавить:
"""

# Кнопки
BUTTONS = {
    'in_stock': '📦 В наявності',
    'pre_order': '📋 Під замовлення',
    'cash_on_delivery': '💵 Накладний платіж',
    'prepayment': '💳 Передплата',
    'confirm_order': '✅ Підтвердити замовлення',
    'admin_panel': '🔧 Адмін панель',
    'broadcast': '📢 Розсилка',
    'view_orders': '📋 Переглянути замовлення',
    'back_to_main': '🔙 На головну'
}
