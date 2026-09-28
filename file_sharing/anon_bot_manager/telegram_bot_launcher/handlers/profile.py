from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from anon_bot_manager.models import BotUser
from asgiref.sync import sync_to_async

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    try:
        # Получаем профиль пользователя из базы данных
        user_profile = await sync_to_async(BotUser.objects.get)(user_id=user_id)

        # Формируем текст ответа с использованием Markdown для форматирования
        response_text = (
            "*Профиль пользователя:*\n\n"
            f"👤 *Никнейм:* @{user_profile.username}\n\n"

            f"📊 *Сгенерировано ссылок:* {user_profile.generated_links}\n"
        )

        # Создаем кнопки для управления подпиской и возвращения в меню
        keyboard = [
            [KeyboardButton("Вернуться в меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
    except BotUser.DoesNotExist:
        # Обработка случая, когда профиль пользователя не найден
        await update.message.reply_text("Профиль не найден.")
    except Exception as e:
        # Обработка других ошибок
        print(e)
        await update.message.reply_text("Произошла ошибка при получении профиля. Пожалуйста, попробуйте снова позже.")
