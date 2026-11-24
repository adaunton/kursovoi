# Система управления заказами ремонтной мастерской и складом запчастей

Учебный курсовой проект на **Python 3.11+ / Flask / PostgreSQL**.
Полнофункциональная веб-система для автоматизации работы сервисного центра: приём и ведение заказов на ремонт, автоматическое списание запчастей со склада, контроль минимальных остатков, формирование заявок поставщикам, аналитические графики Chart.js и журналирование действий.

---

## Пошаговая инструкция по запуску

1. **Создать БД `repair_shop` в pgAdmin**
   Откройте pgAdmin 4, создайте новую базу данных с именем `repair_shop` (кодировка `UTF8`).

2. **Выполнить `init_db.sql`**
   Откройте Query Tool для базы `repair_shop`, загрузите файл `init_db.sql` и выполните его (F5). Будут созданы все 10 таблиц, индексы и ограничения `CHECK`.

3. **Вписать данные в `config.py` (`DB_USER`, `DB_PASSWORD`, `DB_NAME`)**
   Откройте файл `config.py` и замените плейсхолдеры на ваши реальные параметры PostgreSQL:
   ```python
   DB_USER = "postgres"
   DB_PASSWORD = "ваш_пароль_от_postgresql"
   DB_NAME = "repair_shop"
   ```

4. **Установить зависимости**
   ```bash
   pip install -r requirements.txt
   ```

5. **Заполнить базу тестовыми данными**
   ```bash
   python seed.py
   ```

6. **Запустить приложение**
   ```bash
   python app.py
   ```

7. **Открыть в браузере**
   Перейдите по адресу: [http://127.0.0.1:5000](http://127.0.0.1:5000)

8. **Тестовые логины (пароли хранятся в открытом виде для учебного проекта)**
   - Администратор: `admin` / `admin123`
   - Мастер по ремонту: `master` / `master123`
   - Клиент: `client` / `client123`

---

## Бэкап базы данных

Для создания резервной копии базы данных PostgreSQL выполните команду:
```bash
python backup.py
```
Скрипт вызовет утилиту `pg_dump` с параметрами из `config.py` и сохранит SQL-дамп в папку:
`backups/repair_shop_YYYYMMDD_HHMMSS.sql`

Для восстановления базы из резервной копии:
```bash
psql -h localhost -p 5432 -U postgres -d repair_shop -f backups/repair_shop_YYYYMMDD_HHMMSS.sql
```

---

## Структура проекта

```text
repair_shop/
├── app.py                # Точка входа, create_app(), обработчики ошибок 403/404/500
├── config.py             # Конфигурация подключения к PostgreSQL и параметров приложения
├── models.py             # SQLAlchemy-модели (10 таблиц БД)
├── forms.py              # Формы Flask-WTF с валидацией на русском языке
├── routes.py             # Все маршруты приложения (без Blueprint)
├── utils.py              # Декоратор @role_required, логирование, списание запчастей, экспорт CSV
├── init_db.sql           # Чистый SQL-скрипт создания таблиц, индексов и CHECK-ограничений
├── seed.py               # Идемпотентный скрипт начального заполнения тестовыми данными
├── backup.py             # Скрипт резервного копирования БД через pg_dump
├── requirements.txt      # Список Python-библиотек
├── README.md             # Документация проекта
├── static/
│   └── style.css         # Минимальные вспомогательные стили в дополнение к Bootstrap 5 CDN
├── logs/                 # Папка для текстового лога logs/app.log (создаётся автоматически)
└── templates/            # Серверные шаблоны Jinja2 на базе Bootstrap 5
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── 404.html
    ├── 500.html
    ├── profile.html
    ├── orders/           # list.html, form.html, detail.html
    ├── parts/            # list.html, form.html, history.html, categories.html
    ├── suppliers/        # list.html, form.html
    ├── purchase_requests/# list.html, form.html
    └── users/            # list.html, logs.html
```
