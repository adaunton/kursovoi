# -*- coding: utf-8 -*-
"""
Модели базы данных SQLAlchemy (models.py).
Описывают таблицы системы управления заказами ремонтной мастерской и складом запчастей.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

# Инициализируем объект SQLAlchemy (привязывается к app в app.py)
db = SQLAlchemy()


class User(db.Model, UserMixin):
    """
    Модель пользователя системы.
    Роли: 'admin' (администратор), 'master' (мастер по ремонту), 'client' (клиент).
    Упрощение для учебного проекта. В продакшене — хеширование (werkzeug.security)
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # Упрощение для учебного проекта. В продакшене — хеширование (werkzeug.security)
    password = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="client")  # admin / master / client
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    # Связи с заказами (как клиент и как назначенный мастер)
    client_orders = db.relationship(
        "Order", foreign_keys="Order.client_id", backref="client", lazy="dynamic"
    )
    master_orders = db.relationship(
        "Order", foreign_keys="Order.master_id", backref="master", lazy="dynamic"
    )

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Order(db.Model):
    """
    Модель заказа на ремонт техники.
    Статусы:
      - waiting  («Ожидание»)
      - in_work  («В работе»)
      - ready    («Готов»)
      - issued   («Выдан»)
    Приоритеты:
      - normal   («Обычный»)
      - urgent   («Срочный»)
    """
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    master_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    device = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="waiting", index=True)
    priority = db.Column(db.String(20), nullable=False, default="normal")

    cost_preliminary = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    cost_final = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    warranty_days = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
    accepted_at = db.Column(db.DateTime, nullable=True, default=datetime.now)
    issued_at = db.Column(db.DateTime, nullable=True)

    # Комментарии к заказу и привязанные запчасти
    comments = db.relationship(
        "OrderComment",
        backref="order",
        cascade="all, delete-orphan",
        order_by="OrderComment.created_at.asc()",
    )
    order_parts = db.relationship(
        "OrderPart",
        backref="order",
        cascade="all, delete-orphan",
    )

    @property
    def parts_total_cost(self):
        """Подсчёт общей стоимости запчастей, привязанных к заказу."""
        total = 0
        for item in self.order_parts:
            if item.part and item.part.price:
                total += float(item.part.price) * item.quantity
        return round(total, 2)

    def __repr__(self):
        return f"<Order #{self.id} {self.device} [{self.status}]>"


class OrderComment(db.Model):
    """
    История работ и комментарии к заказу.
    Мастер, администратор или клиент (для своего заказа) могут оставлять сообщения.
    """
    __tablename__ = "order_comments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", backref="comments")

    def __repr__(self):
        return f"<OrderComment #{self.id} for Order #{self.order_id}>"


class PartCategory(db.Model):
    """
    Категория запчастей на складе (например: Экраны, Батареи, Разъёмы).
    """
    __tablename__ = "part_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    parts = db.relationship("Part", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<PartCategory {self.name}>"


class Part(db.Model):
    """
    Запчасть на складе.
    Если quantity <= min_quantity, система сигнализирует о необходимости закупки.
    """
    __tablename__ = "parts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    article = db.Column(db.String(80), unique=True, nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("part_categories.id", ondelete="SET NULL"), nullable=True
    )
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_quantity = db.Column(db.Integer, nullable=False, default=2)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    movements = db.relationship(
        "StockMovement",
        backref="part",
        cascade="all, delete-orphan",
        order_by="StockMovement.created_at.desc()",
    )

    def __repr__(self):
        return f"<Part {self.article} - {self.name} (остаток: {self.quantity})>"


class Supplier(db.Model):
    """
    Поставщик запчастей.
    """
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    contact_person = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)

    purchase_requests = db.relationship("PurchaseRequest", backref="supplier", lazy="dynamic")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class OrderPart(db.Model):
    """
    Связка «Заказ — Запчасть».
    Поле written_off показывает, была ли запчасть уже списана со склада
    при переводе заказа в статус 'ready' («Готов»).
    """
    __tablename__ = "order_parts"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    written_off = db.Column(db.Boolean, nullable=False, default=False)

    part = db.relationship("Part", backref="order_usages")

    def __repr__(self):
        return f"<OrderPart Order#{self.order_id} Part#{self.part_id} x{self.quantity}>"


class PurchaseRequest(db.Model):
    """
    Заявка на закупку запчастей у поставщика.
    Статусы:
      - new      («Новая»)
      - approved («Одобрена»)
      - received («Получена» — при переходе в этот статус остаток запчасти пополняется)
    """
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="new", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    part = db.relationship("Part", backref="purchase_requests")
    creator = db.relationship("User", backref="created_purchase_requests")

    def __repr__(self):
        return f"<PurchaseRequest #{self.id} status={self.status}>"


class StockMovement(db.Model):
    """
    История движения запчастей на складе.
    Типы (type):
      - income     (приход, quantity > 0)
      - outcome    (расход/списание по заказу, quantity < 0)
      - adjustment (корректировка остатка)
    """
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # income / outcome / adjustment
    quantity = db.Column(db.Integer, nullable=False)  # + для прихода, - для расхода
    comment = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", backref="stock_movements")

    def __repr__(self):
        return f"<StockMovement Part#{self.part_id} {self.type} {self.quantity}>"


class ActionLog(db.Model):
    """
    Журнал действий пользователей для контроля администратором.
    """
    __tablename__ = "action_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    user = db.relationship("User", backref="action_logs")

    def __repr__(self):
        return f"<ActionLog {self.username}: {self.action}>"
