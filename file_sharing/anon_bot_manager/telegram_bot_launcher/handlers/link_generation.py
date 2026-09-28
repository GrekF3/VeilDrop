import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from anon_bot_manager.telegram_bot_launcher.utils import generate_unique_key
import requests
from anon_bot_manager.models import BotUser
from django.conf import settings
import mimetypes
import os
from asgiref.sync import sync_to_async

from telegram import InputFile

from PIL import Image
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Определение состояний
SELECTING_FILE_TYPE = 'selecting_file_type'
WAITING_FOR_FILE = 'waiting_for_file'
WAITING_FOR_IMAGE_TEXT = 'waiting_for_image_text'

#LINK
URL = os.getenv('URL')
if settings.DEBUG == True:
    LOCAL_URL = 'https://anonloader.io'
else:
    LOCAL_URL = URL


def generate_custom_qr_code(link, size=300, logo_path=None):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Максимальная коррекция для лого
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)

    # Генерация QR-кода с круглыми модулями и градиентной заливкой
    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=RadialGradiantColorMask(back_color=(255, 255, 255), center_color=(0, 0, 0), edge_color=(100, 100, 255))
    )

    qr_img = qr_img.convert("RGB")
    qr_img = qr_img.resize((size, size))

    # Добавление логотипа в центр QR-кода, если есть
    if logo_path:
        logo = Image.open(logo_path)
        logo_size = size // 5  # Лого будет занимать 1/5 QR-кода
        logo = logo.resize((logo_size, logo_size))

        # Определение позиции для вставки логотипа в центр QR-кода
        pos = ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2)
        qr_img.paste(logo, pos, logo)

    return qr_img







async def generate_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Пользователь запрашивает генерацию ссылки")
    context.user_data['state'] = SELECTING_FILE_TYPE
    keyboard = [
        [InlineKeyboardButton("anonloader.io", url="https://anonloader.io")],
        [InlineKeyboardButton("Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Пожалуйста, отправьте ваш файл.\n\n"
        "*Обратите внимание, что максимальный размер файла для загрузки составляет 1 Гб.*\n\n"
        "Также вы можете воспользоваться веб-версией для загрузки файлов:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def update_generated_links(user_id):
    logger.info(f"Обновление количества сгенерированных ссылок для пользователя с ID {user_id}")
    user = await sync_to_async(BotUser.objects.get)(user_id=user_id)
    user.generated_links += 1
    await sync_to_async(user.save)()
    return

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    file = None
    file_type = None
    file_size = None
    file_mime_type = None
    progress_message = None

    # Определяем тип файла
    if message.video:
        file = await message.video.get_file()
        file_size = message.video.file_size
        file_mime_type = message.video.mime_type
        file_type = 'video'
    elif message.audio:
        file = await message.audio.get_file()
        file_size = message.audio.file_size
        file_mime_type = message.audio.mime_type
        file_type = 'audio'
    elif message.document:
        file = await message.document.get_file()
        file_size = message.document.file_size
        file_mime_type = message.document.mime_type
        file_type = 'file'
        # Проверяем, является ли документ изображением или аудио
        if file_mime_type and file_mime_type.startswith('image/'):
            file_type = 'image'
        elif file_mime_type and file_mime_type.startswith('audio/'):
            file_type = 'audio'
    elif message.photo:
        file = await message.photo[-1].get_file()  # Берем самое большое изображение
        file_size = message.photo[-1].file_size
        file_mime_type = 'image/jpeg'  # Telegram не всегда предоставляет MIME-тип для фотографий
        file_type = 'image'
    else:
        await update.message.reply_text("Этот тип файла не поддерживается.")
        return

    logger.info(f"Обрабатывается {file_type} размером {file_size} байт")
    max_file_size = 1_010_000_000  # 1,01 ГБ в байтах
    if file_size > max_file_size:
        await update.message.reply_text(f"Файл слишком большой. Максимальный размер файла: 1ГБ.")
        return

    try:
        # Отправляем начальное сообщение о загрузке
        progress_message = await update.message.reply_text(f"Начинаю обработку {file_type}...")

        # Обновляем сообщение о получении информации о файле
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=progress_message.message_id,
            text="Получаю информацию о файле..."
        )

        # Обрабатываем файл (можно загрузить больше 20 МБ)
        file_data = await file.download_as_bytearray()
        file_type_translation = {
            'image': 'изображения',
            'video': 'видео',
            'audio': 'аудио',
            'file': 'документа',
        }
        file_type_russian = file_type_translation.get(file_type, 'файла')  # По умолчанию 'файл'

        # Обновляем сообщение о процессе загрузки
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=progress_message.message_id,
            text=f"Обработка {file_type_russian} завершена."
        )

        # Сохраняем информацию о загруженном контенте
        context.user_data['uploaded_content'] = {
            'type': file_type,
            'content': file_data,
            'mime_type': file_mime_type,
        }

        # Запрашиваем время жизни ссылки
        await ask_for_link_lifetime(update)

    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {str(e)}")
        if progress_message:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=progress_message.message_id,
                text="Произошла ошибка при загрузке файла."
            )



