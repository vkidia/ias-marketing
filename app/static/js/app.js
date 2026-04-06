// AJAX-логика для смены статусов лидов появится в Спринте 3.

// Автоматически скрываем flash-сообщения через 5 секунд
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function (alert) {
            // bootstrap.Alert.getOrCreateInstance(alert).close() — стандартный способ
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        });
    }, 5000); // 5000 миллисекунд = 5 секунд
});