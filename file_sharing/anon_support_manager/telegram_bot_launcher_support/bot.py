import logging
import os
import django
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from django.conf import settings
from anon_support_manager.models import User, Ticket, Operator  # Импортируем модель Message
from django.utils import timezone
from asgiref.sync import sync_to_async
import base64
from channels.layers import get_channel_layer


# Установка переменной окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'file_sharing.settings')
django.setup()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)  # Для новых версий
logging.getLogger('telegram').setLevel(logging.WARNING)  # Для старых версий
# Асинхронные функции взаимодействия с базой данных


async def send_message_to_websocket(ticket_id, message):
    channel_layer = get_channel_layer()
    # Проверяем, является ли сообщение изображением
    if isinstance(message, dict) and 'image_data' in message:
        await channel_layer.group_send(
            f"support_{ticket_id}",
            {
                "type": "image_message",  # Новый тип для обработки изображений
                "image_data": message['image_data']
            }
        )
    else:
        await channel_layer.group_send(
            f"support_{ticket_id}",
            {
                "type": "chat_message",
                "message": message
            }
        )



async def get_or_create_user(user_id, username):
    user, created = await sync_to_async(User.objects.get_or_create)(user_id=user_id, defaults={'username': username})
    if created:
        logger.info(f"Создан новый пользователь: {username} (ID: {user_id})")
    else:
        logger.info(f"Найден существующий пользователь: {username} (ID: {user_id})")
        user.username = username
        await sync_to_async(user.save)()
    return user

async def get_operator_by_user(user):
    try:
        operator = await sync_to_async(Operator.objects.get)(user=user)
        logger.info(f"Найден оператор для пользователя: {user.username}")
        return operator
    except Operator.DoesNotExist:
        logger.warning(f"Оператор для пользователя {user.username} не найден.")
        return None
    
# Основные команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает бот и регистрирует пользователя."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    user = await get_or_create_user(user_id, username)

    welcome_message = "Добро пожаловать! Вы можете задать вопрос, и мы вам поможем."
    await update.message.reply_text(welcome_message)
    logger.info(f"Пользователь {username} (ID: {user_id}) запустил бота.")

    # Проверяем, является ли пользователь оператором
    operator = await get_operator_by_user(user)
    if operator:
        await operator_menu(update, context)

async def operator_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню оператора с доступными действиями."""
    user_id = update.effective_user.id
    operator = await get_operator_by_user(await get_or_create_user(user_id, update.effective_user.username))
    # Определяем набор кнопок в зависимости от статуса оператора
    if operator.is_active:
        # Оператор на смене - показываем кнопку "Закончить смену"
        keyboard = [
            [KeyboardButton("Закончить смену")],
            [KeyboardButton("Проверить тикеты")],
        ]
    else:
        # Оператор не на смене - показываем кнопку "Начать смену"
        keyboard = [
            [KeyboardButton("Начать смену")],
            [KeyboardButton("Проверить тикеты")],
        ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def toggle_operator_shift(update: Update, context: ContextTypes.DEFAULT_TYPE, start: bool):
    """Включает или выключает смену оператора."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    user = await get_or_create_user(user_id, username)
    operator = await get_operator_by_user(user)

    if operator:
        if start:
            # Если оператор хочет начать смену
            if operator.is_active:
                # Оператор уже на смене
                await update.message.reply_text("Смена уже начата.")
                return
            # Начинаем смену
            operator.is_active = True
            await sync_to_async(operator.save)()
            await update.message.reply_text("Смена начата.")
            logger.info(f"Оператор {user_id} начал смену.")
            await operator_menu(update, context)
            await send_available_tickets(update, context)
        else:
            # Если оператор хочет закончить смену
            if not operator.is_active:
                # Оператор уже завершил смену
                await update.message.reply_text("Смена уже завершена.")
                return
            # Завершаем смену
            operator.is_active = False
            await sync_to_async(operator.save)()
            await update.message.reply_text("Смена завершена.")
            logger.info(f"Оператор {user_id} завершил смену.")
            await operator_menu(update, context)
    else:
        logger.warning(f"Пользователь {user_id} попытался изменить смену, не будучи оператором.")
        await update.message.reply_text("Вы не являетесь оператором.")

