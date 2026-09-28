# main_menu.py

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from anon_bot_manager.telegram_bot_launcher.handlers.privacy_policy import privacy_policy
from anon_bot_manager.telegram_bot_launcher.handlers.link_generation import generate_link
from anon_bot_manager.telegram_bot_launcher.handlers.profile import profile
from anon_bot_manager.telegram_bot_launcher.handlers.support import support_bot
from anon_bot_manager.models import BotUser
from asgiref.sync import sync_to_async

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print('Кто-то нажал старт))')
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    context.user_data.clear()

    try:
        # Получаем или создаем профиль пользователя
        user, created = await sync_to_async(BotUser.objects.get_or_create)(
            user_id=user_id,
            defaults={'username': username}
        )

        # Обновляем username, если он изменился
        if not created and user.username != username:
            user.username = username
            await sync_to_async(user.save)()  # Асинхронное сохранение

        # Проверяем согласие пользователя на политику конфиденциальности
        if not user.user_consent:
            await privacy_policy(update, context)
        else:
            await show_main_menu(update)

    except Exception as e:
        print(f"Ошибка при обработке пользователя: {e}")

async def show_main_menu(update: Update) -> None:
    user_id = update.message.from_user.id

    # Получаем профиль пользователя через Django ORM
    try:
        user = await sync_to_async(BotUser.objects.get)(user_id=user_id)
    except BotUser.DoesNotExist:
        await update.message.reply_text("Пользователь не найден.")
        return

    # Формируем основное меню
    keyboard = [
        [KeyboardButton("🔗 Сгенерировать ссылку 🔗")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("Поддержка 🆘")],
        [KeyboardButton("📕 Политика конфиденциальности 📕")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Выберите опцию:', reply_markup=reply_markup)

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    try:
        # Получаем профиль пользователя через Django ORM
        user_profile = await sync_to_async(BotUser.objects.get)(user_id=user_id)
    except BotUser.DoesNotExist:
        await update.message.reply_text("Профиль пользователя не найден.")
        return

    # Основное меню
    selected_option = update.message.text
    if selected_option == "🔗 Сгенерировать ссылку 🔗":
        await generate_link(update, context)
    elif selected_option == "👤 Профиль":
        await profile(update, context)
    elif selected_option in ["Поддержка 🆘"]:
        await support_bot(update, context)
    elif selected_option == "📕 Политика конфиденциальности 📕":
        await privacy_policy(update, context)
    elif selected_option == "⚙ Администраторское меню ⚙" and user_profile.is_admin:
        # Здесь может быть вызов функции для админ-меню, если требуется
        await update.message.reply_text("Вы вошли в администраторское меню.")
    elif selected_option == "Вернуться в меню":
        await show_main_menu(update)
    else:
        await update.message.reply_text("Неизвестная команда. Пожалуйста, выберите из меню.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Подтверждаем, что колбек был получен

    # Сброс состояния пользователя
    context.user_data['state'] = None  
    context.user_data['uploaded_content'] = None  # Убираем загруженное содержимое, если есть

    # Ответ пользователю
    await query.message.edit_text("Отменено.")
