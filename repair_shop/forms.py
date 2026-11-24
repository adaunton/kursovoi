# -*- coding: utf-8 -*-
"""
Формы Flask-WTF (forms.py).
Все сообщения валидации переведены на русский язык.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    TextAreaField,
    SelectField,
    IntegerField,
    DecimalField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Email,
    Optional,
    NumberRange,
    Regexp,
    EqualTo,
    ValidationError,
)
from models import User, Part, Supplier, PartCategory

# Регулярное выражение для проверки номера телефона
PHONE_REGEX = r"^\+?[0-9\s\-()]{10,20}$"


class LoginForm(FlaskForm):
    """Форма входа в систему."""
    username = StringField(
        "Логин",
        validators=[DataRequired(message="Введите логин")],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Введите пароль")],
    )
    submit = SubmitField("Войти")


class RegisterForm(FlaskForm):
    """Форма самостоятельной регистрации (создаёт только роль client)."""
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Поле логина обязательно"),
            Length(min=3, max=64, message="Логин должен содержать от 3 до 64 символов"),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль"),
            Length(min=6, message="Пароль должен быть не менее 6 символов"),
        ],
    )
    confirm_password = PasswordField(
        "Повторите пароль",
        validators=[
            DataRequired(message="Повторите пароль"),
            EqualTo("password", message="Пароли не совпадают"),
        ],
    )
    full_name = StringField(
        "ФИО полностью",
        validators=[
            DataRequired(message="Укажите ваше ФИО"),
            Length(min=3, max=150, message="ФИО должно быть от 3 до 150 символов"),
        ],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите номер телефона"),
            Regexp(PHONE_REGEX, message="Некорректный формат телефона (пример: +7 (999) 123-45-67)"),
        ],
    )
    email = StringField(
        "Email (необязательно)",
        validators=[
            Optional(),
            Email(message="Введите корректный адрес электронной почты"),
        ],
    )
    submit = SubmitField("Зарегистрироваться")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("Пользователь с таким логином уже существует.")


class ProfileForm(FlaskForm):
    """Форма редактирования своего профиля (ФИО, телефон, email)."""
    full_name = StringField(
        "ФИО полностью",
        validators=[
            DataRequired(message="Укажите ФИО"),
            Length(min=3, max=150, message="ФИО должно содержать от 3 до 150 символов"),
        ],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите телефон"),
            Regexp(PHONE_REGEX, message="Некорректный формат телефона (10-20 символов)"),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            Optional(),
            Email(message="Некорректный адрес электронной почты"),
        ],
    )
    submit = SubmitField("Сохранить изменения")


class ChangePasswordForm(FlaskForm):
    """Форма смены пароля в профиле."""
    old_password = PasswordField(
        "Текущий пароль",
        validators=[DataRequired(message="Введите текущий пароль")],
    )
    new_password = PasswordField(
        "Новый пароль",
        validators=[
            DataRequired(message="Введите новый пароль"),
            Length(min=6, message="Новый пароль должен быть не менее 6 символов"),
        ],
    )
    confirm_password = PasswordField(
        "Повторите новый пароль",
        validators=[
            DataRequired(message="Повторите новый пароль"),
            EqualTo("new_password", message="Пароли не совпадают"),
        ],
    )
    submit = SubmitField("Обновить пароль")


class OrderCreateForm(FlaskForm):
    """Форма создания нового заказа."""
    device = StringField(
        "Устройство (марка, модель)",
        validators=[
            DataRequired(message="Укажите название и модель устройства"),
            Length(min=2, max=200, message="Длина от 2 до 200 символов"),
        ],
    )
    description = TextAreaField(
        "Описание неисправности",
        validators=[
            DataRequired(message="Опишите проблему или симптомы поломки"),
            Length(min=5, message="Описание должно быть не менее 5 символов"),
        ],
    )
    priority = SelectField(
        "Приоритет",
        choices=[("normal", "Обычный"), ("urgent", "Срочный")],
        default="normal",
    )
    # Поля ниже используются, если заказ оформляет мастер или администратор в приёмке
    client_id = SelectField("Клиент", coerce=int, validators=[Optional()])
    cost_preliminary = DecimalField(
        "Предварительная стоимость (₽)",
        places=2,
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0, message="Стоимость не может быть отрицательной"),
        ],
    )
    submit = SubmitField("Создать заказ")


class OrderEditForm(FlaskForm):
    """Форма полного редактирования заказа (для администратора)."""
    client_id = SelectField("Клиент", coerce=int, validators=[DataRequired()])
    master_id = SelectField("Назначенный мастер", coerce=int, validators=[Optional()])
    device = StringField(
        "Устройство",
        validators=[DataRequired(message="Укажите устройство"), Length(max=200)],
    )
    description = TextAreaField(
        "Описание неисправности",
        validators=[DataRequired(message="Введите описание неисправности")],
    )
    status = SelectField(
        "Статус заказа",
        choices=[
            ("waiting", "Ожидание"),
            ("in_work", "В работе"),
            ("ready", "Готов"),
            ("issued", "Выдан"),
        ],
    )
    priority = SelectField(
        "Приоритет",
        choices=[("normal", "Обычный"), ("urgent", "Срочный")],
    )
    cost_preliminary = DecimalField(
        "Предварительная стоимость (₽)",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message="Предварительная стоимость должна быть >= 0"),
        ],
    )
    cost_final = DecimalField(
        "Итоговая стоимость (₽)",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message="Итоговая стоимость должна быть >= 0"),
        ],
    )
    warranty_days = IntegerField(
        "Гарантия (дней)",
        default=0,
        validators=[
            DataRequired(message="Укажите срок гарантии (0 если нет)"),
            NumberRange(min=0, message="Срок гарантии не может быть отрицательным"),
        ],
    )
    submit = SubmitField("Сохранить заказ")


class OrderStatusForm(FlaskForm):
    """Форма быстрой смены статуса заказа мастером или админом."""
    status = SelectField(
        "Новый статус",
        choices=[
            ("waiting", "Ожидание"),
            ("in_work", "В работе"),
            ("ready", "Готов"),
            ("issued", "Выдан"),
        ],
        validators=[DataRequired()],
    )
    cost_final = DecimalField(
        "Итоговая стоимость ремонта (₽)",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message="Стоимость не может быть меньше 0"),
        ],
    )
    warranty_days = IntegerField(
        "Гарантия (дней)",
        validators=[
            Optional(),
            NumberRange(min=0, message="Гарантия должна быть >= 0 дней"),
        ],
    )
    submit = SubmitField("Обновить статус")


class OrderAddPartForm(FlaskForm):
    """Форма привязки запчасти со склада к заказу."""
    part_id = SelectField(
        "Запчасть со склада",
        coerce=int,
        validators=[DataRequired(message="Выберите запчасть")],
    )
    quantity = IntegerField(
        "Количество",
        default=1,
        validators=[
            DataRequired(message="Укажите количество"),
            NumberRange(min=1, message="Количество должно быть больше 0"),
        ],
    )
    submit = SubmitField("Добавить к заказу")


class OrderCommentForm(FlaskForm):
    """Форма добавления комментария к заказу."""
    text = TextAreaField(
        "Текст комментария / отчёт о проделанной работе",
        validators=[
            DataRequired(message="Введите текст комментария"),
            Length(min=2, max=2000, message="Комментарий должен быть от 2 до 2000 символов"),
        ],
    )
    submit = SubmitField("Отправить комментарий")


class PartForm(FlaskForm):
    """Форма создания и редактирования запчасти на складе."""
    name = StringField(
        "Наименование запчасти",
        validators=[
            DataRequired(message="Введите наименование запчасти"),
            Length(min=2, max=200),
        ],
    )
    article = StringField(
        "Артикул (уникальный код)",
        validators=[
            DataRequired(message="Введите артикул"),
            Length(min=2, max=80),
        ],
    )
    category_id = SelectField(
        "Категория",
        coerce=int,
        validators=[Optional()],
    )
    quantity = IntegerField(
        "Текущий остаток (шт.)",
        default=0,
        validators=[
            NumberRange(min=0, message="Остаток не может быть отрицательным"),
        ],
    )
    min_quantity = IntegerField(
        "Минимальный остаток для уведомления (шт.)",
        default=2,
        validators=[
            NumberRange(min=0, message="Минимальный остаток должен быть >= 0"),
        ],
    )
    price = DecimalField(
        "Цена за единицу (₽)",
        places=2,
        default=0,
        validators=[
            DataRequired(message="Укажите цену"),
            NumberRange(min=0, message="Цена должна быть >= 0"),
        ],
    )
    submit = SubmitField("Сохранить запчасть")

    def __init__(self, original_article=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_article = original_article

    def validate_article(self, field):
        article_clean = field.data.strip()
        if self.original_article and article_clean == self.original_article:
            return
        if Part.query.filter_by(article=article_clean).first():
            raise ValidationError("Запчасть с таким артикулом уже зарегистрирована на складе.")


class CategoryForm(FlaskForm):
    """Форма создания категории запчастей."""
    name = StringField(
        "Название категории",
        validators=[
            DataRequired(message="Введите название категории"),
            Length(min=2, max=100, message="От 2 до 100 символов"),
        ],
    )
    submit = SubmitField("Добавить категорию")

    def validate_name(self, field):
        if PartCategory.query.filter_by(name=field.data.strip()).first():
            raise ValidationError("Такая категория уже существует.")


class SupplierForm(FlaskForm):
    """Форма создания и редактирования поставщика."""
    name = StringField(
        "Название компании / ИП",
        validators=[
            DataRequired(message="Введите название поставщика"),
            Length(min=2, max=150),
        ],
    )
    contact_person = StringField(
        "Контактное лицо",
        validators=[
            DataRequired(message="Укажите контактное лицо"),
            Length(min=2, max=150),
        ],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите телефон поставщика"),
            Regexp(PHONE_REGEX, message="Некорректный формат телефона (пример: +7 (495) 111-22-33)"),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            Optional(),
            Email(message="Введите корректный Email"),
        ],
    )
    address = StringField(
        "Адрес склада / офиса",
        validators=[Optional(), Length(max=255)],
    )
    submit = SubmitField("Сохранить поставщика")

    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, field):
        name_clean = field.data.strip()
        if self.original_name and name_clean == self.original_name:
            return
        if Supplier.query.filter_by(name=name_clean).first():
            raise ValidationError("Поставщик с таким названием уже есть в базе.")


class PurchaseRequestForm(FlaskForm):
    """Форма создания и редактирования заявки на закупку."""
    part_id = SelectField(
        "Запчасть",
        coerce=int,
        validators=[DataRequired(message="Выберите запчасть")],
    )
    supplier_id = SelectField(
        "Поставщик (обязательно)",
        coerce=int,
        validators=[DataRequired(message="Выберите поставщика")],
    )
    quantity = IntegerField(
        "Количество для закупки",
        default=5,
        validators=[
            DataRequired(message="Укажите количество"),
            NumberRange(min=1, message="Количество должно быть больше 0"),
        ],
    )
    price = DecimalField(
        "Закупочная цена за шт. (₽)",
        places=2,
        validators=[
            DataRequired(message="Укажите закупочную цену"),
            NumberRange(min=0, message="Цена не может быть отрицательной"),
        ],
    )
    submit = SubmitField("Создать заявку")
