document.addEventListener("DOMContentLoaded", function () {
    const selectLifetime = document.getElementById("file_lifetime");
    const oneTimeNotice = document.getElementById("oneTimeNotice");
    const submitButton = document.querySelector('#uploadForm button[type="submit"]');
    const fileInput = document.querySelector('#uploadForm input[type="file"]');
    const overlay = document.getElementById('overlay');
    const statusText = document.getElementById('uploadStatusText');

    // Функция для отображения уведомления при выборе одноразовой ссылки
    function toggleOneTimeNotice() {
        if (selectLifetime.value === "one_time") {
            oneTimeNotice.style.display = "block";
        } else {
            oneTimeNotice.style.display = "none";
        }
    }

    // Функция для активации/деактивации кнопки отправки
    function toggleSubmitButtonState() {
        if (fileInput.files.length > 0 && selectLifetime.value !== "") {
            submitButton.disabled = false;
        } else {
            submitButton.disabled = true;
        }
    }

    // Инициализация событий при загрузке
    selectLifetime.addEventListener("change", function () {
        toggleOneTimeNotice();
        toggleSubmitButtonState();
    });

    fileInput.addEventListener("change", toggleSubmitButtonState);

    // Проверка и инициализация видимости уведомления и состояния кнопки
    toggleOneTimeNotice();
    toggleSubmitButtonState();

    // Добавляем функционал затемнения фона и показа процесса отправки
    document.getElementById('uploadForm').addEventListener('submit', function(event) {
        event.preventDefault();
    
        // Показать overlay при начале загрузки
        overlay.style.display = 'flex';
        statusText.style.opacity = 1;
    
        const formData = new FormData(this);
        const xhr = new XMLHttpRequest();
    
        xhr.open('POST', this.action, true);
        xhr.timeout = 10000;  // Тайм-аут 10 секунд
    
        xhr.ontimeout = function() {
            console.error('Превышено время ожидания запроса');
            overlay.style.display = 'none';  // Скрыть overlay при тайм-ауте
            statusText.textContent = 'Не удалось загрузить файл. Попробуйте снова.';
            
            // Перезагрузка через 1 секунду
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        };
    
        xhr.onerror = function() {
            console.error('Ошибка запроса на сервер');
            overlay.style.display = 'none';  // Скрыть overlay при ошибке запроса
            statusText.textContent = 'Не удалось загрузить файл. Попробуйте снова.';
    
            // Перезагрузка через 1 секунду
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        };
    
        xhr.onload = function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                console.log('Файл успешно загружен');
            } else {
                console.error('Ошибка при загрузке файла: ' + xhr.status);
                overlay.style.display = 'none';  // Скрыть overlay при ошибке на сервере
                statusText.textContent = 'Не удалось загрузить файл. Попробуйте снова.';
    
                // Перезагрузка через 1 секунду
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            }
        };
    
        const interval = setInterval(() => {
            fetch('/check-upload-status/')
                .then(response => response.json())
                .then(statusData => {
                    console.log("Статус с сервера:", statusData.message); 
                    statusText.textContent = statusData.message; 
    
                    if (statusData.status === 'completed' || statusData.status === 'error') {
                        clearInterval(interval);
    
                        // Если статус "completed", подождать 1 секунду и переадресовать
                        if (statusData.status === 'completed') {
                            setTimeout(() => {
                                overlay.style.display = 'none';  // Скрыть overlay перед переадресацией
                                window.location.href = '/upload/success/';
                            }, 1000);
                        }
    
                        // Если ошибка, сразу скрыть overlay и перезагрузить страницу
                        if (statusData.status === 'error') {
                            overlay.style.display = 'none'; // Скрыть overlay при ошибке
    
                            // Перезагрузка через 1 секунду
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        }
                    }
                })
                .catch(error => {
                    console.error("Ошибка при получении статуса:", error); 
                    clearInterval(interval);
                    overlay.style.display = 'none'; // Скрыть overlay при ошибке в запросе статуса
    
                    // Перезагрузка через 1 секунду
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                });
        }, 3000);
    
        xhr.send(formData);
    });
});
