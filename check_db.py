cat > check_db.py << 'EOF'
import MySQLdb

try:
    conn = MySQLdb.connect(
        host='localhost',
        user='ci666774_observatorydb',       # Логин = имя базы (как в панели)
        passwd='НОВЫЙ_ПАРОЛЬ_ОТ_ШАГА_1',      # <-- ВСТАВЬ СЮДА НОВЫЙ ПАРОЛЬ
        db='ci666774_observatorydb',          # Имя базы
        port=3306,
    )
    print("OK — соединение успешно!")
    conn.close()
except MySQLdb.Error as e:
    print(f"Ошибка подключения: {e}")
EOF
