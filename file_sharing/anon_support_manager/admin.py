from django.contrib import admin
from .models import User, Ticket, Operator, Message


class MessageInline(admin.TabularInline):  # Используем TabularInline для отображения сообщений
    model = Message
    extra = 0  # Количество пустых полей для добавления новых сообщений
    readonly_fields = ('sender', 'content', 'timestamp')  # Поля, которые будут только для чтения

    def sender(self, obj):
        return obj.user.username if obj.user else 'Неизвестный'
    sender.short_description = 'Отправитель'  # Заголовок для колонки


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'username')  # Отображение ID и имени пользователя
    search_fields = ('username', 'user_id')  # Поля для поиска


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'user', 'get_assigned_user_username', 'status', 'created_at', 'updated_at')  # Добавлены даты
    search_fields = ('ticket_id', 'user__username', 'assigned_user__username')  # Поиск по тикетам и пользователям
    list_filter = ('status', 'created_at', 'updated_at')  # Фильтры по статусу и датам
    raw_id_fields = ('user',)  # Поле пользователя отображается как поле с выбором ID
    inlines = [MessageInline]  # Включаем отображение сообщений внутри тикетов

    def get_assigned_user_username(self, obj):
        return obj.assigned_user.username if obj.assigned_user else 'Нет оператора'
    get_assigned_user_username.short_description = 'Оператор'  # Заголовок для колонки


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active')  # Отображение информации о операторе


