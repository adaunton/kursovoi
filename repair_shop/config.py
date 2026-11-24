# -*- coding: utf-8 -*-
"""
Файл конфигурации приложения (config.py).
Перед запуском проекта обязательно укажите свои данные для подключения к PostgreSQL!
"""


class Config:
    # Секретный ключ для защиты сессий и CSRF-токенов в формах Flask-WTF.
    # ЗАМЕНИТЕ на любую случайную строку перед использованием.
    SECRET_KEY = "CHANGE_ME_SECRET_KEY"

    # Параметры подключения к базе данных PostgreSQL:
    # 1. Впишите имя пользователя PostgreSQL (обычно 'postgres') вместо CHANGE_ME_USER
    DB_USER = "postgres"
    # 2. Впишите пароль от вашего пользователя PostgreSQL вместо CHANGE_ME_PASSWORD
    DB_PASSWORD = "123456"
    # 3. Хост и порт БД (по умолчанию локальный сервер на порту 5432)
    DB_HOST = "localhost"
    DB_PORT = "5432"
    # 4. Впишите название созданной в pgAdmin базы данных (например, 'repair_shop')
    DB_NAME = "repair_shop"

    # Строка подключения SQLAlchemy (собирается автоматически из параметров выше)
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?client_encoding=utf8"
    )

    # Отключаем отслеживание модификаций объектов для экономии памяти
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Путь к файлу текстового лога действий пользователей
    LOG_FILE = "logs/app.log"

    # Количество элементов на одной странице при пагинации
    PAGE_SIZE = 20
