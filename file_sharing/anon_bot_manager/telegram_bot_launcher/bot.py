import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ApplicationBuilder
import django
from django.conf import settings
from anon_bot_manager.telegram_bot_launcher.handlers.main_menu import start, handle_user_input, cancel
from anon_bot_manager.telegram_bot_launcher.handlers.link_generation import (
    link_lifetime_selected,
    handle_media,
)
from anon_bot_manager.telegram_bot_launcher.handlers.support import support_bot
from anon_bot_manager.telegram_bot_launcher.handlers.privacy_policy import accept_policy
import os


# Установка Django настроек
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'file_sharing.settings')
django.setup()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

logging.getLogger('httpx').setLevel(logging.WARNING)  # Для новых версий
logging.getLogger('telegram').setLevel(logging.WARNING)  # Для старых версий

def register_handlers(application: Application) -> None:
    """Регистрирует все обработчики для бота"""
    logger.info("Регистрация обработчиков...")

    # Команда /start вызывает start, которое показывает главное меню
    application.add_handler(CommandHandler("start", start))
    logger.info("Обработчик /start зарегистрирован")

    # Команда для поддержки
    application.add_handler(CommandHandler("subscription", support_bot))
    logger.info("Обработчик /subscription зарегистрирован")

    # Основной обработчик текста, проверяет ввод и вызывает соответствующие функции
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    logger.info("Обработчик текстовых сообщений зарегистрирован")

    # Универсальный обработчик для всех типов файлов (фото, видео, аудио, документы)
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, handle_media))
    logger.info("Универсальный обработчик для медиа файлов зарегистрирован")

    # Обработчик для выбора времени жизни ссылки
    application.add_handler(CallbackQueryHandler(link_lifetime_selected, pattern='one_time|1_day|3_days|7_days'))
    logger.info("Обработчик выбора времени жизни ссылки зарегистрирован")

    # Обработчик для отмены
    application.add_handler(CallbackQueryHandler(cancel, pattern='cancel'))
    logger.info("Обработчик отмены зарегистрирован")

    # Обработчик политики конфиденциальности:
    application.add_handler(CallbackQueryHandler(accept_policy, pattern='accept_policy'))
    logger.info("Обработчик политики конфиденциальности зарегистрирован")

def main() -> None:
    """Запуск бота"""
    logger.info("Инициализация бота...")

    try:
        # Создаем приложение без использования token()
        application = ApplicationBuilder().token(settings.ANON_TOKEN).base_url("http://telegram-bot-api:8081/bot").base_file_url("http://telegram-bot-api:8081/file/bot").local_mode(True).build()
        register_handlers(application)
        logger.info('Бот успешно запущен!')
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.exception("Критическая ошибка при запуске бота: %s", e)



