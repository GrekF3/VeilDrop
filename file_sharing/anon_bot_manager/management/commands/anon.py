import asyncio
from django.core.management.base import BaseCommand
from anon_bot_manager.telegram_bot_launcher.bot import main  # Импортируем вашу функцию main

class Command(BaseCommand):
    help = 'Запуск основного бота'

    def handle(self, *args, **kwargs):
        asyncio.run(main())  # Запускаем асинхронную функцию main с использованием asyncio.run
