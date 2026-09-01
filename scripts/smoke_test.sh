#!/bin/bash
# Быстрая проверка после деплоя: сайт реально отвечает, а не просто
# systemd не ругнулся на рестарт. Проверяет ключевые страницы через curl
# и сверяет ожидаемый HTTP-код. НЕ проверяет содержимое страниц — только
# что они вообще открываются с правильным статусом.
#
# Запуск на сервере после деплоя:
#   bash scripts/smoke_test.sh
#
# По умолчанию бьёт в https://putnabludatel.ru — можно переопределить:
#   BASE_URL=http://127.0.0.1:8000 bash scripts/smoke_test.sh

set -uo pipefail

BASE_URL="${BASE_URL:-https://putnabludatel.ru}"
FAILED=0

check() {
    local path="$1"
    local expected="$2"
    local label="$3"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 -L --max-redirs 0 "${BASE_URL}${path}")
    if [ "$code" = "$expected" ]; then
        echo "OK   [$code] $label ($path)"
    else
        echo "FAIL [$code, ожидали $expected] $label ($path)"
        FAILED=1
    fi
}

echo "Проверяю ${BASE_URL}..."
echo

check "/" "200" "Главная страница"
check "/privacy/" "200" "Политика конфиденциальности"
check "/terms/" "200" "Пользовательское соглашение"
check "/robots.txt" "200" "robots.txt"
check "/sitemap.xml" "200" "sitemap.xml"
check "/accounts/login/" "200" "Страница входа"
check "/vk/login/" "302" "Начало входа через VK (редирект на id.vk.com)"
check "/admin/" "302" "Админка требует входа (редирект на логин)"
check "/crm/" "302" "CRM требует входа (редирект на логин)"
check "/course/" "302" "Курс требует входа (редирект на логин)"
check "/this-page-does-not-exist-404-check/" "404" "Несуществующая страница отдаёт 404, не 500"

echo
if [ "$FAILED" -eq 0 ]; then
    echo "Всё хорошо — все проверки прошли."
    exit 0
else
    echo "Есть проблемы — см. FAIL выше. Проверить journalctl -u observatory -n 50 --no-pager"
    exit 1
fi
