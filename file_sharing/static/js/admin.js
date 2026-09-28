// admin.js
document.addEventListener('DOMContentLoaded', function() {
    // Функция для фильтрации пользователей
    document.getElementById('searchUserInput').addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const userList = document.getElementById('userList');
        const users = userList.getElementsByTagName('li');

        Array.from(users).forEach(function(user) {
            const username = user.querySelector('strong').textContent.toLowerCase(); // Получаем имя пользователя
            const userId = user.textContent.match(/\(ID: (\d+)\)/)[1]; // Извлекаем user_id

            // Проверяем, содержится ли искомый текст в username или user_id
            if (username.includes(searchTerm) || userId.includes(searchTerm)) {
                user.style.display = 'flex'; // Показываем элемент
            } else {
                user.style.setProperty('display', 'none', 'important'); // Скрываем элемент
            }
        });
    });
});
