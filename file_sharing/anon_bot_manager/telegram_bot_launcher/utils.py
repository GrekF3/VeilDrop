# utils.py
import uuid

def generate_unique_key():
    unique_key = str(uuid.uuid4())  # Генерация уникального ключа
    return unique_key
