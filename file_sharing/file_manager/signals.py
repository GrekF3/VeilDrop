# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import File
from .tasks import delete_expired_file

@receiver(post_save, sender=File)
def schedule_file_deletion(sender, instance, created, **kwargs):
    if created and instance.expires_at:
        # Убедитесь, что expires_at в UTC
        expires_at_utc = timezone.make_aware(instance.expires_at, timezone.utc)
        
        # Запланировать задачу на удаление
        if expires_at_utc > timezone.now():
            delete_expired_file.apply_async((instance.id,), eta=expires_at_utc)