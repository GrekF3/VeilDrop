# -------Django
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf.urls import handler404
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.core.files.base import ContentFile
from django.conf import settings
# -------MODELS
from .models import File, AdsBanner
from .forms import UniqueKeyForm, UploadFileForm
from .tasks import delete_qr_code_file
# -------LOGICAL BASE
import os
import random
import mimetypes
import uuid, base64
from cryptography.fernet import Fernet
import logging
from PIL import Image
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask
from datetime import timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Вспомогательная функция для удаления файла
def delete_file(file_record):
    file_path = file_record.file.path
    file_record.delete()
    if os.path.exists(file_path):
        os.remove(file_path)


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

def custom_404(request, exception):
    return render(request, '404.html', status=404)

handler404 = custom_404

@csrf_exempt
def upload_file(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        unique_key = request.POST.get('key')
        file_type = request.POST.get('type')
        text = request.POST.get('text', '')
        mime_type = request.POST.get('mime_type')
        expiry_duration = request.POST.get('expiry_duration')  # Получаем срок жизни файла из запроса

        if uploaded_file and unique_key and file_type:
            try:
                # Чтение содержимого файла
                file_data = uploaded_file.read()
                # Генерация ключа шифрования
                encryption_key = Fernet.generate_key().decode()

                # Шифрование файла
                fernet = Fernet(encryption_key.encode())
                encrypted_file_data = fernet.encrypt(file_data)

                # Создание файла в памяти с зашифрованными данными
                encrypted_file_content = ContentFile(encrypted_file_data, name=uploaded_file.name)

                # Определение MIME-типа
                if not mime_type:
                    mime_type = 'application/octet-stream'

                # Создание записи в базе данных
                file_record = File.objects.create(
                    unique_key=unique_key,
                    file=encrypted_file_content,
                    encryption_key=encryption_key,  # Сохраняем ключ шифрования
                    type=file_type,
                    text=text,
                    mime_type=mime_type  # Сохраняем MIME-тип
                )

                # Установка срока жизни файла, если он указан
                if expiry_duration != 'one_time':
                    try:
                        expiry_duration, _ = str(expiry_duration).split('_')
                        expiry_duration = int(expiry_duration)
                        file_record.set_expiry(expiry_duration)
                    except ValueError:
                        logger.warning("Ошибка: Неверный формат срока жизни файла")

                # Создание полного URL для файла
                file_url = request.build_absolute_uri(reverse('file_view', args=[unique_key]))

                # Логирование успешной загрузки файла
                logger.info(f"Файл успешно загружен. URL: {file_url}, уникальный ключ: {unique_key}, тип файла: {file_type}, MIME-тип: {mime_type}")

                # Формирование ответа
                response_data = {
                    'file_url': file_url,
                    'unique_key': unique_key,
                }
                return JsonResponse(response_data, status=200)

            except Exception as e:
                logger.error(f"Ошибка при обработке файла: {str(e)}")
                return JsonResponse({'error': str(e)}, status=500)

        logger.error("Ошибка: отсутствуют обязательные поля")
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    logger.error("Ошибка: недопустимый метод")
    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
def handle_file_upload(request):
    if request.method == 'POST':
        request.session.pop('upload_status', None)
        request.session.pop('upload_success', None)
        request.session.save()  # Сохранение изменений в сессии
        
        request.session['upload_status'] = {
            'status': 'in_progress',
            'message': 'Загрузка файла...'
        }
        request.session.save()  # Сохранение сессии на этом этапе
        print(request.session['upload_status'])
        uploaded_file = request.FILES.get('file')
        unique_key = str(uuid.uuid4())  # Генерация уникального ключа
        text = request.POST.get('text', '')
        mime_type = request.POST.get('mime_type', 'application/octet-stream')
        expiry_duration = request.POST.get('file_lifetime') 
        
        # Сохраняем статус в сессии для каждого пользователя

        if uploaded_file:
            try:
                request.session['upload_status']['message'] = 'Шифрование файла...'
                request.session.save()  # Сохранение статуса в сессии
                print(request.session['upload_status'])
                # Чтение содержимого файла
                file_data = uploaded_file.read()

                # Определение типа файла (изображение, видео или обычный файл)
                mime_type, _ = mimetypes.guess_type(uploaded_file.name)
                file_type = (
                    'image' if mime_type and mime_type.startswith('image') else
                    'video' if mime_type and mime_type.startswith('video') else
                    'audio' if mime_type and mime_type.startswith('audio') else
                    'file'
                )

                # Генерация ключа шифрования и шифрование файла
                encryption_key = Fernet.generate_key().decode()
                fernet = Fernet(encryption_key.encode())
                encrypted_file_data = fernet.encrypt(file_data)
                # Создание файла в памяти с зашифрованными данными
                encrypted_file_content = ContentFile(encrypted_file_data, name=uploaded_file.name)

                
                # Создание записи в базе данных
                file_record = File.objects.create(
                    unique_key=unique_key,
                    file=encrypted_file_content,
                    encryption_key=encryption_key,
                    type=file_type,
                    text=text,
                    mime_type=mime_type
                )

                # Установка срока жизни файла
                if expiry_duration == 'one_time':
                    expiration_str = 'Одноразовая ссылка'
                else:
                    try:
                        expiry_duration, _ = str(expiry_duration).split('_')
                        expiry_duration = int(expiry_duration)
                        file_record.set_expiry(expiry_duration)

                        expiration_str = (
                            "1 день" if expiry_duration == 1 else
                            f"{expiry_duration} дня" if 2 <= expiry_duration <= 4 else
                            f"{expiry_duration} дней"
                        )
                    except ValueError:
                        expiration_str = 'не задан'


                request.session['upload_status']['message'] = 'Генерация QR-кода...'
                request.session.save()  # Сохранение статуса в сессии
                print(request.session['upload_status'])
                # Генерация QR-кода и его сохранение
                qr_code_dir = f"{settings.MEDIA_ROOT}/qr_codes/"
                if not os.path.exists(qr_code_dir):
                    os.makedirs(qr_code_dir)

                download_link = request.build_absolute_uri(reverse('file_view', args=[unique_key]))
                qr_code_img = generate_custom_qr_code(download_link)
                avatar_img = Image.open(f'/home/app/web/media/logo/base.png')
                qr_size = avatar_img.width // 3
                qr_code_img = qr_code_img.resize((qr_size, qr_size))
                avatar_img.paste(qr_code_img, (avatar_img.width - qr_size, avatar_img.height - qr_size))

                qr_code_image_path = f"{qr_code_dir}avatar_with_custom_qr_{unique_key}.jpg"
                avatar_img.save(qr_code_image_path)

                # Сохранение информации в сессии
                request.session['upload_success'] = {
                    'unique_key': unique_key,
                    'link': download_link,
                    'file_expiration': expiration_str,
                    'qr_code_image_path': qr_code_image_path,
                }

                delete_qr_code_file.apply_async((qr_code_image_path,), eta=now() + timedelta(minutes=5))
                
                request.session['upload_status']['status'] = 'completed'
                request.session['upload_status']['message'] = 'Успешно. Переадресация...'
                request.session.save()  # Сохранение финального статуса
                print(request.session['upload_status'])
                # Перенаправление на страницу успешной загрузки
                return JsonResponse({'success': True, 'unique_key': unique_key})

            except Exception as e:
                logger.error(f"Ошибка при обработке файла: {str(e)}")
                request.session['upload_status'] = {
                    'status': 'error',
                    'message': 'Ошибка при обработке файла.'
                }
                request.session.save()  # Сохранение статуса ошибки
                return JsonResponse({'error'}, status=500)
        
        logger.error("Ошибка: отсутствуют обязательные поля")
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    logger.error("Ошибка: недопустимый метод")
    return JsonResponse({'error': 'Invalid method'}, status=405)


def check_upload_status(request):
    # Проверяем, есть ли статус загрузки в сессии
    upload_status = request.session.get('upload_status', {'status': 'not_started', 'message': ''})
    return JsonResponse(upload_status)

def check_load_status(request):
    # Проверяем, есть ли статус скачивания в сессии
    download_status = request.session.get('download_status', {'status': 'not_started', 'message': ''})
    return JsonResponse(download_status)

def home(request, error_message=None):
    request.session.flush()  # Полный сброс сессии
    error_file_message = None
    upload_form = UploadFileForm()
    search_form = UniqueKeyForm()
    ads_banners = AdsBanner.objects.filter(is_active=True)

    if request.method == 'POST':
        if 'unique_key' in request.POST:  # Обработка поиска файла по ключу
            search_form = UniqueKeyForm(request.POST)
            if search_form.is_valid():
                unique_key = search_form.cleaned_data['unique_key']
                try:
                    return redirect('file_view', key=unique_key)
                except File.DoesNotExist:
                    error_message = "Файл с таким ключом не найден."
                    logger.error(error_message)
            else:
                error_message = "Некорректный ключ."
                logger.warning(error_message)
        elif 'file' in request.FILES:  # Обработка загрузки файла
            try:
                # Перенаправление на новую функцию для загрузки файла
                return handle_file_upload(request)
            except Exception as e:
                error_message = "Ошибка при загрузке файла."
                logger.error(f"{error_message} Подробности: {str(e)}")

    context = {
        'form': search_form,
        'file_form': upload_form,
        'error_message': error_message,
        'error_file_message': error_file_message,
        'ads_banners': ads_banners,
    }

    return render(request, 'home.html', context)

# Представление для отображения и скачивания файла
def file_view(request, key):
    request.session['download_status'] = {
        'status': 'in_progress',
        'message': 'Загрузка файла...'
    }
    request.session.save() 
    

    error_message = None  # Инициализируем переменную для ошибки

    logger.info("Начало обработки запроса для ключа: %s", key)

    try:
        file_record = File.objects.get(unique_key=key)
        logger.info("Файл с ключом %s найден в базе данных", key)
    except File.DoesNotExist:
        # Сообщение об ошибке, если файла нет
        error_message = "Такого ключа не существует."
        logger.error(error_message)
        return home(request, error_message)
    
    # Проверка, доступен ли файл для скачивания
    if file_record.is_opened:
        logger.info("Файл уже открыт")
        # Если файл может быть загружен, но срок его действия истек
        if file_record.can_be_downloaded and (file_record.is_expired() or file_record.expires_at is None):
            logger.warning("Файл может быть загружен, но срок действия истек или нет даты истечения")
            # Удаляем файл, так как он уже был открыт или срок действия истек
            file_path = file_record.file.path
            file_record.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Файл %s был удален из файловой системы.", file_path)
            return HttpResponse("Файл недоступен для скачивания", status=403)
    # Если файл был открыт и срок действия истек (если он одноразовый)
    elif file_record.is_opened and file_record.is_expired():
        logger.warning("Файл был открыт и срок действия истек")
        # Удаляем файл
        file_path = file_record.file.path
        file_record.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Файл %s был удален из файловой системы.", file_path)
        return HttpResponse("Файл недоступен для скачивания", status=403)

    logger.info("Чтение файла")
    # Чтение файла
    try:
        with file_record.file.open('rb') as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        error_message = "Ошибка: файл не найден."
        logger.error(error_message)
        return home(request, error_message)
    except IOError:
        error_message = "Ошибка: не удалось прочитать файл."
        logger.error(error_message)
        return home(request, error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {e}"
        logger.error(error_message)
        return home(request, error_message)

    logger.info("Файл прочитан, начинаем расшифровку")
    decrypted_data = decrypt_file(encrypted_data, file_record.encryption_key)


    request.session['download_status']['message'] = "Расшифровка файла..."
    request.session.save() 


    if decrypted_data is None:
        logger.error("Ошибка расшифровки файла")
        return HttpResponse("Не удалось расшифровать файл.", status=400)

    mime_type = file_record.mime_type
    logger.info("MIME-тип файла: %s", mime_type)

    file_size = len(decrypted_data) / (1024 * 1024)  # Размер файла в МБ
    upload_date = file_record.created_at.strftime('%Y-%m-%d %H:%M:%S')
    logger.info("Размер файла: %.2f МБ, дата загрузки: %s", file_size, upload_date)
    
    context = {
        'file': file_record,
        'file_size': f"{file_size:.2f} МБ",
        'upload_date': upload_date,
        'mime_type': mime_type,
    }

    if file_record.type == 'image':
        logger.info("Файл является изображением")
        image_base64 = base64.b64encode(decrypted_data).decode('utf-8')
        context['image_data'] = image_base64
        render_response = render(request, 'file_detail.html', context)

    elif file_record.type == 'video':
        logger.info("Файл является видео")
        video_base64 = base64.b64encode(decrypted_data).decode('utf-8')
        context['video_data'] = video_base64
        render_response = render(request, 'file_detail.html', context)

    elif file_record.type == 'audio':
        logger.info("Файл является аудио")
        audio_base64 = base64.b64encode(decrypted_data).decode('utf-8')
        context['audio_data'] = audio_base64
        render_response = render(request, 'file_detail.html', context)

    elif file_record.type == 'file':
        logger.info("Файл является простым файлом")
        render_response = render(request, 'file_detail.html', context)

    else:
        logger.warning("Файл неизвестного типа, отправляем как байтовый поток")
        render_response = HttpResponse(decrypted_data, content_type='application/octet-stream')
        render_response['Content-Disposition'] = f'attachment; filename="{file_record.file.name}"'

    # Помечаем файл как открытый и запускаем проверку удаления
    if not file_record.is_opened:
        link_opened(file_record)

    request.session['download_status']['status'] = 'completed'
    request.session['download_status']['message'] = "Загрузка завершена."
    request.session.save()
    return render_response

def link_opened(file_record):
    """
    Помечает файл как открытый 
    """
    if not file_record.is_opened:
        file_record.mark_as_opened()  # Обновляем статус открытия

def upload_success_view(request):
    try:
        upload_success = request.session.get('upload_success')

        if not upload_success:
            return HttpResponseRedirect(reverse('home'))

        qr_code_image_path = upload_success.get('qr_code_image_path')

        qr_code_url = None
        if qr_code_image_path:
            qr_code_url = f"{request.build_absolute_uri('/media/qr_codes/')}{os.path.basename(qr_code_image_path)}"

        return render(request, 'upload_success.html', {
            'unique_key': upload_success['unique_key'],
            'link': upload_success['link'],
            'file_expiration': upload_success['file_expiration'],
            'qr_code_url': qr_code_url
        })

    except Exception as e:
        logger.error(f"Ошибка в представлении успешной загрузки: {e}")
        return JsonResponse({'error': 'Произошла ошибка'}, status=500)
    
def decrypt_file(encrypted_data, key):
    try:
        fernet = Fernet(key.encode())  # Создание объекта Fernet с ключом
        decrypted_data = fernet.decrypt(encrypted_data)  # Дешифрование данных
        return decrypted_data
    except Exception as e:
        logger.error("Ошибка при расшифровке файла: %s", e)  # Логирование ошибок
        return None

def download_file(request, key):
    # Получение записи файла по уникальному ключу
    file_record = get_object_or_404(File, unique_key=key)
    logger.info("Получена запись файла: %s", file_record)

    # Проверка, может ли файл быть скачан (одноразовая ссылка или срок жизни)
    if not file_record.can_be_downloaded():
        logger.warning("Файл недоступен для скачивания. Он был либо уже скачан, либо истек срок его жизни.")
        return HttpResponse("Файл недоступен для скачивания.", status=403)

    with file_record.file.open('rb') as f:
        encrypted_data = f.read()  # Чтение зашифрованных данных
        logger.info("Прочитаны зашифрованные данные, размер: %d байт", len(encrypted_data))

    # Расшифровка данных
    decrypted_data = decrypt_file(encrypted_data, file_record.encryption_key)
    if decrypted_data is None:
        logger.error("Ошибка: Не удалось расшифровать файл.")
        return HttpResponse("Не удалось расшифровать файл. Проверьте ключ шифрования.", status=400)
    
    logger.info("Данные расшифрованы.")

    # Определение MIME-типа
    mime_type = file_record.mime_type or mimetypes.guess_type(file_record.file.name)[0]
    if not mime_type:
        mime_type = 'application/octet-stream'
    logger.info("Определённый MIME-тип: %s", mime_type)

    # Получаем расширение файла и имя файла
    original_filename = file_record.file.name
    file_name, file_extension = os.path.splitext(original_filename)
    if not file_extension:
        file_extension = mimetypes.guess_extension(mime_type) or '.bin'
    logger.info("Определённое расширение файла: %s", file_extension)

    filename = f"{file_record.unique_key}{file_extension}"  # Задаем имя файла с расширением
    logger.info("Имя файла для скачивания: %s", filename)

    # Формирование ответа с расшифрованными данными
    response = HttpResponse(decrypted_data, content_type=mime_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    logger.info("Файл готов к отправке.")

    # Если файл одноразовый, помечаем его как скачанный и удаляем
    if not file_record.expires_at:  # Если срок жизни не установлен, файл одноразовый
        file_record.mark_as_downloaded()
        delete_file(file_record)
        logger.info("Файл %s был удалён после скачивания (одноразовый файл).", file_record.file.name)
    else:
        logger.info("Файл имеет срок жизни, он не будет удалён после скачивания.")

    return response

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin_bot/",
        "Disallow: /upload/",
        "Disallow: /file/",
        "Disallow: /download/",
        "Allow: /",
        "",
        "Sitemap: https://anonloader.io/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def restopre_php_page(request):
    random_phrases_ru = [
        "Ты что-то задумал, а я уже всё понял!",
        "Попытка — не пытка, но ты точно пытался!",
        "Ну вот, почти получилось... Но нет!",
        "Твоя попытка не прошла незамеченной. Но она провалилась!",
        "Хорошая попытка, но моя защита лучше!",
        "Ты попался! Ну почти.",
        "Упс, не в этот раз!",
        "Кто-то здесь явно что-то не то замышляет!",
    ]

    random_phrases_en = [
        "Oops! Looks like you tried, but no luck!",
        "Nice try, but not good enough!",
        "Your effort was noticed, but it didn't work!",
        "Almost had it... Almost!",
        "Better luck next time, champ!",
        "Caught you trying, didn't I?",
        "Did you really think this would work? Think again!",
        "Oops! Not today!",
        "You might be smart, but I'm smarter!",
        "Nice attempt, but the firewall says no!"
    ]
    random_phrase_ru = random.choice(random_phrases_ru)
    random_phrase_en = random.choice(random_phrases_en)
    
    # Выбираем рандомную фразу
    # Рендерим страницу с рандомной фразой
    return render(request, 'restore.html', {
        'random_phrase_ru': random_phrase_ru,
        'random_phrase_en': random_phrase_en
    })