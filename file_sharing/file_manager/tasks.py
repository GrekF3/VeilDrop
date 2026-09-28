from celery import shared_task
import logging
from .models import File
from django.utils import timezone
from datetime import timedelta
import os

logger = logging.getLogger(__name__)

@shared_task
def delete_expired_file():
    logger.info("Запустил задание")
    files = File.objects.all()
    
    for file in files:
        try:
            # Условие для удаления истекшего файла
            if file.is_expired():
                file.delete()
                logger.info(f"File {file.unique_key} has been deleted (expired).")
            
            # Условие для удаления одноразового файла, если он был открыт, но не скачан
            elif file.is_opened and not file.is_downloaded:
                if file.expires_at:
                    # Если срок действия указан и истек - удаляем
                    if file.is_expired():
                        file.delete()
                        logger.info(f"File {file.unique_key} has been deleted (opened but expired).")
                    else:
                        logger.info(f"File {file.unique_key} has been opened but is still valid (not expired).")
                else:
                    # Если срок действия не указан, удаляем файл
                    file.delete()
                    logger.info(f"File {file.unique_key} has been deleted (opened without expiration date).")
            
            # Условие для удаления файлов, которые не были открыты и не скачаны через неделю после создания
            elif not file.is_opened and not file.is_downloaded:
                if timezone.now() - file.created_at > timedelta(weeks=1):
                    file.delete()
                    logger.info(f"File {file.unique_key} has been deleted (not opened or downloaded after one week).")
                else:
                    logger.info(f"File {file.unique_key} is still valid (not opened or downloaded).")
                    
            else:
                logger.info(f"File {file.unique_key} is not expired or still valid.")
        
        except File.DoesNotExist:
            logger.warning(f"File {file.unique_key} does not exist.")
            


@shared_task
def delete_qr_code_file(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Файл {file_path} успешно удалён.")
        else:
            logger.warning(f"Файл {file_path} не найден для удаления.")
    except Exception as e:
        logger.error(f"Ошибка при удалении файла {file_path}: {e}")



@shared_task
def celery_status():
    """Выводит в консоль, что Celery запущен и работает."""
    return logger.info("Celery запущен и работает.")
