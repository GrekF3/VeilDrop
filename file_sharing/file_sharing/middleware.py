import logging

logger = logging.getLogger(__name__)

class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Получение IP-адреса клиента
        ip_address = request.META.get('REMOTE_ADDR')

        # Логирование запроса и IP-адреса
        logger.info(f"Request URL: {request.path}, IP Address: {ip_address}")

        # Обработка запроса
        response = self.get_response(request)

        return response