async def ask_for_link_lifetime(update: Update) -> None:
    keyboard = [
        [InlineKeyboardButton("Одноразовая ссылка", callback_data='one_time')],
        [InlineKeyboardButton("Ссылка на 1 день", callback_data='1_day')],
        [InlineKeyboardButton("Ссылка на 3 дня", callback_data='3_days')],
        [InlineKeyboardButton("Ссылка на 7 дней", callback_data='7_days')],
        [InlineKeyboardButton("Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите срок жизни ссылки:", reply_markup=reply_markup)
    
async def link_lifetime_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    LIFETIME_DISPLAY = {
        'one_time': 'Одноразовая ссылка | Срок жизни ссылки: 7 дней',
        '1_day': '1 день',
        '3_days': '3 дня',
        '7_days': '7 дней'
    }
    query = update.callback_query
    await query.answer()

    lifetime = query.data
    lifetime_display = LIFETIME_DISPLAY.get(lifetime, 'Неизвестный срок жизни')
    uploaded_content = context.user_data.get('uploaded_content')

    if not uploaded_content:
        logger.error(f"Ошибка: контент не найден для пользователя {update.effective_user.id}")
        await query.message.reply_text("Ошибка: не найден загруженный контент.")
        return

    unique_key = generate_unique_key()
    logger.info(f"Генерация ссылки с уникальным ключом: {unique_key} для пользователя {update.effective_user.id}")

    # Получаем имя файла и MIME-тип
    original_filename = uploaded_content.get('filename', 'uploaded_file')
    mime_type = uploaded_content['mime_type']
    logger.info(f"Файл для загрузки: {original_filename}, MIME-тип: {mime_type}, срок жизни ссылки: {lifetime_display}")

    files = {
        'file': (original_filename, uploaded_content['content'])  # Используем оригинальное имя и MIME-тип
    }
    data = {
        'key': unique_key,
        'type': uploaded_content['type'],
        'text': context.user_data.get('text', ''),
        'expiry_duration': lifetime,
        'mime_type': mime_type,
    }
    
    loading_message = await query.message.edit_text("Загрузка файла на сервер...")
    
    try:
        logger.info(f"Отправка файла на сервер для пользователя {update.effective_user.id}...")
        response = requests.post("http://web:8000/upload/", data=data, files=files, allow_redirects=True)
        logger.info(f"Заголовки ответа: {response.headers}")

        if response.status_code == 200:
            response_data = response.json()
            file_url = response_data.get('file_url')
            unique_key = response_data.get('unique_key')

            logger.info(f"Ответ сервера: {response_data}")

            if file_url is None:
                logger.error("Ошибка: сервер не вернул ссылку на файл.")
                await loading_message.edit_text("Ошибка: сервер не вернул ссылку на файл.")
                return
            
            logger.info(f"Файл успешно загружен: {file_url} для пользователя {update.effective_user.id}")
            loading_message = await query.message.edit_text("Файл был загружен на сервер...")

            if lifetime != 'one_time':
                download_count = 'Неограничено'
            else:
                download_count = '1'

            user_id = update.effective_user.id
            avatar_path = '/home/app/web/anon_bot_manager/telegram_bot_launcher/handlers/images/base.png'  # Путь к аватарке
            download_link = f"{LOCAL_URL}/file/{unique_key}"  # Ссылка для скачивания

            logger.info("Начинаем генерировать QR-код...")
            loading_message = await query.message.edit_text("Генерация QR-кода...")
            qr_code_img = generate_custom_qr_code(download_link)
            
            logger.info("QR-код сгенерирован, обрабатываем изображение с аватаркой...")
            avatar_img = Image.open(avatar_path)
            qr_size = avatar_img.width // 3  # Размер QR-кода относительно аватарки
            qr_code_img = qr_code_img.resize((qr_size, qr_size))
            avatar_img.paste(qr_code_img, (avatar_img.width - qr_size, avatar_img.height - qr_size))
            avatar_img.save("avatar_with_custom_qr.jpg")
            
            loading_message = await query.message.edit_text("Проверяем, что все в порядке...")
            
            if download_count == 1:
                defender_message = '🛡️ <i>Ваша ссылка защищена и удалится после первого открытия.</i>'
            else:
                defender_message = "🛡️ <i>Ваша ссылка защищена.</i>"
            
            keyboard = [
                [InlineKeyboardButton("🔗 Скачать файл", url=f"{LOCAL_URL}/file/{unique_key}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            logger.info("Отправляем QR-код пользователю...")
            with open("avatar_with_custom_qr.jpg", "rb") as qr_image_file:
                await loading_message.delete()
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=InputFile(qr_image_file),
                    caption=(
                        f"✅ <b>Ваш файл был успешно загружен на сервер!</b>\n\n"
                        f"🔗 <b>Защищенная ссылка</b> для загрузки файла: <a href='{LOCAL_URL}/file/{unique_key}'>Загрузить файл</a>\n"
                        f"🔑 <b>Ключ доступа:</b> <code>{unique_key}</code>\n"
                        f"⏳ <b>Срок жизни файла:</b> {lifetime_display}\n"
                        f"🔒 <b>Количество доступных открытий:</b> {download_count}\n\n"
                        f"{defender_message}"
                    ),
                    parse_mode='html',
                    reply_markup=reply_markup
                )
            
            os.remove("avatar_with_custom_qr.jpg")
            await update_generated_links(user_id=user_id)
            context.user_data['state'] = None
        else:
            logger.error(f"Ошибка при загрузке файла, код ответа: {response.status_code}")
            await loading_message.edit_text("Произошла ошибка при загрузке файла.")
    except requests.RequestException as e:
        logger.exception(f"Ошибка подключения к серверу: {e}")
        await loading_message.edit_text("Ошибка при подключении к серверу. Пожалуйста, попробуйте снова.")