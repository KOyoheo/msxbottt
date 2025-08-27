import logging
import asyncio
import signal
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, WELCOME_MESSAGE, SHOP_NAME
from database import Database
from keyboards import *

# Налаштування логування для продакшену
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('bot.log', encoding='utf-8', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Стани розмови
CHOOSING_OPTION, ENTERING_ORDER, CHOOSING_PAYMENT, ENTERING_ADDRESS, CONFIRMING_ORDER = range(5)

# Ініціалізація бази даних
db = Database()

# Словник для зберігання тимчасових даних користувачів
user_data = {}

# Статистика бота
bot_stats = {
    'start_time': datetime.now(),
    'total_users': 0,
    'total_orders': 0,
    'errors': 0
}

async def graceful_shutdown(signal, loop):
    """Граціозне завершення роботи бота"""
    logger.info(f"Отримано сигнал {signal.name}...")
    logger.info("Зупиняю бота...")
    
    # Зберігаємо статистику
    save_bot_stats()
    
    # Зупиняємо event loop
    loop.stop()
    logger.info("Бот зупинено.")

def save_bot_stats():
    """Збереження статистики бота"""
    try:
        stats_data = {
            'start_time': bot_stats['start_time'].isoformat(),
            'total_users': bot_stats['total_users'],
            'total_orders': bot_stats['total_orders'],
            'errors': bot_stats['errors'],
            'uptime_hours': (datetime.now() - bot_stats['start_time']).total_seconds() / 3600
        }
        
        with open('bot_stats.json', 'w', encoding='utf-8') as f:
            import json
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Статистика збережена: {stats_data}")
    except Exception as e:
        logger.error(f"Помилка збереження статистики: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початкова команда"""
    try:
        user = update.effective_user
        
        # Очищаємо попередні дані користувача
        if user.id in user_data:
            del user_data[user.id]
        
        db.add_user(user.id, user.username or "Невідомий", user.first_name or "Невідомий")
        bot_stats['total_users'] += 1
        
        logger.info(f"Користувач {user.id} (@{user.username}) запустив бота")
        
        await update.message.reply_text(
            WELCOME_MESSAGE,
            reply_markup=get_main_keyboard()
        )
        return CHOOSING_OPTION
    except Exception as e:
        logger.error(f"Помилка в команді start: {e}")
        bot_stats['errors'] += 1
        await update.message.reply_text("❌ Помилка запуску бота. Спробуйте ще раз.")
        return CHOOSING_OPTION

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник натискань кнопок"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == 'back_to_main':
            # Очищаємо дані користувача при поверненні на головну
            if user_id in user_data:
                del user_data[user_id]
            
            await query.edit_message_text(
                WELCOME_MESSAGE,
                reply_markup=get_main_keyboard()
            )
            return CHOOSING_OPTION
        
        elif query.data in ['in_stock', 'pre_order']:
            # Ініціалізуємо нове замовлення
            user_data[user_id] = {'order_type': query.data}
            
            message_text = "📝 Введіть деталі вашого замовлення:\n\n"
            if query.data == 'in_stock':
                message_text += "🏀 Що саме вас цікавить з наявності?\n"
            else:
                message_text += "📋 Що саме ви хочете замовити?\n"
            
            message_text += "\n💡 Можете прикріпити фото товару для кращого розуміння!"
            
            await query.edit_message_text(
                message_text,
                reply_markup=get_back_keyboard()
            )
            return ENTERING_ORDER
        
        elif query.data in ['cash_on_delivery', 'prepayment']:
            if user_id in user_data and 'order_type' in user_data[user_id]:
                user_data[user_id]['payment_method'] = query.data
                
                payment_text = "💳 Оберіть спосіб оплати:\n\n"
                if query.data == 'cash_on_delivery':
                    payment_text += "💵 Накладний платіж - оплата при отриманні"
                else:
                    payment_text += "💳 Передплата - оплата заздалегідь"
                
                await query.edit_message_text(
                    payment_text,
                    reply_markup=get_back_keyboard()
                )
                
                await query.message.reply_text(
                    "📍 Введіть адресу доставки або відділення пошти:"
                )
                return ENTERING_ADDRESS
            else:
                # Якщо немає даних замовлення, повертаємося на головну
                await query.edit_message_text(
                    "❌ Помилка: спочатку створіть замовлення",
                    reply_markup=get_main_keyboard()
                )
                return CHOOSING_OPTION
        
        elif query.data == 'confirm_order':
            if user_id in user_data and all(key in user_data[user_id] for key in ['order_type', 'payment_method', 'address', 'order_details']):
                order_data = user_data[user_id]
                
                # Додаємо інформацію про користувача
                user = update.effective_user
                order_data['username'] = user.username or "Невідомий"
                order_data['first_name'] = user.first_name or "Невідомий"
                
                # Створюємо замовлення
                order_id = db.add_order(user_id, order_data)
                bot_stats['total_orders'] += 1
                
                # Відправляємо підтвердження користувачу
                confirmation_text = f"""
✅ Ваше замовлення підтверджено!

🆔 Номер замовлення: {order_id}
📦 Тип: {'В наявності' if order_data['order_type'] == 'in_stock' else 'Під замовлення'}
💳 Спосіб оплати: {'Накладний платіж' if order_data['payment_method'] == 'cash_on_delivery' else 'Передплата'}
📍 Адреса: {order_data.get('address', 'Не вказано')}
📝 Деталі: {order_data.get('order_details', 'Не вказано')}

🎉 Дякуємо за замовлення! Ми зв'яжемося з вами найближчим часом.
                """
                
                await query.edit_message_text(
                    confirmation_text,
                    reply_markup=get_main_keyboard()
                )
                
                # Відправляємо повідомлення адміну
                await send_admin_notification(context, order_id, user_id, order_data)
                
                # Очищаємо дані користувача
                if user_id in user_data:
                    del user_data[user_id]
                
                return CHOOSING_OPTION
            else:
                # Якщо не всі дані заповнені
                await query.edit_message_text(
                    "❌ Помилка: не всі дані замовлення заповнені",
                    reply_markup=get_main_keyboard()
                )
                return CHOOSING_OPTION
        
        elif query.data == 'admin_panel':
            if user_id in ADMIN_IDS:
                await query.edit_message_text(
                    "🔧 Адмін панель\n\nОберіть дію:",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await query.edit_message_text(
                    "❌ У вас немає доступу до адмін панелі!",
                    reply_markup=get_back_keyboard()
                )
        
        elif query.data == 'admin_broadcast':
            if user_id in ADMIN_IDS:
                await query.edit_message_text(
                    "📢 Розсилка\n\nОберіть тип розсилки:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Тільки текст", callback_data='broadcast_text_only')],
                        [InlineKeyboardButton("📸 Фото з текстом", callback_data='broadcast_photo_text')],
                        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
                    ])
                )
        
        elif query.data == 'broadcast_text_only':
            if user_id in ADMIN_IDS:
                await query.edit_message_text(
                    "📢 Розсилка тексту\n\nВведіть текст повідомлення для розсилки всім користувачам:",
                    reply_markup=get_back_keyboard()
                )
                context.user_data['admin_state'] = 'waiting_broadcast_text'
        
        elif query.data == 'broadcast_photo_text':
            if user_id in ADMIN_IDS:
                await query.edit_message_text(
                    "📸 Розсилка фото з текстом\n\nСпочатку прикріпіть фото:",
                    reply_markup=get_back_keyboard()
                )
                context.user_data['admin_state'] = 'waiting_broadcast_photo'
        
        elif query.data == 'confirm_broadcast':
            if user_id in ADMIN_IDS:
                text = context.user_data.get('broadcast_text', '')
                photo_file_id = context.user_data.get('broadcast_photo')
                
                if not text:
                    await query.edit_message_text(
                        "❌ Помилка: текст для розсилки не знайдено",
                        reply_markup=get_admin_keyboard()
                    )
                    return
                
                # Виконуємо розсилку
                await query.edit_message_text(
                    "📢 Виконую розсилку...",
                    reply_markup=get_back_keyboard()
                )
                
                success_count, error_count = await execute_broadcast(context, text, photo_file_id)
                
                # Очищаємо дані розсилки
                if 'broadcast_text' in context.user_data:
                    del context.user_data['broadcast_text']
                if 'broadcast_photo' in context.user_data:
                    del context.user_data['broadcast_photo']
                if 'admin_state' in context.user_data:
                    del context.user_data['admin_state']
                
                result_text = f"""
✅ Розсилка завершена!

📊 Результат:
✅ Успішно відправлено: {success_count}
❌ Помилки: {error_count}

📢 Повідомлення відправлено всім користувачам
                """
                
                await query.edit_message_text(
                    result_text,
                    reply_markup=get_admin_keyboard()
                )
        
        elif query.data == 'change_broadcast':
            if user_id in ADMIN_IDS:
                # Очищаємо дані та повертаємося до вибору типу розсилки
                if 'broadcast_text' in context.user_data:
                    del context.user_data['broadcast_text']
                if 'broadcast_photo' in context.user_data:
                    del context.user_data['broadcast_photo']
                
                await query.edit_message_text(
                    "📢 Розсилка\n\nОберіть тип розсилки:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Тільки текст", callback_data='broadcast_text_only')],
                        [InlineKeyboardButton("📸 Фото з текстом", callback_data='broadcast_photo_text')],
                        [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
                    ])
                )
        
        elif query.data == 'admin_view_orders':
            if user_id in ADMIN_IDS:
                orders = db.get_recent_orders(10)
                if orders:
                    orders_text = "📋 Останні 10 замовлень:\n\n"
                    for order in orders:
                        orders_text += f"""
🆔 {order['id']}
👤 {order['first_name']} (@{order['username']})
📅 {order['created_date'][:10]}
📦 {'В наявності' if order['order_data']['order_type'] == 'in_stock' else 'Під замовлення'}
💳 {'Накладний платіж' if order['order_data']['payment_method'] == 'cash_on_delivery' else 'Передплата'}
📍 {order['order_data'].get('address', 'Не вказано')}
📝 {order['order_data'].get('order_details', 'Не вказано')}
🔗 ID користувача: {order['user_id']}
                        """
                        orders_text += "\n" + "─" * 50 + "\n"
                    
                    orders_text += "\n💬 Для відправки повідомлення замовнику використовуйте:\n"
                    orders_text += "/message НОМЕР_ЗАМОВЛЕННЯ ТЕКСТ_ПОВІДОМЛЕННЯ"
                    
                    # Розбиваємо на частини, якщо текст занадто довгий
                    if len(orders_text) > 4096:
                        for i in range(0, len(orders_text), 4096):
                            await query.message.reply_text(orders_text[i:i+4096])
                    else:
                        await query.edit_message_text(orders_text, reply_markup=get_admin_keyboard())
                else:
                    await query.edit_message_text(
                        "📭 Поки що немає замовлень",
                        reply_markup=get_admin_keyboard()
                    )
        
        elif query.data == 'admin_stats':
            if user_id in ADMIN_IDS:
                uptime_hours = (datetime.now() - bot_stats['start_time']).total_seconds() / 3600
                stats_text = f"""
📊 Статистика бота:

⏰ Час роботи: {uptime_hours:.1f} годин
👥 Всього користувачів: {bot_stats['total_users']}
📦 Всього замовлень: {bot_stats['total_orders']}
❌ Помилок: {bot_stats['errors']}
🔄 Статус: Активний
                """
                
                await query.edit_message_text(
                    stats_text,
                    reply_markup=get_admin_keyboard()
                )
    
    except Exception as e:
        logger.error(f"Помилка в button_handler: {e}")
        bot_stats['errors'] += 1
        try:
            await query.edit_message_text(
                "❌ Помилка обробки запиту. Спробуйте ще раз.",
                reply_markup=get_main_keyboard()
            )
        except:
            pass
        return CHOOSING_OPTION

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник текстових повідомлень"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        # Перевіряємо, чи це адмін команда
        if user_id in ADMIN_IDS and context.user_data.get('admin_state') == 'waiting_broadcast_text':
            await handle_broadcast_confirmation(update, context)
            return
        
        # Обробка кнопки "Назад"
        if text == "🔙 Назад":
            await update.message.reply_text(
                WELCOME_MESSAGE,
                reply_markup=get_main_keyboard()
            )
            return CHOOSING_OPTION
        
        # Обробка введення деталей замовлення
        if user_id in user_data and 'order_type' in user_data[user_id] and 'order_details' not in user_data[user_id]:
            user_data[user_id]['order_details'] = text
            
            await update.message.reply_text(
                "💳 Тепер оберіть спосіб оплати:",
                reply_markup=get_payment_keyboard()
            )
            return CHOOSING_PAYMENT
        
        # Обробка введення адреси
        if user_id in user_data and 'payment_method' in user_data[user_id] and 'address' not in user_data[user_id]:
            user_data[user_id]['address'] = text
            
            # Показуємо деталі замовлення для підтвердження
            order_data = user_data[user_id]
            summary_text = f"""
📋 Деталі вашого замовлення:

🏀 Тип: {'В наявності' if order_data['order_type'] == 'in_stock' else 'Під замовлення'}
💳 Спосіб оплати: {'Накладний платіж' if order_data['payment_method'] == 'cash_on_delivery' else 'Передплата'}
📍 Адреса: {order_data['address']}
📝 Деталі: {order_data.get('order_details', 'Не вказано')}

✅ Все правильно? Підтвердіть замовлення:
            """
            
            await update.message.reply_text(
                summary_text,
                reply_markup=get_confirm_keyboard()
            )
            return CONFIRMING_ORDER
        
        # Якщо не впізнали повідомлення, повертаємося на головну
        await update.message.reply_text(
            "❓ Не зрозумів ваше повідомлення. Повертаюся на головну.",
            reply_markup=get_main_keyboard()
        )
        return CHOOSING_OPTION
    
    except Exception as e:
        logger.error(f"Помилка в handle_message: {e}")
        bot_stats['errors'] += 1
        await update.message.reply_text(
            "❌ Помилка обробки повідомлення. Спробуйте ще раз.",
            reply_markup=get_main_keyboard()
        )
        return CHOOSING_OPTION

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник фотографій"""
    try:
        user_id = update.effective_user.id
        
        if user_id in user_data and 'order_type' in user_data[user_id]:
            # Зберігаємо фото
            photo = update.message.photo[-1]
            file_id = photo.file_id
            
            if 'photos' not in user_data[user_id]:
                user_data[user_id]['photos'] = []
            user_data[user_id]['photos'].append(file_id)
            
            await update.message.reply_text(
                "📸 Фото додано! Тепер введіть деталі замовлення:"
            )
    except Exception as e:
        logger.error(f"Помилка в handle_photo: {e}")
        bot_stats['errors'] += 1
        await update.message.reply_text(
            "❌ Помилка обробки фото. Спробуйте ще раз."
        )

async def handle_broadcast_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Підтвердження розсилки"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        context.user_data['broadcast_text'] = text
        
        await update.message.reply_text(
            f"📢 Текст для розсилки:\n\n{text}\n\n✅ Все правильно? Відправляємо?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Так, відправити", callback_data='confirm_broadcast')],
                [InlineKeyboardButton("❌ Ні, змінити", callback_data='change_broadcast')]
            ])
        )
    except Exception as e:
        logger.error(f"Помилка в handle_broadcast_confirmation: {e}")
        bot_stats['errors'] += 1

async def handle_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник фото для розсилки"""
    try:
        user_id = update.effective_user.id
        
        if user_id in ADMIN_IDS and context.user_data.get('admin_state') == 'waiting_broadcast_photo':
            photo = update.message.photo[-1]
            file_id = photo.file_id
            
            context.user_data['broadcast_photo'] = file_id
            
            await update.message.reply_text(
                "📸 Фото додано! Тепер введіть текст для розсилки:"
            )
            context.user_data['admin_state'] = 'waiting_broadcast_text'
    except Exception as e:
        logger.error(f"Помилка в handle_broadcast_photo: {e}")
        bot_stats['errors'] += 1

