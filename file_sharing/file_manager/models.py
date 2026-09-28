from django.db import models
from datetime import timedelta
from django.utils import timezone
import os

class File(models.Model):
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('file', 'File'),
        ('video', "Video"),
        ('audio', "Audio"),
    ]
    unique_key = models.CharField(max_length=255, unique=True)
    file = models.FileField(upload_to='files/')
    created_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    encryption_key = models.CharField(max_length=44)  # Ключ шифрования
    text = models.TextField(blank=True, null=True)
    is_downloaded = models.BooleanField(default=False)  # Отмечает, был ли файл скачан (для одноразовой ссылки)
    is_opened = models.BooleanField(default=False)
    mime_type = models.CharField(max_length=50, blank=True, null=True)  # Поле для хранения MIME-типа
    expires_at = models.DateTimeField(blank=True, null=True)  # Поле для хранения срока жизни файла

    def __str__(self):
        return f"{self.file.name} ({self.get_type_display()})"

    def set_expiry(self, duration):
        """Устанавливает срок жизни файла в днях."""
        self.expires_at = timezone.now() + timedelta(days=duration)
        self.save()

    def is_expired(self):
        """Проверяет, истек ли срок жизни файла."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        # Если срок не указан, но файл одноразовый (и уже был открыт), считаем его истекшим
        return False

    def can_be_downloaded(self):
        """Проверяет, доступен ли файл для скачивания."""
        # Файл может быть скачан, если он не был ранее скачан (если он одноразовый) и срок жизни не истек
        if (self.is_downloaded and not self.expires_at) or self.is_expired():
            return False
        return True

    def mark_as_downloaded(self):
        """Помечает файл как скачанный (для одноразовой ссылки)."""
        if not self.expires_at:
            self.is_downloaded = True
            self.save()

    def mark_as_opened(self):
        self.is_opened = True
        self.save()

    def delete(self, *args, **kwargs):
        """Удаляет файл из файловой системы при удалении записи из базы данных."""
        if self.file and os.path.isfile(self.file.path):
            print(f"Удаление файла: {self.file.path}")  # Отладочное сообщение
            self.file.delete(save=False)  # Удаляет файл
        else:
            print("Файл не существует, ничего не удаляем.")
        super().delete(*args, **kwargs)  # Вызывает стандартное удаление

class AdsBanner(models.Model):
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    image = models.ImageField(upload_to='bnr_recomends/', verbose_name="Изображение (GIF поддерживается)")
    link = models.URLField(verbose_name="Ссылка")
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"