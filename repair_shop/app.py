# -*- coding: utf-8 -*-
"""
Точка входа в приложение (app.py).
Содержит функцию create_app(), настройку Flask-Login и обработчики ошибок 403/404/500.
Без Blueprint-архитектуры и сложных абстракций — всё просто и наглядно для учебного проекта.
"""

import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db, User

# Инициализируем менеджер авторизации и CSRF-защиту
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Пожалуйста, войдите в систему для доступа к этой странице."
login_manager.login_message_category = "warning"

csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя из БД по его ID для сессии Flask-Login."""
    return db.session.get(User, int(user_id))


def create_app():
    """Создание и настройка экземпляра приложения Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Автоматически создаём папку для логов, если её ещё нет
    os.makedirs("logs", exist_ok=True)

    # Подключаем расширения к приложению
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Регистрируем все маршруты из модуля routes.py
    from routes import register_routes
    register_routes(app)

    # Обработчики ошибок HTTP (403, 404, 500)
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("404.html", error_code=403, error_title="Доступ запрещён (403)"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("404.html", error_code=404, error_title="Страница не найдена (404)"), 404

    @app.errorhandler(500)
    def internal_error(error):
        # При внутренней ошибке сервера обязательно откатываем незавершённую транзакцию БД
        db.session.rollback()
        return render_template("500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    # Запуск встроенного сервера разработки на http://127.0.0.1:5000
    app.run(host="127.0.0.1", port=5000, debug=True)
