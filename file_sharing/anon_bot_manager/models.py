# anon_bot_manager/models.py
from django.db import models

class BotUser(models.Model):
    user_id = models.BigIntegerField(unique=True)  # Измените на BigIntegerField
    username = models.CharField(max_length=255)
    generated_links = models.IntegerField(default=0)
    join_date = models.DateTimeField(auto_now_add=True)
    user_consent = models.BooleanField(default=False)

    def __str__(self):
        return self.username
