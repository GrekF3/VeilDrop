document.addEventListener("DOMContentLoaded", function () {
    const overlay = document.getElementById('overlay');
    const statusText = document.getElementById('loadStatusText');

    function hideLoader() {
        overlay.style.display = 'none';
    }
    
    function handleFileLoad() {

        const interval = setInterval(() => {
            fetch('/check-file-load-status/') 
                .then(response => response.json())
                .then(statusData => {
                    statusText.innerText = statusData.message;
                    console.log(statusData.message)
                    if (statusData.status === 'completed') {
                        console.log("Загрузка завершена успешно.");
                        clearInterval(interval);
                        hideLoader();
                    } else if (statusData.status === 'error') {
                        console.error("Ошибка при загрузке файла.");
                        clearInterval(interval);
                        hideLoader();
                    }
                })
                .catch(error => {
                    console.error('Ошибка запроса статуса загрузки:', error);
                    clearInterval(interval);
                    hideLoader();
                });
        }, 1000);
    }

    handleFileLoad();
});
