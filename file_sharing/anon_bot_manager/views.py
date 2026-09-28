from django.shortcuts import render, redirect
from .models import BotUser
import requests
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.files.storage import default_storage
import os
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
import logging
import re
logger = logging.getLogger(__name__)


def send_broadcast(message, image_path=None):
    logger.info("Начало рассылки")
    users = BotUser.objects.all()
    bot_token = os.getenv('ANON_TOKEN')
    for user in users:
        data = {
            'chat_id': user.user_id,
            'text': message,
            'parse_mode': 'Markdown'  # Использование Markdown для форматирования
        }
        if image_path:
            logger.info(f"Отправка фото пользователю {user.user_id}")
            try:
                with open(image_path, 'rb') as image_file:
                    files = {'photo': image_file}
                    data['caption'] = message  # Markdown будет применяться к `caption`
                    response = requests.post(f'https://api.telegram.org/bot{bot_token}/sendPhoto', data=data, files=files)
                    response.raise_for_status()
                    logger.info(f"Фото успешно отправлено пользователю {user.user_id}")
            except requests.exceptions.HTTPError as e:
                if response.status_code == 403:
                    logger.warning(f"Пользователь {user.user_id} заблокировал бота или удалил чат.")
                else:
                    logger.error(f"Ошибка при отправке фото пользователю {user.user_id}: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке фото пользователю {user.user_id}: {e}")
        else:
            logger.info(f"Отправка сообщения пользователю {user.user_id}")
            try:
                response = requests.post(f'https://api.telegram.org/bot{bot_token}/sendMessage', data=data)
                response.raise_for_status()
                logger.info(f"Сообщение успешно отправлено пользователю {user.user_id}")
            except requests.exceptions.HTTPError as e:
                if response.status_code == 403:
                    logger.warning(f"Пользователь {user.user_id} заблокировал бота или удалил чат.")
                else:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user.user_id}: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user.user_id}: {e}")
    logger.info("Рассылка завершена")

@login_required
def bot_admin_panel(request):
    return render(request, 'bot_admin_panel.html', {'section': 'manage_users', 'users': BotUser.objects.all()})

@login_required
def broadcast_view(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        image = request.FILES.get('image')

        image_path = None
        if image:
            image_name = default_storage.save(os.path.join('uploads', image.name), image)
            image_path = os.path.join(settings.MEDIA_ROOT, image_name)
        
        logger.info(f'Запуск рассылки с сообщением: "{message}" и изображением: {image_path}')
        send_broadcast(message, image_path)
        
        return render(request, 'bot_admin_panel.html', {'section': 'broadcast', 'status': 'Рассылка выполнена успешно!'})
    
    return render(request, 'bot_admin_panel.html', {'section': 'broadcast', 'status': None})

@login_required
def manage_users_view(request):
    users = BotUser.objects.all()

    # Возвращаем страницу управления пользователями с отображением всех пользователей
    return render(request, 'bot_admin_panel.html', {
        'section': 'manage_users',
        'users': users,
        'total_users': users.count(),  # Отображаем общее количество пользователей
    })
