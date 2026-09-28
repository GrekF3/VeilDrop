# file_sharing/management/commands/start_bot.py

import asyncio
from django.core.management.base import BaseCommand
from anon_support_manager.telegram_bot_launcher_support.bot import main  # Импортируем вашу функцию main

class Command(BaseCommand):
    help = 'Запуск бота'

    def handle(self, *args, **kwargs):
        asyncio.run(main())  # Запускаем асинхронную функцию main с использованием asyncio.run
