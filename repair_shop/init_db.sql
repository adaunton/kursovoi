-- ============================================================================
-- 1) Создать БД repair_shop в pgAdmin.
-- 2) Выполнить этот скрипт.
-- 3) Запустить python seed.py
-- ============================================================================
-- Скрипт создания таблиц базы данных системы управления ремонтной мастерской
-- и складом запчастей (БЕЗ начальных данных — заполнение выполняется через seed.py).

-- 1. Таблица пользователей (users)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    -- Упрощение для учебного проекта. В продакшене — хеширование (werkzeug.security)
    password VARCHAR(128) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(120),
    role VARCHAR(20) NOT NULL DEFAULT 'client'
        CHECK (role IN ('admin', 'master', 'client')),
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- 2. Таблица заказов на ремонт (orders)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    master_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    device VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'in_work', 'ready', 'issued')),
    priority VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('normal', 'urgent')),
    cost_preliminary NUMERIC(10, 2) DEFAULT 0 CHECK (cost_preliminary >= 0),
    cost_final NUMERIC(10, 2) DEFAULT 0 CHECK (cost_final >= 0),
    warranty_days INTEGER NOT NULL DEFAULT 0 CHECK (warranty_days >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issued_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_client_id ON orders (client_id);
CREATE INDEX IF NOT EXISTS idx_orders_master_id ON orders (master_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at);

-- 3. Таблица комментариев и истории работ по заказу (order_comments)
CREATE TABLE IF NOT EXISTS order_comments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_comments_order_id ON order_comments (order_id);

-- 4. Таблица категорий запчастей (part_categories)
CREATE TABLE IF NOT EXISTS part_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 5. Таблица запчастей на складе (parts)
CREATE TABLE IF NOT EXISTS parts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    article VARCHAR(80) NOT NULL UNIQUE,
    category_id INTEGER REFERENCES part_categories(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    min_quantity INTEGER NOT NULL DEFAULT 2 CHECK (min_quantity >= 0),
    price NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (price >= 0)
);

CREATE INDEX IF NOT EXISTS idx_parts_article ON parts (article);
CREATE INDEX IF NOT EXISTS idx_parts_category_id ON parts (category_id);

-- 6. Таблица поставщиков (suppliers)
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    contact_person VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(120),
    address VARCHAR(255)
);

-- 7. Таблица привязанных к заказам запчастей (order_parts)
CREATE TABLE IF NOT EXISTS order_parts (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    written_off BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_order_parts_order_id ON order_parts (order_id);

-- 8. Таблица заявок на закупку запчастей (purchase_requests)
CREATE TABLE IF NOT EXISTS purchase_requests (
    id SERIAL PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    price NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'approved', 'received')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_purchase_requests_status ON purchase_requests (status);

-- 9. Таблица истории движения запчастей на складе (stock_movements)
CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    type VARCHAR(20) NOT NULL
        CHECK (type IN ('income', 'outcome', 'adjustment')),
    quantity INTEGER NOT NULL,
    comment VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_part_id ON stock_movements (part_id);

-- 10. Таблица журнала действий пользователей (action_logs)
CREATE TABLE IF NOT EXISTS action_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(64) NOT NULL,
    action VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_action_logs_created_at ON action_logs (created_at);
