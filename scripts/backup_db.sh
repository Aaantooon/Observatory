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

set -euo pipefail

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

# --- Медиа (аватары, PDF модулей и т.п.) ---
if [ -d "./media" ]; then
    tar -czf "$BACKUP_DIR/media_${DATE}.tar.gz" media/
fi

# --- Удаляем бэкапы старше KEEP_DAYS дней ---
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
find "$BACKUP_DIR" -name "media_*.tar.gz" -mtime "+${KEEP_DAYS}" -delete

echo "[$(date)] Бэкап готов: db_${DATE}.sql.gz, media_${DATE}.tar.gz"
