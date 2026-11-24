# -*- coding: utf-8 -*-
"""
Скрипт резервного копирования базы данных PostgreSQL (backup.py).
Использует утилиту pg_dump и настройки подключения из config.py.
Сохраняет дамп в папку: backups/repair_shop_YYYYMMDD_HHMMSS.sql

Запуск резервного копирования:
    python backup.py

Как восстановить базу данных из созданной резервной копии:
1) Через консоль psql (для текстового SQL-дампа):
    psql -h localhost -p 5432 -U postgres -d repair_shop -f backups/repair_shop_YYYYMMDD_HHMMSS.sql
2) Или через pgAdmin:
    Откройте Query Tool в базе repair_shop, загрузите .sql файл и нажмите Execute (F5).
"""

import os
import subprocess
from datetime import datetime
from config import Config


def create_backup():
    """Создаёт резервную копию БД PostgreSQL с помощью pg_dump."""
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"repair_shop_{timestamp}.sql")

    # Передаём пароль через переменную окружения PGPASSWORD, чтобы pg_dump не запрашивал ввод вручную
    env = os.environ.copy()
    env["PGPASSWORD"] = Config.DB_PASSWORD

    command = [
        "pg_dump",
        "-h", Config.DB_HOST,
        "-p", str(Config.DB_PORT),
        "-U", Config.DB_USER,
        "-d", Config.DB_NAME,
        "-F", "p",  # plain-text SQL формат
        "-f", backup_file,
    ]

    print(f"[INFO] Запуск резервного копирования БД '{Config.DB_NAME}'...")
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"[OK] Резервная копия успешно сохранена в файл: {backup_file}")
        return backup_file
    except FileNotFoundError:
        print(
            "[ОШИБКА] Утилита pg_dump не найдена в PATH. "
            "Убедитесь, что PostgreSQL установлен и папка bin добавлена в переменную PATH."
        )
    except subprocess.CalledProcessError as exc:
        print(f"[ОШИБКА] Не удалось выполнить pg_dump (код {exc.returncode}):")
        print(exc.stderr)


if __name__ == "__main__":
    create_backup()
