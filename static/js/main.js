/**
 * main.js — основные скрипты сайта
 */

// ============================================================
// 1. ЗАГРУЗКА ДОКУМЕНТА
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Путь наблюдателя загружен!');
    initTooltips();
    initAutoDismissAlerts();
});

// ============================================================
// 2. ИНИЦИАЛИЗАЦИЯ TOOLTIP
// ============================================================

function initTooltips() {
    // Инициализируем Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ============================================================
// 3. АВТО-ЗАКРЫТИЕ УВЕДОМЛЕНИЙ
// ============================================================

function initAutoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            // Плавно скрываем уведомление через 5 секунд
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 500);
        }, 5000);
    });
}

// ============================================================
// 4. ПОДСВЕТКА УЗЛОВ НА КАРТЕ
// ============================================================

function highlightNodes(nodeIds) {
    /**
     * Подсвечивает узлы на ментальной карте по их ID.
     * nodeIds — массив ID узлов.
     */
    if (!nodeIds || nodeIds.length === 0) return;

    nodeIds.forEach(function(id) {
        const node = document.querySelector(`[data-node-id="${id}"]`);
        if (node) {
            node.classList.add('is-highlighted');
            // Плавная подсветка
            node.style.transition = 'background-color 0.3s ease';
            node.style.backgroundColor = '#fff3cd';
            // Добавляем обводку
            node.style.border = '2px solid #ffc107';
        }
    });
}

// ============================================================
// 5. РАБОТА С ФИЛЬТРАМИ
// ============================================================

function applyFilter(filterType, value) {
    /**
     * Применяет фильтр к списку элементов.
     */
    const items = document.querySelectorAll('.filter-item');
    items.forEach(function(item) {
        const attr = item.dataset[filterType];
        if (attr === value || value === 'all' || !value) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// ============================================================
// 6. РАБОТА С ФОРМОЙ СОЗДАНИЯ КАРТЫ
// ============================================================

function initMapForm() {
    const form = document.querySelector('#map-create-form');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        const title = document.querySelector('#id_title');
        const central = document.querySelector('#id_central_node');

        if (!title.value.trim() || !central.value.trim()) {
            e.preventDefault();
            alert('Пожалуйста, заполните название и центральный узел.');
        }
    });
}

// ============================================================
// 7. ДИНАМИЧЕСКОЕ ПОКАЗАНИЕ ПОЛЯ "ДРУГОЕ" В ФОРМЕ
// ============================================================

function initOtherFieldToggle() {
    const select = document.querySelector('[data-toggle-other]');
    if (!select) return;

    const otherField = document.querySelector(select.dataset.target);
    if (!otherField) return;

    select.addEventListener('change', function() {
        if (this.value === 'other') {
            otherField.style.display = 'block';
            otherField.required = true;
        } else {
            otherField.style.display = 'none';
            otherField.required = false;
            otherField.value = '';
        }
    });
}

// ============================================================
// 8. ИНИЦИАЛИЗАЦИЯ ВСЕХ МОДУЛЕЙ
// ============================================================

// Инициализируем все модули
document.addEventListener('DOMContentLoaded', function() {
    initMapForm();
    initOtherFieldToggle();

    // Проверяем, есть ли параметр highlight в URL
    const urlParams = new URLSearchParams(window.location.search);
    const highlight = urlParams.get('highlight');
    if (highlight) {
        const ids = highlight.split(',').map(Number);
        highlightNodes(ids);
    }
});