async def execute_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str, photo_file_id: str = None):
    """Виконання розсилки всім користувачам"""
    try:
        users = db.get_all_users()
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                if photo_file_id:
                    # Відправляємо фото з текстом
                    await context.bot.send_photo(
                        chat_id=user['user_id'],
                        photo=photo_file_id,
                        caption=text
                    )
                else:
                    # Відправляємо тільки текст
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=text
                    )
                success_count += 1
                
                # Невелика затримка для уникнення спаму
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Помилка відправки розсилки користувачу {user['user_id']}: {e}")
        
        return success_count, error_count
    except Exception as e:
        logger.error(f"Помилка в execute_broadcast: {e}")
        bot_stats['errors'] += 1
        return 0, 0

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, order_id: str, user_id: int, order_data: dict):
    """Відправка повідомлення адміну про нове замовлення"""
    try:
        admin_message = f"""
🆕 НОВЕ ЗАМОВЛЕННЯ!

🆔 Номер: {order_id}
👤 Користувач: {order_data.get('username', 'Невідомий')}
🆔 ID користувача: {user_id}
📦 Тип: {'В наявності' if order_data['order_type'] == 'in_stock' else 'Під замовлення'}
💳 Спосіб оплати: {'Накладний платіж' if order_data['payment_method'] == 'cash_on_delivery' else 'Передплата'}
📍 Адреса: {order_data.get('address', 'Не вказано')}
📝 Деталі: {order_data.get('order_details', 'Не вказано')}

💬 Для відправки повідомлення замовнику використовуйте:
/message {order_id} ТЕКСТ_ПОВІДОМЛЕННЯ
        """
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Помилка відправки повідомлення адміну {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Помилка в send_admin_notification: {e}")
        bot_stats['errors'] += 1

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin"""
    try:
        user_id = update.effective_user.id
        
        if user_id in ADMIN_IDS:
            await update.message.reply_text(
                "🔧 Адмін панель\n\nОберіть дію:",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text("❌ У вас немає доступу до адмін панелі!")
    except Exception as e:
        logger.error(f"Помилка в admin_command: {e}")
        bot_stats['errors'] += 1

async def message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /message для адмінів"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас немає доступу до цієї команди!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ Неправильний формат! Використовуйте:\n"
                "/message НОМЕР_ЗАМОВЛЕННЯ ТЕКСТ_ПОВІДОМЛЕННЯ"
            )
            return
        
        order_id = context.args[0]
        message_text = ' '.join(context.args[1:])
        
        order = db.get_order(order_id)
        if not order:
            await update.message.reply_text("❌ Замовлення не знайдено!")
            return
        
        try:
            await context.bot.send_message(
                chat_id=order['user_id'],
                text=f"💬 Повідомлення від {SHOP_NAME}:\n\n{message_text}"
            )
            await update.message.reply_text(f"✅ Повідомлення відправлено замовнику {order_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Помилка відправки: {e}")
    except Exception as e:
        logger.error(f"Помилка в message_command: {e}")
        bot_stats['errors'] += 1

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /broadcast для адмінів"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас немає доступу до цієї команди!")
            return
        
        await update.message.reply_text(
            "📢 Розсилка\n\nОберіть тип розсилки:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Тільки текст", callback_data='broadcast_text_only')],
                [InlineKeyboardButton("📸 Фото з текстом", callback_data='broadcast_photo_text')],
                [InlineKeyboardButton("🔙 Назад", callback_data='admin_panel')]
            ])
        )
    except Exception as e:
        logger.error(f"Помилка в broadcast_command: {e}")
        bot_stats['errors'] += 1

async def view_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /view_users для адмінів"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас немає доступу до цієї команди!")
            return
        
        users = db.get_all_users()
        if users:
            users_text = f"👥 Всього користувачів: {len(users)}\n\n"
            for user in users:
                users_text += f"""
👤 {user['first_name']} (@{user['username']})
🆔 ID: {user['user_id']}
📅 Дата реєстрації: {user['joined_date'][:10]}
📦 Замовлень: {user['orders_count']}
                """
                users_text += "\n" + "─" * 30 + "\n"
            
            # Розбиваємо на частини, якщо текст занадто довгий
            if len(users_text) > 4096:
                for i in range(0, len(users_text), 4096):
                    await update.message.reply_text(users_text[i:i+4096])
            else:
                await update.message.reply_text(users_text)
        else:
            await update.message.reply_text("📭 Поки що немає користувачів")
    except Exception as e:
        logger.error(f"Помилка в view_users_command: {e}")
        bot_stats['errors'] += 1

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats для адмінів"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас немає доступу до цієї команди!")
            return
        
        uptime_hours = (datetime.now() - bot_stats['start_time']).total_seconds() / 3600
        stats_text = f"""
📊 Статистика бота:

⏰ Час роботи: {uptime_hours:.1f} годин
👥 Всього користувачів: {bot_stats['total_users']}
📦 Всього замовлень: {bot_stats['total_orders']}
❌ Помилок: {bot_stats['errors']}
🔄 Статус: Активний
        """
        
        await update.message.reply_text(stats_text)
    except Exception as e:
        logger.error(f"Помилка в stats_command: {e}")
        bot_stats['errors'] += 1

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ping для перевірки роботи бота"""
    try:
        start_time = datetime.now()
        await update.message.reply_text("🏓 Pong!")
        end_time = datetime.now()
        
        response_time = (end_time - start_time).total_seconds() * 1000
        
        await update.message.reply_text(f"⏱️ Час відповіді: {response_time:.2f} мс")
    except Exception as e:
        logger.error(f"Помилка в ping_command: {e}")
        bot_stats['errors'] += 1

def main():
    """Головна функція"""
    try:
        # Налаштування сигналів для граціозного завершення
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(graceful_shutdown(s, loop)))
        
        # Створюємо застосунок
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Додаємо обробники
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                CHOOSING_OPTION: [
                    CallbackQueryHandler(button_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
                ],
                ENTERING_ORDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                    MessageHandler(filters.PHOTO, handle_photo),
                    CallbackQueryHandler(button_handler)
                ],
                CHOOSING_PAYMENT: [
                    CallbackQueryHandler(button_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
                ],
                ENTERING_ADDRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                    CallbackQueryHandler(button_handler)
                ],
                CONFIRMING_ORDER: [
                    CallbackQueryHandler(button_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
                ]
            },
            fallbacks=[CommandHandler('start', start)]
        )
        
        application.add_handler(conv_handler)
        
        # Додаємо обробник фото для розсилки (поза ConversationHandler)
        application.add_handler(MessageHandler(filters.PHOTO, handle_broadcast_photo))
        
        # Додаємо команди адміна
        application.add_handler(CommandHandler('admin', admin_command))
        application.add_handler(CommandHandler('message', message_command))
        application.add_handler(CommandHandler('broadcast', broadcast_command))
        application.add_handler(CommandHandler('view_users', view_users_command))
        application.add_handler(CommandHandler('stats', stats_command))
        application.add_handler(CommandHandler('ping', ping_command))
        
        # Запускаємо бота
        logger.info("🚀 Бот запущений!")
        logger.info(f"👥 Адміністратори: {ADMIN_IDS}")
        logger.info(f"🏀 Назва магазину: {SHOP_NAME}")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Критична помилка в main: {e}")
        bot_stats['errors'] += 1
        sys.exit(1)

if __name__ == '__main__':
    main()
