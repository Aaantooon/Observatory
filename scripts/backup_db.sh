#!/bin/bash
# Бэкап базы данных (Postgres) и папки media/ (аватары, загруженные файлы).
# Хранит бэкапы за последние KEEP_DAYS дней, старые удаляет автоматически.
#
# Настройка (один раз на сервере):
#   chmod +x scripts/backup_db.sh
#   crontab -e
#   # каждый день в 4:00 ночи:
#   0 4 * * * /root/Observatory/scripts/backup_db.sh >> /root/Observatory/backups/backup.log 2>&1
#
# Проверить, что сработало: cat backups/backup.log
#
# Копия на Яндекс.Диск (02.09.2026): помимо локальной папки backups/ на
# самом сервере, свежий дамп дополнительно копируется в облако — иначе при
# потере/удалении самого сервера все локальные бэкапы пропадают вместе с
# ним. Настройка (один раз, до первого запуска этой версии скрипта):
#   1. https://id.yandex.ru/security/app-passwords → создать пароль
#      приложения с назначением «Яндекс Диск» (WebDAV)
#   2. rclone config create yandex webdav url https://webdav.yandex.ru \
#        vendor other user ТВОЙ_ЛОГИН pass ТВОЙ_ПАРОЛЬ_ПРИЛОЖЕНИЯ
#   3. rclone lsd yandex:   — должно отработать без ошибки
#   (лайв-проверка 02.09.2026: залив 2 МБ занял ~60-90 сек — это нормально,
#   не баг; см. --bind/--timeout в _copy_to_yandex ниже)
# Если rclone не установлен или remote "yandex:" не настроен — шаг просто
# молча пропускается (весь остальной бэкап при этом всё равно отрабатывает
# как раньше, ничего не ломается).

set -euo pipefail

YANDEX_REMOTE="yandex:Observatory-backups"

# Копирует файл на Яндекс.Диск, если rclone доступен и remote настроен.
# Намеренно не роняет весь скрипт при сбое (сеть, протухший пароль
# приложения и т.п.) — локальный бэкап к этому моменту уже готов, это
# только дополнительная подстраховка сверху.
_copy_to_yandex() {
    local file="$1"
    if ! command -v rclone >/dev/null 2>&1; then
        return 0
    fi
    if ! rclone listremotes 2>/dev/null | grep -q "^yandex:$"; then
        return 0
    fi
    # --bind 0.0.0.0 — форсирует IPv4: без этого соединение иногда уходило
    # по IPv6, а на нём заливка файла зависала намертво (мелкие запросы,
    # такие как список папок, проходили нормально, а сама передача файла —
    # нет; похоже на типичный обрыв ICMP "Packet Too Big" где-то по пути).
    # --timeout 180s — у Яндекс.Диска по WebDAV скорость отдачи заметно
    # ограничена (на практике ~30-60 КБ/с), стандартного таймаута мало.
    if rclone copy "$file" "$YANDEX_REMOTE/" --quiet --bind 0.0.0.0 --timeout 180s; then
        echo "[$(date)] → скопировано на Яндекс.Диск: $(basename "$file")"
    else
        echo "[$(date)] ⚠️ Не удалось скопировать на Яндекс.Диск: $(basename "$file")"
    fi
}

cd "$(dirname "$0")/.."   # в корень проекта, независимо от того, откуда запущен

# Читаем DB_NAME/DB_USER/DB_HOST/DB_PORT из .env (пароль передаём через PGPASSWORD)
set -a
source .env
set +a

BACKUP_DIR="./backups"
KEEP_DAYS=14
DATE=$(date +%Y-%m-%d_%H-%M)

mkdir -p "$BACKUP_DIR"

# --- База данных ---
export PGPASSWORD="$DB_PASSWORD"
pg_dump -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME" \
    | gzip > "$BACKUP_DIR/db_${DATE}.sql.gz"
unset PGPASSWORD
_copy_to_yandex "$BACKUP_DIR/db_${DATE}.sql.gz"

# --- Медиа (аватары, PDF модулей и т.п.) ---
MEDIA_NOTE="медиа пропущены (папки media/ ещё нет)"
if [ -d "./media" ]; then
    tar -czf "$BACKUP_DIR/media_${DATE}.tar.gz" media/
    MEDIA_NOTE="media_${DATE}.tar.gz"
    _copy_to_yandex "$BACKUP_DIR/media_${DATE}.tar.gz"
fi

# --- Удаляем бэкапы старше KEEP_DAYS дней ---
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
find "$BACKUP_DIR" -name "media_*.tar.gz" -mtime "+${KEEP_DAYS}" -delete

echo "[$(date)] Бэкап готов: db_${DATE}.sql.gz, ${MEDIA_NOTE}"
