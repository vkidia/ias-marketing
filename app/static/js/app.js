// Автоматически скрываем flash-сообщения через 5 секунд
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function (alert) {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        });
    }, 5000);
});

// Глобальные настройки Chart.js — применяются ко всем графикам
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = 'system-ui, -apple-system, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#6c757d';
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.scale.grid.color = 'rgba(0,0,0,0.05)';
    Chart.defaults.scale.border.dash = [3, 3];
}
