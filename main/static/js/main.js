/**
 * main.js — основные скрипты сайта
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Путь наблюдателя загружен!');
    
    // Авто-закрытие уведомлений через 5 секунд
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 500);
        }, 5000);
    });
});

// Функция для подсветки узлов на карте
function highlightNodes(nodeIds) {
    if (!nodeIds || nodeIds.length === 0) return;
    nodeIds.forEach(function(id) {
        const node = document.querySelector(`[data-node-id="${id}"]`);
        if (node) {
            node.classList.add('is-highlighted');
            node.style.backgroundColor = '#fff3cd';
            node.style.border = '2px solid #ffc107';
        }
    });
}
