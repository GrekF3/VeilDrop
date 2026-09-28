from channels.generic.websocket import AsyncWebsocketConsumer
import json

class SupportConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Получаем идентификатор тикета из URL
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.group_name = f'support_{self.ticket_id}'

        # Присоединяемся к группе на основе ticket_id
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Отключаемся от группы
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Получаем сообщение от клиента
    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']

        # Отправляем сообщение в группу
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Получаем сообщение от группы
    async def chat_message(self, event):
        message = event['message']
        # Отправляем сообщение клиенту
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': message
        }))
    
    async def image_message(self, event):
        image_data = event['image_data']
        # Отправляем изображение клиенту
        await self.send(text_data=json.dumps({
            'type': 'image',
            'image_data': image_data
        }))