# Вызываем одну функцию с параметром для смены
async def start_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_operator_shift(update, context, start=True)

async def end_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_operator_shift(update, context, start=False)


async def send_available_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет доступные тикеты активным операторам."""
    logger.info(f"Пользователь {update.effective_user.id} запросил доступные тикеты.")

    available_tickets = await sync_to_async(list)(Ticket.objects.filter(status='new', assigned_user__isnull=True))
    active_operators = await sync_to_async(list)(Operator.objects.filter(is_active=True))

    if not available_tickets:
        logger.info("Нет доступных тикетов.")
        await update.message.reply_text("Доступных тикетов сейчас нет.")
        return

    for operator in active_operators:
        user = await sync_to_async(lambda: operator.user)()

        if not user:
            logger.warning(f"У оператора {operator.id} нет связанного пользователя.")
            continue

        for ticket in available_tickets:
            keyboard = [
                [InlineKeyboardButton("Взять в работу", callback_data=f"take_{ticket.ticket_id}")],
                [InlineKeyboardButton("Закрыть тикет", callback_data=f"close_{ticket.ticket_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_message(
                    chat_id=user.user_id,
                    text=f"Доступный тикет: #{ticket.ticket_id}\nВопрос: {ticket.question or 'Нет вопроса'}",
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлен тикет #{ticket.ticket_id} оператору {user.username}.")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения оператору {user.username}: {e}")

            available_tickets.remove(ticket)
            break

    if available_tickets:
        logger.info("Некоторые тикеты не были распределены из-за отсутствия доступных операторов.")
        await update.message.reply_text("Некоторые тикеты не были распределены из-за отсутствия доступных операторов.")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает сообщения от пользователей и операторов."""
    user_id = update.effective_user.id
    user = await get_or_create_user(user_id, update.effective_user.username)
    
    # Обработка текстовых сообщений
    question = update.message.text
    logger.info(f"Получено сообщение от пользователя {user.username} ({user_id}): {question}")

    operator = await get_operator_by_user(user)
    if operator:
        logger.info(f"Пользователь {user.username} является оператором.")
        if question == "Начать смену":
            logger.info(f"Оператор {user.username} начал смену.")
            await start_shift(update, context)
            return
        elif question == "Закончить смену":
            logger.info(f"Оператор {user.username} завершил смену.")
            await end_shift(update, context)
            return
        elif question == "Проверить тикеты":
            logger.info(f"Оператор {user.username} проверяет тикеты.")
            await send_available_tickets(update, context)
            return
        else:
            return
        
    # Проверяем, пришло ли изображение
    if update.message.photo:
        document = update.message.photo[-1]
        file_id = document.file_id  # Получаем самое высокое качество изображения
        photo = await document.get_file()
        logger.info(f"Получено изображение от пользователя {user.username} ({user_id}).")

        # Получаем изображение как байтовый массив
        image_data = await photo.download_as_bytearray()
        
        # Если нужно отправить в формате base64
        encoded_image_data = base64.b64encode(image_data).decode('utf-8')

        # Ищем открытый тикет
        open_ticket = await sync_to_async(lambda: Ticket.objects.filter(user=user, status__in=['in_progress', 'new']).first())()
        if open_ticket:
            ticket_id = open_ticket.ticket_id  # Получаем идентификатор тикета
            await sync_to_async(open_ticket.add_message)(user, "Изображение отправлено.")  # Сохраняем сообщение
            operator_user = await sync_to_async(lambda: open_ticket.assigned_user)()

            # Отправляем изображение оператору
            await context.bot.send_photo(chat_id=operator_user.user_id, photo=file_id, caption=f"Пользователь #{ticket_id} отправил изображение.")

            # Отправляем данные изображения в вебсокет
            await send_message_to_websocket(ticket_id, {'image_data': encoded_image_data})
        else:
            # Обработка случая, когда открытого тикета нет
            await update.message.reply_text("Пожалуйста, сначала создайте тикет.")
        return

    # Проверяем, есть ли открытый тикет у пользователя
    open_ticket = await sync_to_async(lambda: Ticket.objects.filter(user=user, status__in=['in_progress', 'new']).first())()
    if open_ticket:
        ticket_id = await sync_to_async(lambda: open_ticket.ticket_id)()
        logger.info(f"Найден открытый тикет #{ticket_id} у пользователя {user.username}.")
        operator_user = await sync_to_async(lambda: open_ticket.assigned_user)()
        
        # Сохранение сообщения в истории тикета
        await sync_to_async(open_ticket.add_message)(user, question)
        
        if operator_user:
            keyboard = [[InlineKeyboardButton("Завершить диалог", callback_data=f"end_dialog_{ticket_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            logger.info(f"Сообщение пользователя {user.username} по тикету #{ticket_id} отправлено оператору {operator_user.username}.")
            await context.bot.send_message(chat_id=operator_user.user_id, text=f"Пользователь #{ticket_id} спросил: {question}", reply_markup=reply_markup)

            # Отправляем текстовое сообщение в вебсокет
            await send_message_to_websocket(ticket_id, {'message': question})
        else:
            logger.info(f"Сообщение пользователя {user.username} по тикету #{ticket_id} отправлено активным операторам.")
            await notify_operators_of_user_message(context, ticket_id, user_id, question)
    else:
        # Если открытого тикета нет, создаём новый
        ticket = await sync_to_async(Ticket.objects.create)(
            user=user,
            question=question,
            status='new',
            created_at=timezone.now()
        )
        ticket_id = ticket.ticket_id  # Присваиваем ticket_id нового тикета
        logger.info(f"Создан новый тикет #{ticket_id} для пользователя {user.username}.")

        # Сохранение сообщения в истории нового тикета
        await sync_to_async(ticket.add_message)(user, question)
        
        await notify_operators(context, ticket.ticket_id, user_id, question)
        logger.info(f"Уведомлены операторы о новом тикете #{ticket.ticket_id} от пользователя {user.username}.")
        await update.message.reply_text("Ваш вопрос был зарегистрирован. Ожидайте ответа от оператора.")


async def notify_operators_of_user_message(context: ContextTypes.DEFAULT_TYPE, ticket_id: int, user_id: int, question: str) -> None:
    """Уведомляет операторов о сообщении от пользователя."""
    logger.info(f"Уведомление операторов о новом сообщении от пользователя {user_id} по тикету #{ticket_id}")
    
    operators = await sync_to_async(list)(Operator.objects.filter(is_active=True))
    if not operators:
        logger.warning("Нет активных операторов для уведомления.")
        return

    for operator in operators:
        chat_id = await sync_to_async(lambda: operator.user.user_id)()
        await context.bot.send_message(chat_id=chat_id, text=f"#{ticket_id}: {question}")
        logger.info(f"Оператор {chat_id} уведомлен о новом сообщении.")



async def notify_operators(context: ContextTypes.DEFAULT_TYPE, ticket_id: int, user_id: int, question: str) -> None:
    """Уведомляет операторов о новом тикете."""
    logger.info(f"Уведомление операторов о новом тикете #{ticket_id} от пользователя {user_id}")

    operators = await sync_to_async(list)(Operator.objects.filter(is_active=True))
    if not operators:
        logger.warning("Нет активных операторов для уведомления о новом тикете.")
        return

    for operator in operators:
        keyboard = [
            [InlineKeyboardButton("Взять в работу", callback_data=f"take_{ticket_id}")],
            [InlineKeyboardButton("Закрыть тикет", callback_data=f"close_{ticket_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=await sync_to_async(lambda: operator.user.user_id)(),
            text=f"👤 Новый вопрос от пользователя: {user_id}\n💬 Вопрос: {question}\n📝 Номер тикета: {ticket_id}",
            reply_markup=reply_markup
        )
        logger.info(f"Оператор {operator.user.user_id} уведомлен о новом тикете #{ticket_id}.")


async def end_dialog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает завершение диалога по запросу оператора."""
    query = update.callback_query
    await query.answer()
    try:
        ticket_id = int(query.data.split("_")[2])
        ticket = await sync_to_async(Ticket.objects.get)(ticket_id=ticket_id)
        
        if ticket.status != 'closed':
            ticket.status = 'closed'
            operator_id = await sync_to_async(lambda: ticket.assigned_user.user_id)()
            await context.bot.send_message(chat_id=operator_id, text="Диалог завершен.")
            await query.edit_message_text(f"Диалог по тикету #{ticket_id} завершен.")

            await sync_to_async(ticket.save)()
            logger.info(f"Диалог по тикету #{ticket_id} завершен оператором {operator_id}.")
        else:
            await query.edit_message_text(f"Тикет #{ticket_id} уже закрыт.")
    except (ValueError, Ticket.DoesNotExist) as e:
        logger.error(f"Ошибка при завершении диалога: {e}")
        await query.edit_message_text("Ошибка при завершении диалога. Тикет не найден.")


async def take_ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос оператора на взятие тикета в работу."""
    query = update.callback_query
    await query.answer()

    try:
        ticket_id = int(query.data.split("_")[1])
        ticket = await sync_to_async(Ticket.objects.get)(ticket_id=ticket_id)
        question = await sync_to_async(lambda: ticket.question)()

        operator = await get_operator_by_user(await get_or_create_user(update.effective_user.id, update.effective_user.username))
        work_operator = await sync_to_async(lambda: ticket.assigned_user)()

        if work_operator is None:
            ticket.status = 'in_progress'
            ticket.assigned_user = await sync_to_async(lambda: operator.user)()
            keyboard = [
                [
                    InlineKeyboardButton("Закрыть тикет", callback_data=f"close_{ticket_id}"),
                    InlineKeyboardButton("Чат с пользователем", url=f"https://anonloader.io/supports/tickets/chat/{ticket_id}/")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await sync_to_async(ticket.save)()
            await query.edit_message_text(f"Вы взяли тикет #{ticket_id} в работу.\n\nВопрос: {question}", reply_markup=reply_markup)
            logger.info(f"Оператор {operator.user.user_id} взял тикет #{ticket_id} в работу.")
        else:
            await query.edit_message_text("Этот тикет уже взят в работу или недоступен.")
    except (ValueError, Ticket.DoesNotExist) as e:
        logger.error(f"Ошибка при взятии тикета #{ticket_id}: {e}")
        await query.edit_message_text("Ошибка при обработке тикета. Попробуйте еще раз.")


async def close_ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос оператора на закрытие тикета."""
    query = update.callback_query
    await query.answer()

    try:
        ticket_id = int(query.data.split("_")[1])
        ticket = await sync_to_async(Ticket.objects.get)(ticket_id=ticket_id)

        if ticket.status != 'closed':
            ticket.status = 'closed'
            await query.edit_message_text(f"Тикет #{ticket_id} был закрыт.")
            await sync_to_async(ticket.save)()
            logger.info(f"Оператор {update.effective_user.username} закрыл тикет #{ticket_id}.")
        else:
            await query.edit_message_text(f"Тикет #{ticket_id} уже закрыт.")
    except (ValueError, Ticket.DoesNotExist) as e:
        logger.error(f"Ошибка при закрытии тикета #{ticket_id}: {e}")
        await query.edit_message_text("Ошибка при закрытии тикета. Попробуйте еще раз.")

# Инициализация бота и команд
def main():
    application = Application.builder().token(settings.ANON_SUPPORT_TOKEN).build()
    logger.info(f"Бот был успешно запущен.")
    logger.info(f"Регистрация обработчиков...")
    application.add_handler(CommandHandler("start", start))
    logger.info(f"Обработчик команды /start запущен.")
    application.add_handler(MessageHandler(filters.ALL, handle_user_message))
    logger.info(f"Обработчик сообщений запущен.")
    application.add_handler(CallbackQueryHandler(end_dialog_handler, pattern=r"end_dialog_\d+"))
    application.add_handler(CallbackQueryHandler(take_ticket_handler, pattern=r"take_\d+"))
    application.add_handler(CallbackQueryHandler(close_ticket_handler, pattern=r"close_\d+"))
    logger.info(f"Обработчики Inline кнопок запущены.")
    application.run_polling()

if __name__ == "__main__":
    logger.info(f'Запуск бота..')
    main()
