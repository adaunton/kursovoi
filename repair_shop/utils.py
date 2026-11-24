# -*- coding: utf-8 -*-
"""
Вспомогательные функции (utils.py):
- декоратор проверки ролей @role_required
- функция логирования действий в БД и текстовый файл log_action()
- транзакционная функция списания запчастей со склада write_off_parts()
- функция формирования CSV-выгрузки заказов export_orders_to_csv()
"""

import os
import csv
import io
import logging
from functools import wraps
from datetime import datetime
from flask import flash, abort
from flask_login import current_user
from config import Config
from models import db, ActionLog, StockMovement

# Убеждаемся, что папка logs/ существует
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)

# Настраиваем запись в текстовый лог-файл logs/app.log
file_logger = logging.getLogger("repair_shop_logger")
file_logger.setLevel(logging.INFO)
if not file_logger.handlers:
    file_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)
    file_logger.addHandler(file_handler)


def role_required(*roles):
    """
    Декоратор для ограничения доступа к маршруту по роли пользователя.
    Пример использования:
        @app.route('/users')
        @login_required
        @role_required('admin')
        def users_list(): ...
    Если роль текущего пользователя не входит в список разрешённых —
    показывается flash-сообщение и возвращается код 403.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in roles:
                flash("У вас недостаточно прав для выполнения этого действия.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_action(user, action, entity_type=None, entity_id=None, commit=True):
    """
    Записывает действие пользователя:
    1) В таблицу action_logs в БД PostgreSQL
    2) В текстовый файл logs/app.log в формате:
       2026-01-15 14:32:10 | admin | Создан заказ #5
    """
    username = user.username if user and hasattr(user, "username") else "гость"
    user_id = user.id if user and hasattr(user, "id") else None

    log_entry = ActionLog(
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at=datetime.now(),
    )
    db.session.add(log_entry)
    if commit:
        db.session.commit()

    # Форматируем строку для текстового файла
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp_str} | {username} | {action}"
    file_logger.info(log_line)


def write_off_parts(order, user):
    """
    Транзакционное списание запчастей со склада при переводе заказа в статус 'ready' («Готов»).

    Логика работы:
    1. Перебираем все позиции OrderPart данного заказа, где written_off == False.
    2. Проверяем, хватает ли остатка на складе (part.quantity >= order_part.quantity).
    3. Если хотя бы одной запчасти не хватает:
       - откатываем транзакцию (db.session.rollback())
       - выводим flash-сообщение «Недостаточно запчастей: <name>»
       - возвращаем False (статус заказа НЕ меняется).
    4. Если всех запчастей достаточно:
       - уменьшаем остаток part.quantity -= order_part.quantity
       - ставим флаг order_part.written_off = True
       - создаём запись движения склада StockMovement(type='outcome', quantity=-N)
       - записываем событие в ActionLog.
    """
    try:
        for order_part in order.order_parts:
            if not order_part.written_off:
                part = order_part.part
                if part.quantity < order_part.quantity:
                    db.session.rollback()
                    flash(f"Недостаточно запчастей: {part.name}", "danger")
                    return False

                # Уменьшаем остаток на складе
                part.quantity -= order_part.quantity
                order_part.written_off = True

                # Записываем расход в историю движения склада
                movement = StockMovement(
                    part_id=part.id,
                    user_id=user.id if user else None,
                    type="outcome",
                    quantity=-order_part.quantity,
                    comment=f"Списание по заказу #{order.id}",
                    created_at=datetime.now(),
                )
                db.session.add(movement)

                # Логируем списание без промежуточного коммита (единая транзакция)
                log_action(
                    user=user,
                    action=f"Списание запчасти '{part.name}' ({order_part.quantity} шт.) по заказу #{order.id}",
                    entity_type="order",
                    entity_id=order.id,
                    commit=False,
                )
        return True
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка при списании запчастей: {exc}", "danger")
        return False


def export_orders_to_csv(orders):
    """
    Генерирует CSV-файл со списком заказов (с поддержкой кириллицы в Excel через UTF-8 BOM).
    Возвращает байтовую строку для отправки пользователю.
    """
    output = io.StringIO()
    # Добавляем BOM для корректного открытия русского текста в Microsoft Excel
    output.write("\ufeff")

    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "ID заказа",
            "Дата приёма",
            "Клиент",
            "Телефон клиента",
            "Мастер",
            "Устройство",
            "Описание неисправности",
            "Приоритет",
            "Статус",
            "Предварительная стоимость (руб.)",
            "Итоговая стоимость (руб.)",
            "Гарантия (дней)",
            "Дата выдачи",
        ]
    )

    status_map = {
        "waiting": "Ожидание",
        "in_work": "В работе",
        "ready": "Готов",
        "issued": "Выдан",
    }
    priority_map = {
        "normal": "Обычный",
        "urgent": "Срочный",
    }

    for o in orders:
        writer.writerow(
            [
                o.id,
                o.accepted_at.strftime("%d.%m.%Y %H:%M") if o.accepted_at else "",
                o.client.full_name if o.client else "",
                o.client.phone if o.client else "",
                o.master.full_name if o.master else "Не назначен",
                o.device,
                o.description,
                priority_map.get(o.priority, o.priority),
                status_map.get(o.status, o.status),
                f"{o.cost_preliminary or 0:.2f}",
                f"{o.cost_final or 0:.2f}",
                o.warranty_days,
                o.issued_at.strftime("%d.%m.%Y %H:%M") if o.issued_at else "",
            ]
        )

    return output.getvalue().encode("utf-8")
