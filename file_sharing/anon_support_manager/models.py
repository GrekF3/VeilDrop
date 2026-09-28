# anon_support_manager/models.py

from django.db import models
from django.utils import timezone

class User(models.Model):
    user_id = models.BigIntegerField(unique=True)  # Уникальный идентификатор пользователя
    username = models.CharField(max_length=255)

    def __str__(self):
        return self.username


class Operator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operator')  # Связь с пользователем
    is_active = models.BooleanField(default=False)  # Статус активности на смене

    def __str__(self):
        return f'Operator: {self.user.username} (Active: {self.is_active})'


class Ticket(models.Model):
    ticket_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    assigned_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    question = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=[('new', 'New'), ('in_progress', 'In Progress'), ('closed', 'Closed')], default='new')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def add_message(self, sender, text):
        """Метод для добавления сообщения в историю сообщений."""
        message = Message.objects.create(ticket=self, user=sender, content=text)  # Исправлены аргументы
        return message  # Возвращаем созданное сообщение

    def get_messages(self):
        """Метод для получения истории сообщений в удобном формате."""
        return self.messages.all()  # Возвращает все сообщения, связанные с тикетом

    def get_last_message(self):
        """Метод для получения последнего сообщения тикета."""
        return self.messages.last()  # Возвращает последнее сообщение тикета

    def __str__(self):
        return f'Ticket #{self.ticket_id} - User: {self.user.username if self.user else "Unknown"}'

class Message(models.Model):
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, related_name='messages')  # Связь с тикетом
    user = models.ForeignKey('User', on_delete=models.CASCADE)  # Связь с пользователем
    content = models.TextField()  # Содержимое сообщения
    timestamp = models.DateTimeField(default=timezone.now)  # Время отправки сообщения

    def __str__(self):
        return f"Message from {self.user.username} on Ticket #{self.ticket.ticket_id}"
