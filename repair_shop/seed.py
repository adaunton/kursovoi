# -*- coding: utf-8 -*-
"""
Скрипт заполнения базы данных начальными тестовыми данными (seed.py).
Идемпотентный: если пользователи в БД уже существуют, повторная вставка пропускается.
Запуск: python seed.py
"""

from datetime import datetime, timedelta
from app import app
from models import (
    db,
    User,
    PartCategory,
    Part,
    Supplier,
    Order,
    OrderPart,
    OrderComment,
    PurchaseRequest,
    StockMovement,
    ActionLog,
)


def seed_database():
    """Заполняет базу данных тестовыми записями для защиты курсового проекта."""
    with app.app_context():
        # Создаём таблицы на случай, если init_db.sql не был запущен вручную
        db.create_all()

        # Проверяем идемпотентность: если пользователи уже есть — выходим
        if User.query.first() is not None:
            print("[INFO] База данных уже содержит данные. Повторное заполнение пропущено.")
            return

        print("[INFO] Начинаем заполнение БД тестовыми данными...")

        # 1. Три пользователя (пароли ОТКРЫТЫМ ТЕКСТОМ согласно заданию)
        admin = User(
            username="admin",
            password="admin123",
            full_name="Иванов Иван",
            phone="+7 (900) 111-22-33",
            email="admin@repair-shop.local",
            role="admin",
            is_blocked=False,
        )
        master = User(
            username="master",
            password="master123",
            full_name="Петров Пётр",
            phone="+7 (900) 222-33-44",
            email="master@repair-shop.local",
            role="master",
            is_blocked=False,
        )
        client = User(
            username="client",
            password="client123",
            full_name="Сидоров Сидор",
            phone="+7 (900) 333-44-55",
            email="client@repair-shop.local",
            role="client",
            is_blocked=False,
        )
        db.session.add_all([admin, master, client])
        db.session.flush()

        # 2. Три категории запчастей: Экраны, Батареи, Разъёмы
        cat_screens = PartCategory(name="Экраны")
        cat_batteries = PartCategory(name="Батареи")
        cat_connectors = PartCategory(name="Разъёмы")
        db.session.add_all([cat_screens, cat_batteries, cat_connectors])
        db.session.flush()

        # 3. Пять запчастей (с категориями; часть с низким остатком для демонстрации автозаявки)
        part1 = Part(
            name="Дисплейный модуль iPhone 13 OLED",
            article="SCR-IP13-OLED",
            category_id=cat_screens.id,
            quantity=6,
            min_quantity=2,
            price=6500.00,
        )
        part2 = Part(
            name="Дисплей Samsung Galaxy A54 Super AMOLED",
            article="SCR-SAM-A54",
            category_id=cat_screens.id,
            quantity=1,  # <= min_quantity (2) — попадёт в блок «Требуется закупка»
            min_quantity=2,
            price=4800.00,
        )
        part3 = Part(
            name="Аккумулятор iPhone 12 (2815 mAh)",
            article="BAT-IP12-ORIG",
            category_id=cat_batteries.id,
            quantity=8,
            min_quantity=3,
            price=2200.00,
        )
        part4 = Part(
            name="Аккумулятор Xiaomi Redmi Note 12 (BN5M)",
            article="BAT-XIA-RN12",
            category_id=cat_batteries.id,
            quantity=2,  # <= min_quantity (3) — попадёт в блок «Требуется закупка»
            min_quantity=3,
            price=1450.00,
        )
        part5 = Part(
            name="Разъём зарядки USB Type-C (универсальный 24-pin)",
            article="CON-USBC-24P",
            category_id=cat_connectors.id,
            quantity=15,
            min_quantity=5,
            price=350.00,
        )
        db.session.add_all([part1, part2, part3, part4, part5])
        db.session.flush()

        # 4. Три поставщика: ООО «Ромашка», ИП Иванов, ООО «ТехноСнаб»
        sup1 = Supplier(
            name="ООО «Ромашка»",
            contact_person="Кузнецова Анна Сергеевна",
            phone="+7 (495) 101-20-30",
            email="zakaz@romashka-parts.ru",
            address="г. Москва, ул. Складочная, д. 1, стр. 18",
        )
        sup2 = Supplier(
            name="ИП Иванов",
            contact_person="Иванов Алексей Викторович",
            phone="+7 (916) 555-77-88",
            email="ip-ivanov-gsm@mail.ru",
            address="г. Москва, Савёловский проезд, пав. Б-42",
        )
        sup3 = Supplier(
            name="ООО «ТехноСнаб»",
            contact_person="Морозов Дмитрий Игоревич",
            phone="+7 (499) 700-80-90",
            email="supply@tehnosnab-pro.ru",
            address="г. Санкт-Петербург, пр. Обуховской Обороны, д. 86",
        )
        db.session.add_all([sup1, sup2, sup3])
        db.session.flush()

        now = datetime.now()

        # 5. Три заказа в разных статусах (waiting, in_work, ready)
        order1 = Order(
            client_id=client.id,
            master_id=None,
            device="Смартфон Xiaomi Redmi Note 12",
            description="Быстро разряжается аккумулятор, выключается на 25% заряда.",
            status="waiting",
            priority="normal",
            cost_preliminary=2500.00,
            cost_final=0.00,
            warranty_days=30,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
            accepted_at=now - timedelta(days=2),
        )
        order2 = Order(
            client_id=client.id,
            master_id=master.id,
            device="Apple iPhone 13 128GB",
            description="Разбито стекло дисплея после падения, сенсор частично не реагирует.",
            status="in_work",
            priority="urgent",
            cost_preliminary=8500.00,
            cost_final=8500.00,
            warranty_days=90,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=1),
            accepted_at=now - timedelta(days=5),
        )
        order3 = Order(
            client_id=client.id,
            master_id=master.id,
            device="Apple iPhone 12 64GB",
            description="Замена вздувшегося аккумулятора и чистка разъёма зарядки.",
            status="ready",
            priority="normal",
            cost_preliminary=3500.00,
            cost_final=3700.00,
            warranty_days=60,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(hours=5),
            accepted_at=now - timedelta(days=10),
        )
        db.session.add_all([order1, order2, order3])
        db.session.flush()

        # Привязываем запчасти к заказам #2 и #3
        op1 = OrderPart(
            order_id=order2.id,
            part_id=part1.id,
            quantity=1,
            written_off=False,  # заказ ещё в работе
        )
        op2 = OrderPart(
            order_id=order3.id,
            part_id=part3.id,
            quantity=1,
            written_off=True,   # заказ готов, запчасть списана
        )
        db.session.add_all([op1, op2])

        # Комментарии к заказам
        comment1 = OrderComment(
            order_id=order2.id,
            user_id=master.id,
            text="Проведена диагностика: материнская плата не повреждена, требуется замена дисплейного модуля OLED.",
            created_at=now - timedelta(days=3),
        )
        comment2 = OrderComment(
            order_id=order3.id,
            user_id=master.id,
            text="Установлен новый аккумулятор, проведено тестирование контроллера питания. Аппарат готов к выдаче.",
            created_at=now - timedelta(hours=5),
        )
        db.session.add_all([comment1, comment2])

        # 6. Две заявки на закупку
        pr1 = PurchaseRequest(
            part_id=part2.id,
            supplier_id=sup1.id,
            quantity=5,
            price=4200.00,
            status="new",
            created_by=master.id,
            created_at=now - timedelta(days=1),
        )
        pr2 = PurchaseRequest(
            part_id=part4.id,
            supplier_id=sup3.id,
            quantity=10,
            price=1150.00,
            status="approved",
            created_by=admin.id,
            created_at=now - timedelta(days=3),
        )
        db.session.add_all([pr1, pr2])

        # 7. Пять записей истории движения склада (StockMovement)
        movements = [
            StockMovement(
                part_id=part1.id,
                user_id=admin.id,
                type="income",
                quantity=6,
                comment="Первичное поступление от ООО «Ромашка»",
                created_at=now - timedelta(days=15),
            ),
            StockMovement(
                part_id=part2.id,
                user_id=admin.id,
                type="income",
                quantity=1,
                comment="Первичное поступление от ООО «Ромашка»",
                created_at=now - timedelta(days=14),
            ),
            StockMovement(
                part_id=part3.id,
                user_id=admin.id,
                type="income",
                quantity=9,
                comment="Закупка партии аккумуляторов у ООО «ТехноСнаб»",
                created_at=now - timedelta(days=12),
            ),
            StockMovement(
                part_id=part5.id,
                user_id=admin.id,
                type="income",
                quantity=15,
                comment="Поставка разъёмов USB Type-C от ИП Иванов",
                created_at=now - timedelta(days=11),
            ),
            StockMovement(
                part_id=part3.id,
                user_id=master.id,
                type="outcome",
                quantity=-1,
                comment=f"Списание по заказу #{order3.id}",
                created_at=now - timedelta(hours=5),
            ),
        ]
        db.session.add_all(movements)

        # Записи в журнал действий (ActionLog)
        logs = [
            ActionLog(
                user_id=admin.id,
                username="admin",
                action="Инициализация базы данных и справочников склада",
                entity_type="system",
                entity_id=1,
                created_at=now - timedelta(days=15),
            ),
            ActionLog(
                user_id=client.id,
                username="client",
                action=f"Создан заказ #{order1.id} ({order1.device})",
                entity_type="order",
                entity_id=order1.id,
                created_at=now - timedelta(days=2),
            ),
            ActionLog(
                user_id=master.id,
                username="master",
                action=f"Создана заявка на закупку #{pr1.id} ({part2.name})",
                entity_type="purchase_request",
                entity_id=1,
                created_at=now - timedelta(days=1),
            ),
            ActionLog(
                user_id=master.id,
                username="master",
                action=f"Изменён статус заказа #{order3.id}: in_work -> ready",
                entity_type="order",
                entity_id=order3.id,
                created_at=now - timedelta(hours=5),
            ),
        ]
        db.session.add_all(logs)

        db.session.commit()
        print("[OK] Тестовые данные успешно добавлены!")
        print("Тестовые учётные записи:")
        print("  Администратор : admin  / admin123")
        print("  Мастер        : master / master123")
        print("  Клиент        : client / client123")


if __name__ == "__main__":
    seed_database()
