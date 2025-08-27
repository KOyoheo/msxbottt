from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import BUTTONS

def get_main_keyboard():
    """Головна клавіатура"""
    keyboard = [
        [InlineKeyboardButton(BUTTONS['in_stock'], callback_data='in_stock')],
        [InlineKeyboardButton(BUTTONS['pre_order'], callback_data='pre_order')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard():
    """Клавіатура вибору способу оплати"""
    keyboard = [
        [InlineKeyboardButton(BUTTONS['cash_on_delivery'], callback_data='cash_on_delivery')],
        [InlineKeyboardButton(BUTTONS['prepayment'], callback_data='prepayment')],
        [InlineKeyboardButton(BUTTONS['back_to_main'], callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard():
    """Клавіатура підтвердження замовлення"""
    keyboard = [
        [InlineKeyboardButton(BUTTONS['confirm_order'], callback_data='confirm_order')],
        [InlineKeyboardButton(BUTTONS['back_to_main'], callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """Клавіатура адмін панелі"""
    keyboard = [
        [InlineKeyboardButton(BUTTONS['broadcast'], callback_data='admin_broadcast')],
        [InlineKeyboardButton(BUTTONS['view_orders'], callback_data='admin_view_orders')],
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton(BUTTONS['back_to_main'], callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    """Клавіатура з кнопкою назад"""
    keyboard = [
        [InlineKeyboardButton(BUTTONS['back_to_main'], callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_contact_keyboard():
    """Клавіатура для отримання контакту"""
    keyboard = [
        [KeyboardButton("📱 Поділитися контактом", request_contact=True)],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_simple_keyboard():
    """Проста клавіатура"""
    keyboard = [
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
