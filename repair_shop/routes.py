# -*- coding: utf-8 -*-
"""
Все маршруты (роуты) приложения (routes.py).
Реализованы строго по техническому заданию без использования Blueprint.
"""

from datetime import datetime, timedelta
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    Response,
)
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_, func
from config import Config
from models import (
    db,
    User,
    Order,
    OrderComment,
    PartCategory,
    Part,
    Supplier,
    OrderPart,
    PurchaseRequest,
    StockMovement,
    ActionLog,
)
from forms import (
    LoginForm,
    RegisterForm,
    ProfileForm,
    ChangePasswordForm,
    OrderCreateForm,
    OrderEditForm,
    OrderStatusForm,
    OrderAddPartForm,
    OrderCommentForm,
    PartForm,
    CategoryForm,
    SupplierForm,
    PurchaseRequestForm,
)
from utils import role_required, log_action, write_off_parts, export_orders_to_csv


def register_routes(app):
    """Регистрирует все маршруты в объекте Flask app."""

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    # =========================================================================
    # АВТОРИЗАЦИЯ И ПРОФИЛЬ (/login, /register, /logout, /profile)
    # =========================================================================

    @app.route("/register", methods=["GET", "POST"])
    def register():
        """Самостоятельная регистрация создаёт ТОЛЬКО пользователя с ролью client."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = RegisterForm()
        if form.validate_on_submit():
            # Пароль сохраняется в открытом виде согласно требованиям учебного проекта
            new_user = User(
                username=form.username.data.strip(),
                password=form.password.data,
                full_name=form.full_name.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip() if form.email.data else None,
                role="client",
                is_blocked=False,
            )
            db.session.add(new_user)
            db.session.commit()

            log_action(new_user, f"Зарегистрирован новый клиент {new_user.username}", "user", new_user.id)
            flash("Регистрация прошла успешно! Теперь вы можете войти в систему.", "success")
            return redirect(url_for("login"))

        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Вход в систему. Проверка пароля в открытом виде: user.password == form.password.data."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data.strip()).first()
            # Прямое сравнение пароля в открытом виде
            if user and user.password == form.password.data:
                if user.is_blocked:
                    flash("Ваша учётная запись заблокирована администратором.", "danger")
                    return render_template("login.html", form=form)

                login_user(user)
                log_action(user, "Вход в систему", "user", user.id)
                flash(f"Добро пожаловать, {user.full_name}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Неверный логин или пароль.", "danger")

        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        """Выход из системы."""
        log_action(current_user, "Выход из системы", "user", current_user.id)
        logout_user()
        flash("Вы вышли из системы.", "info")
        return redirect(url_for("login"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        """Просмотр и редактирование своего профиля (ФИО, телефон, email)."""
        profile_form = ProfileForm(obj=current_user)
        password_form = ChangePasswordForm()

        if profile_form.validate_on_submit() and "submit_profile" in request.form:
            current_user.full_name = profile_form.full_name.data.strip()
            current_user.phone = profile_form.phone.data.strip()
            current_user.email = profile_form.email.data.strip() if profile_form.email.data else None
            db.session.commit()

            log_action(current_user, "Обновлён личный профиль", "user", current_user.id)
            flash("Данные профиля успешно обновлены.", "success")
            return redirect(url_for("profile"))

        return render_template(
            "profile.html",
            profile_form=profile_form,
            password_form=password_form,
        )

    @app.route("/profile/password", methods=["GET", "POST"])
    @login_required
    def profile_password():
        """Смена собственного пароля пользователем."""
        profile_form = ProfileForm(obj=current_user)
        password_form = ChangePasswordForm()

        if request.method == "POST" and password_form.validate_on_submit():
            if current_user.password != password_form.old_password.data:
                flash("Текущий пароль указан неверно.", "danger")
            else:
                current_user.password = password_form.new_password.data
                db.session.commit()
                log_action(current_user, "Изменён пароль учётной записи", "user", current_user.id)
                flash("Пароль успешно изменён!", "success")
                return redirect(url_for("profile"))

        return render_template(
            "profile.html",
            profile_form=profile_form,
            password_form=password_form,
        )

    # =========================================================================
    # ДАШБОРД И АНАЛИТИКА CHART.JS (/dashboard)
    # =========================================================================

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """
        Главная панель управления (разный контент по роли) + графики Chart.js.
        """
        if current_user.role == "client":
            orders_query = Order.query.filter_by(client_id=current_user.id)
        else:
            orders_query = Order.query

        # Счётчики заказов по статусам
        status_counts = {
            "waiting": orders_query.filter_by(status="waiting").count(),
            "in_work": orders_query.filter_by(status="in_work").count(),
            "ready": orders_query.filter_by(status="ready").count(),
            "issued": orders_query.filter_by(status="issued").count(),
        }

        # Статистика по последним 6 месяцам (количество заказов и выручка по выданным)
        month_labels = []
        month_orders_data = []
        month_revenue_data = []

        now = datetime.now()
        russian_months = [
            "", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
            "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
        ]

        for i in range(5, -1, -1):
            target_date = now - timedelta(days=i * 30)
            y, m = target_date.year, target_date.month
            month_labels.append(f"{russian_months[m]} {y}")

            # Количество созданных заказов за месяц
            orders_in_month = [
                o for o in orders_query.all()
                if o.created_at and o.created_at.year == y and o.created_at.month == m
            ]
            month_orders_data.append(len(orders_in_month))

            # Выручка за месяц (сумма cost_final по выданным заказам)
            issued_in_month = [
                float(o.cost_final or 0)
                for o in orders_query.filter_by(status="issued").all()
                if (o.issued_at or o.updated_at)
                and (o.issued_at or o.updated_at).year == y
                and (o.issued_at or o.updated_at).month == m
            ]
            month_revenue_data.append(round(sum(issued_in_month), 2))

        # Данные для мастеров и администраторов: склад и автозаявки
        low_stock_parts = []
        top_parts_labels = []
        top_parts_quantities = []

        if current_user.role in ("admin", "master"):
            # Запчасти, где quantity <= min_quantity (блок «Заканчивается на складе / Требуется закупка»)
            low_stock_parts = (
                Part.query.filter(Part.quantity <= Part.min_quantity)
                .order_by(Part.quantity.asc())
                .all()
            )
            # Топ-10 запчастей по остатку для столбчатой диаграммы
            top_parts = Part.query.order_by(Part.quantity.desc()).limit(10).all()
            top_parts_labels = [p.name for p in top_parts]
            top_parts_quantities = [p.quantity for p in top_parts]

        # Дополнительные сводные показатели для администратора
        admin_stats = {}
        recent_logs = []
        if current_user.role == "admin":
            admin_stats = {
                "users_count": User.query.count(),
                "suppliers_count": Supplier.query.count(),
                "active_requests_count": PurchaseRequest.query.filter(
                    PurchaseRequest.status.in_(["new", "approved"])
                ).count(),
            }
            recent_logs = ActionLog.query.order_by(ActionLog.created_at.desc()).limit(10).all()

        # Последние 5 заказов для быстрого доступа
        recent_orders = orders_query.order_by(Order.created_at.desc()).limit(5).all()

        return render_template(
            "dashboard.html",
            status_counts=status_counts,
            month_labels=month_labels,
            month_orders_data=month_orders_data,
            month_revenue_data=month_revenue_data,
            low_stock_parts=low_stock_parts,
            top_parts_labels=top_parts_labels,
            top_parts_quantities=top_parts_quantities,
            admin_stats=admin_stats,
            recent_logs=recent_logs,
            recent_orders=recent_orders,
        )

    # =========================================================================
    # ЗАКАЗЫ (/orders)
    # =========================================================================

    def _build_filtered_orders_query():
        """Вспомогательная функция фильтрации заказов (используется в списке и в CSV-экспорте)."""
        query = Order.query.join(User, Order.client_id == User.id)

        # Клиент видит ТОЛЬКО свои заказы
        if current_user.role == "client":
            query = query.filter(Order.client_id == current_user.id)

        status = request.args.get("status", "").strip()
        priority = request.args.get("priority", "").strip()
        search = request.args.get("search", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        if status:
            query = query.filter(Order.status == status)
        if priority:
            query = query.filter(Order.priority == priority)
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Order.device.ilike(like_pattern),
                    Order.description.ilike(like_pattern),
                    User.full_name.ilike(like_pattern),
                )
            )
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(Order.created_at >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(Order.created_at < dt_to)
            except ValueError:
                pass

        return query.order_by(Order.created_at.desc())

    @app.route("/orders")
    @login_required
    def orders_list():
        """Список заказов с поиском, фильтрами и пагинацией."""
        page = request.args.get("page", 1, type=int)
        query = _build_filtered_orders_query()
        pagination = query.paginate(page=page, per_page=Config.PAGE_SIZE, error_out=False)
        return render_template("orders/list.html", orders=pagination.items, pagination=pagination)

    @app.route("/orders/export")
    @login_required
    @role_required("admin")
    def orders_export():
        """Экспорт отфильтрованных заказов в CSV (только для администратора)."""
        orders = _build_filtered_orders_query().all()
        csv_bytes = export_orders_to_csv(orders)
        log_action(current_user, f"Экспорт заказов в CSV ({len(orders)} зап.)", "order", None)

        filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/orders/create", methods=["GET", "POST"])
    @login_required
    def orders_create():
        """Создание заказа. Клиент создаёт на себя; мастер/админ могут выбрать клиента."""
        form = OrderCreateForm()
        clients = User.query.filter_by(role="client").order_by(User.full_name).all()
        form.client_id.choices = [(c.id, f"{c.full_name} ({c.phone})") for c in clients]

        if form.validate_on_submit():
            if current_user.role == "client":
                target_client_id = current_user.id
                preliminary_cost = 0
            else:
                target_client_id = form.client_id.data or current_user.id
                preliminary_cost = form.cost_preliminary.data or 0

            now = datetime.now()
            order = Order(
                client_id=target_client_id,
                master_id=current_user.id if current_user.role == "master" else None,
                device=form.device.data.strip(),
                description=form.description.data.strip(),
                status="waiting",
                priority=form.priority.data,
                cost_preliminary=preliminary_cost,
                cost_final=0,
                warranty_days=0,
                created_at=now,
                updated_at=now,
                accepted_at=now,
            )
            db.session.add(order)
            db.session.commit()

            log_action(current_user, f"Создан заказ #{order.id} ({order.device})", "order", order.id)
            flash(f"Заказ #{order.id} успешно создан и принят в ожидание!", "success")
            return redirect(url_for("orders_detail", order_id=order.id))

        return render_template("orders/form.html", form=form, is_edit=False)

    @app.route("/orders/<int:order_id>")
    @login_required
    def orders_detail(order_id):
        """Детальная карточка заказа, привязанные запчасти и история комментариев."""
        order = Order.query.get_or_404(order_id)
        if current_user.role == "client" and order.client_id != current_user.id:
            flash("Вы можете просматривать только свои заказы.", "danger")
            abort(403)

        status_form = OrderStatusForm(
            status=order.status,
            cost_final=order.cost_final,
            warranty_days=order.warranty_days,
        )
        add_part_form = OrderAddPartForm()
        all_parts = Part.query.order_by(Part.name).all()
        add_part_form.part_id.choices = [
            (p.id, f"{p.name} [арт. {p.article}] — на складе: {p.quantity} шт. ({p.price} ₽)")
            for p in all_parts
        ]
        comment_form = OrderCommentForm()

        return render_template(
            "orders/detail.html",
            order=order,
            status_form=status_form,
            add_part_form=add_part_form,
            comment_form=comment_form,
        )

    @app.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin", "master")
    def orders_edit(order_id):
        """Редактирование заказа: админ редактирует все поля, мастер — статус и стоимость."""
        order = Order.query.get_or_404(order_id)
        form = OrderEditForm(obj=order)

        clients = User.query.filter_by(role="client").order_by(User.full_name).all()
        masters = User.query.filter(User.role.in_(["master", "admin"])).order_by(User.full_name).all()
        form.client_id.choices = [(c.id, f"{c.full_name} ({c.phone})") for c in clients]
        form.master_id.choices = [(0, "— Не назначен —")] + [
            (m.id, f"{m.full_name} ({m.username})") for m in masters
        ]

        if request.method == "GET":
            form.master_id.data = order.master_id or 0

        if form.validate_on_submit():
            old_status = order.status
            new_status = form.status.data

            # Если статус меняется на 'ready', выполняем списание запчастей
            if new_status == "ready" and old_status != "ready":
                if not write_off_parts(order, current_user):
                    return redirect(url_for("orders_edit", order_id=order.id))

            if current_user.role == "admin":
                order.client_id = form.client_id.data
                order.master_id = form.master_id.data if form.master_id.data != 0 else None
                order.device = form.device.data.strip()
                order.description = form.description.data.strip()
                order.priority = form.priority.data
                order.cost_preliminary = form.cost_preliminary.data or 0

            order.status = new_status
            order.cost_final = form.cost_final.data or 0
            order.warranty_days = form.warranty_days.data or 0
            order.updated_at = datetime.now()

            if new_status == "issued" and not order.issued_at:
                order.issued_at = datetime.now()

            db.session.commit()
            log_action(current_user, f"Отредактирован заказ #{order.id}", "order", order.id)
            flash(f"Заказ #{order.id} успешно обновлён.", "success")
            return redirect(url_for("orders_detail", order_id=order.id))

        return render_template("orders/form.html", form=form, order=order, is_edit=True)

    @app.route("/orders/<int:order_id>/status", methods=["POST"])
    @login_required
    @role_required("admin", "master")
    def orders_change_status(order_id):
        """
        Смена статуса заказа мастером или администратором.
        При переходе в 'ready' автоматически вызывается write_off_parts().
        """
        order = Order.query.get_or_404(order_id)
        form = OrderStatusForm()

        if form.validate_on_submit():
            old_status = order.status
            new_status = form.status.data

            # Если мастер берёт заказ в работу — назначаем его исполнителем
            if new_status == "in_work" and not order.master_id and current_user.role == "master":
                order.master_id = current_user.id

            # При переводе в статус «Готов» списываем не списанные запчасти
            if new_status == "ready" and old_status != "ready":
                if not write_off_parts(order, current_user):
                    return redirect(url_for("orders_detail", order_id=order.id))

            order.status = new_status
            if form.cost_final.data is not None:
                order.cost_final = form.cost_final.data
            if form.warranty_days.data is not None:
                order.warranty_days = form.warranty_days.data
            order.updated_at = datetime.now()

            if new_status == "issued":
                order.issued_at = datetime.now()

            db.session.commit()
            log_action(
                current_user,
                f"Изменён статус заказа #{order.id}: {old_status} -> {new_status}",
                "order",
                order.id,
            )
            flash(f"Статус заказа #{order.id} успешно изменён.", "success")
        else:
            flash("Проверьте корректность введённых данных стоимости и гарантии.", "danger")

        return redirect(url_for("orders_detail", order_id=order.id))

    @app.route("/orders/<int:order_id>/add_part", methods=["POST"])
    @login_required
    @role_required("admin", "master")
    def orders_add_part(order_id):
        """Привязка запчасти со склада к заказу (списание произойдёт при статусе 'ready')."""
        order = Order.query.get_or_404(order_id)
        part_id = request.form.get("part_id", type=int)
        quantity = request.form.get("quantity", 1, type=int)

        if not part_id or quantity <= 0:
            flash("Укажите корректную запчасть и положительное количество.", "danger")
            return redirect(url_for("orders_detail", order_id=order.id))

        part = Part.query.get_or_404(part_id)
        order_part = OrderPart(
            order_id=order.id,
            part_id=part.id,
            quantity=quantity,
            written_off=False,
        )
        db.session.add(order_part)
        db.session.commit()

        log_action(
            current_user,
            f"К заказу #{order.id} добавлена запчасть '{part.name}' ({quantity} шт.)",
            "order",
            order.id,
        )
        flash(f"Запчасть «{part.name}» ({quantity} шт.) привязана к заказу.", "success")
        return redirect(url_for("orders_detail", order_id=order.id))

    @app.route("/orders/<int:order_id>/remove_part/<int:op_id>", methods=["POST"])
    @login_required
    @role_required("admin", "master")
    def orders_remove_part(order_id, op_id):
        """Удаление привязанной запчасти из заказа (если она ещё не была списана)."""
        order = Order.query.get_or_404(order_id)
        order_part = OrderPart.query.filter_by(id=op_id, order_id=order.id).first_or_404()

        if order_part.written_off:
            flash("Нельзя удалить запчасть, которая уже была списана со склада.", "warning")
            return redirect(url_for("orders_detail", order_id=order.id))

        part_name = order_part.part.name if order_part.part else f"ID {order_part.part_id}"
        db.session.delete(order_part)
        db.session.commit()

        log_action(
            current_user,
            f"Из заказа #{order.id} удалена запчасть '{part_name}'",
            "order",
            order.id,
        )
        flash(f"Запчасть «{part_name}» убрана из заказа.", "info")
        return redirect(url_for("orders_detail", order_id=order.id))

    @app.route("/orders/<int:order_id>/comment", methods=["POST"])
    @login_required
    def orders_add_comment(order_id):
        """Добавление комментария к заказу (мастер, админ или клиент своего заказа)."""
        order = Order.query.get_or_404(order_id)
        if current_user.role == "client" and order.client_id != current_user.id:
            abort(403)

        form = OrderCommentForm()
        if form.validate_on_submit():
            comment = OrderComment(
                order_id=order.id,
                user_id=current_user.id,
                text=form.text.data.strip(),
                created_at=datetime.now(),
            )
            db.session.add(comment)
            db.session.commit()

            log_action(
                current_user,
                f"Добавлен комментарий к заказу #{order.id}",
                "order",
                order.id,
            )
            flash("Комментарий добавлен.", "success")
        else:
            flash("Текст комментария не может быть пустым.", "danger")

        return redirect(url_for("orders_detail", order_id=order.id))

    @app.route("/orders/<int:order_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def orders_delete(order_id):
        """Удаление заказа (только администратор, через POST с подтверждением)."""
        order = Order.query.get_or_404(order_id)
        device_name = order.device
        db.session.delete(order)
        db.session.commit()

        log_action(current_user, f"Удалён заказ #{order_id} ({device_name})", "order", order_id)
        flash(f"Заказ #{order_id} удалён.", "info")
        return redirect(url_for("orders_list"))

    # =========================================================================
    # СКЛАД ЗАПЧАСТЕЙ И КАТЕГОРИИ (/parts)
    # =========================================================================

    @app.route("/parts")
    @login_required
    @role_required("admin", "master")
    def parts_list():
        """Список запчастей на складе с поиском по названию/артикулу и фильтром категории."""
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "").strip()
        category_id = request.args.get("category", type=int)

        query = Part.query
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(Part.name.ilike(like_pattern), Part.article.ilike(like_pattern))
            )
        if category_id:
            query = query.filter(Part.category_id == category_id)

        pagination = query.order_by(Part.name.asc()).paginate(
            page=page, per_page=Config.PAGE_SIZE, error_out=False
        )
        categories = PartCategory.query.order_by(PartCategory.name.asc()).all()

        return render_template(
            "parts/list.html",
            parts=pagination.items,
            pagination=pagination,
            categories=categories,
        )

    @app.route("/parts/create", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def parts_create():
        """Добавление новой запчасти на склад (только admin)."""
        form = PartForm()
        categories = PartCategory.query.order_by(PartCategory.name).all()
        form.category_id.choices = [(0, "— Без категории —")] + [
            (c.id, c.name) for c in categories
        ]

        if form.validate_on_submit():
            part = Part(
                name=form.name.data.strip(),
                article=form.article.data.strip(),
                category_id=form.category_id.data if form.category_id.data != 0 else None,
                quantity=form.quantity.data or 0,
                min_quantity=form.min_quantity.data or 0,
                price=form.price.data or 0,
            )
            db.session.add(part)
            db.session.flush()

            # Если начальный остаток больше 0, фиксируем первичный приход на склад
            if part.quantity > 0:
                movement = StockMovement(
                    part_id=part.id,
                    user_id=current_user.id,
                    type="income",
                    quantity=part.quantity,
                    comment="Начальный остаток при создании карточки запчасти",
                )
                db.session.add(movement)

            db.session.commit()
            log_action(
                current_user,
                f"Создана запчасть '{part.name}' (арт. {part.article})",
                "part",
                part.id,
            )
            flash(f"Запчасть «{part.name}» добавлена на склад.", "success")
            return redirect(url_for("parts_list"))

        return render_template("parts/form.html", form=form, is_edit=False)

    @app.route("/parts/<int:part_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def parts_edit(part_id):
        """Редактирование запчасти и корректировка остатка (только admin)."""
        part = Part.query.get_or_404(part_id)
        form = PartForm(original_article=part.article, obj=part)
        categories = PartCategory.query.order_by(PartCategory.name).all()
        form.category_id.choices = [(0, "— Без категории —")] + [
            (c.id, c.name) for c in categories
        ]

        if request.method == "GET":
            form.category_id.data = part.category_id or 0

        if form.validate_on_submit():
            old_qty = part.quantity
            new_qty = form.quantity.data or 0
            diff = new_qty - old_qty

            part.name = form.name.data.strip()
            part.article = form.article.data.strip()
            part.category_id = form.category_id.data if form.category_id.data != 0 else None
            part.quantity = new_qty
            part.min_quantity = form.min_quantity.data or 0
            part.price = form.price.data or 0

            if diff != 0:
                movement = StockMovement(
                    part_id=part.id,
                    user_id=current_user.id,
                    type="adjustment",
                    quantity=diff,
                    comment=f"Ручная корректировка остатка ({old_qty} -> {new_qty})",
                )
                db.session.add(movement)

            db.session.commit()
            log_action(current_user, f"Обновлена запчасть '{part.name}'", "part", part.id)
            flash(f"Данные запчасти «{part.name}» сохранены.", "success")
            return redirect(url_for("parts_list"))

        return render_template("parts/form.html", form=form, part=part, is_edit=True)

    @app.route("/parts/<int:part_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def parts_delete(part_id):
        """Удаление запчасти со склада (только admin)."""
        part = Part.query.get_or_404(part_id)
        if part.order_usages:
            flash(
                "Нельзя удалить запчасть, так как она используется в заказах.",
                "danger",
            )
            return redirect(url_for("parts_list"))

        name = part.name
        db.session.delete(part)
        db.session.commit()
        log_action(current_user, f"Удалена запчасть '{name}'", "part", part_id)
        flash(f"Запчасть «{name}» удалена.", "info")
        return redirect(url_for("parts_list"))

    @app.route("/parts/<int:part_id>/history")
    @login_required
    @role_required("admin", "master")
    def parts_history(part_id):
        """История движения конкретной запчасти (StockMovement)."""
        part = Part.query.get_or_404(part_id)
        page = request.args.get("page", 1, type=int)
        pagination = (
            StockMovement.query.filter_by(part_id=part.id)
            .order_by(StockMovement.created_at.desc())
            .paginate(page=page, per_page=Config.PAGE_SIZE, error_out=False)
        )
        return render_template(
            "parts/history.html",
            part=part,
            movements=pagination.items,
            pagination=pagination,
        )

    @app.route("/parts/categories", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def parts_categories():
        """CRUD категорий запчастей (только admin)."""
        form = CategoryForm()
        if form.validate_on_submit():
            category = PartCategory(name=form.name.data.strip())
            db.session.add(category)
            db.session.commit()
            log_action(
                current_user,
                f"Создана категория запчастей '{category.name}'",
                "category",
                category.id,
            )
            flash(f"Категория «{category.name}» добавлена.", "success")
            return redirect(url_for("parts_categories"))

        categories = PartCategory.query.order_by(PartCategory.name.asc()).all()
        return render_template("parts/categories.html", form=form, categories=categories)

    @app.route("/parts/categories/<int:cat_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def parts_categories_delete(cat_id):
        """Удаление категории запчастей."""
        category = PartCategory.query.get_or_404(cat_id)
        name = category.name
        db.session.delete(category)
        db.session.commit()
        log_action(current_user, f"Удалена категория запчастей '{name}'", "category", cat_id)
        flash(f"Категория «{name}» удалена.", "info")
        return redirect(url_for("parts_categories"))

    # =========================================================================
    # ПОСТАВЩИКИ (/suppliers)
    # =========================================================================

    @app.route("/suppliers")
    @login_required
    @role_required("admin", "master")
    def suppliers_list():
        """Список поставщиков с поиском по названию и контактному лицу."""
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "").strip()

        query = Supplier.query
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Supplier.name.ilike(like_pattern),
                    Supplier.contact_person.ilike(like_pattern),
                )
            )

        pagination = query.order_by(Supplier.name.asc()).paginate(
            page=page, per_page=Config.PAGE_SIZE, error_out=False
        )
        return render_template(
            "suppliers/list.html",
            suppliers=pagination.items,
            pagination=pagination,
        )

    @app.route("/suppliers/create", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def suppliers_create():
        """Добавление поставщика (только admin)."""
        form = SupplierForm()
        if form.validate_on_submit():
            supplier = Supplier(
                name=form.name.data.strip(),
                contact_person=form.contact_person.data.strip(),
                phone=form.phone.data.strip(),
                email=form.email.data.strip() if form.email.data else None,
                address=form.address.data.strip() if form.address.data else None,
            )
            db.session.add(supplier)
            db.session.commit()

            log_action(
                current_user,
                f"Добавлен поставщик '{supplier.name}'",
                "supplier",
                supplier.id,
            )
            flash(f"Поставщик «{supplier.name}» успешно добавлен.", "success")
            return redirect(url_for("suppliers_list"))

        return render_template("suppliers/form.html", form=form, is_edit=False)

    @app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def suppliers_edit(supplier_id):
        """Редактирование поставщика (только admin)."""
        supplier = Supplier.query.get_or_404(supplier_id)
        form = SupplierForm(original_name=supplier.name, obj=supplier)

        if form.validate_on_submit():
            supplier.name = form.name.data.strip()
            supplier.contact_person = form.contact_person.data.strip()
            supplier.phone = form.phone.data.strip()
            supplier.email = form.email.data.strip() if form.email.data else None
            supplier.address = form.address.data.strip() if form.address.data else None
            db.session.commit()

            log_action(
                current_user,
                f"Обновлён поставщик '{supplier.name}'",
                "supplier",
                supplier.id,
            )
            flash(f"Данные поставщика «{supplier.name}» обновлены.", "success")
            return redirect(url_for("suppliers_list"))

        return render_template("suppliers/form.html", form=form, supplier=supplier, is_edit=True)

    @app.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def suppliers_delete(supplier_id):
        """Удаление поставщика (только admin)."""
        supplier = Supplier.query.get_or_404(supplier_id)
        name = supplier.name
        db.session.delete(supplier)
        db.session.commit()

        log_action(current_user, f"Удалён поставщик '{name}'", "supplier", supplier_id)
        flash(f"Поставщик «{name}» удалён.", "info")
        return redirect(url_for("suppliers_list"))

    # =========================================================================
    # ЗАЯВКИ НА ЗАКУПКУ (/purchase_requests)
    # =========================================================================

    @app.route("/purchase_requests")
    @login_required
    @role_required("admin", "master")
    def purchase_requests_list():
        """Список заявок на закупку (admin видит все, master — свои)."""
        page = request.args.get("page", 1, type=int)
        status = request.args.get("status", "").strip()

        query = PurchaseRequest.query
        if current_user.role == "master":
            query = query.filter_by(created_by=current_user.id)
        if status:
            query = query.filter_by(status=status)

        pagination = query.order_by(PurchaseRequest.created_at.desc()).paginate(
            page=page, per_page=Config.PAGE_SIZE, error_out=False
        )
        return render_template(
            "purchase_requests/list.html",
            requests=pagination.items,
            pagination=pagination,
        )

    @app.route("/purchase_requests/create", methods=["GET", "POST"])
    @login_required
    @role_required("admin", "master")
    def purchase_requests_create():
        """Создание заявки на закупку. Поддерживает предзаполнение ?part_id=N."""
        form = PurchaseRequestForm()
        parts = Part.query.order_by(Part.name).all()
        suppliers = Supplier.query.order_by(Supplier.name).all()

        form.part_id.choices = [
            (p.id, f"{p.name} (арт. {p.article}, остаток: {p.quantity} шт.)") for p in parts
        ]
        form.supplier_id.choices = [(s.id, f"{s.name} ({s.phone})") for s in suppliers]

        if request.method == "GET":
            preselected_part_id = request.args.get("part_id", type=int)
            if preselected_part_id:
                form.part_id.data = preselected_part_id
                selected_part = db.session.get(Part, preselected_part_id)
                if selected_part:
                    form.price.data = selected_part.price

        if form.validate_on_submit():
            pr = PurchaseRequest(
                part_id=form.part_id.data,
                supplier_id=form.supplier_id.data,
                quantity=form.quantity.data,
                price=form.price.data,
                status="new",
                created_by=current_user.id,
                created_at=datetime.now(),
            )
            db.session.add(pr)
            db.session.commit()

            log_action(
                current_user,
                f"Создана заявка на закупку #{pr.id} ({pr.part.name}, {pr.quantity} шт.)",
                "purchase_request",
                pr.id,
            )
            flash(f"Заявка на закупку #{pr.id} успешно создана.", "success")
            return redirect(url_for("purchase_requests_list"))

        return render_template("purchase_requests/form.html", form=form, is_edit=False)

    @app.route("/purchase_requests/<int:req_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def purchase_requests_edit(req_id):
        """Редактирование заявки на закупку (только admin)."""
        pr = PurchaseRequest.query.get_or_404(req_id)
        form = PurchaseRequestForm(obj=pr)
        parts = Part.query.order_by(Part.name).all()
        suppliers = Supplier.query.order_by(Supplier.name).all()

        form.part_id.choices = [(p.id, f"{p.name} ({p.article})") for p in parts]
        form.supplier_id.choices = [(s.id, s.name) for s in suppliers]

        if form.validate_on_submit():
            pr.part_id = form.part_id.data
            pr.supplier_id = form.supplier_id.data
            pr.quantity = form.quantity.data
            pr.price = form.price.data
            db.session.commit()

            log_action(
                current_user,
                f"Отредактирована заявка на закупку #{pr.id}",
                "purchase_request",
                pr.id,
            )
            flash(f"Заявка #{pr.id} обновлена.", "success")
            return redirect(url_for("purchase_requests_list"))

        return render_template("purchase_requests/form.html", form=form, pr=pr, is_edit=True)

    @app.route("/purchase_requests/<int:req_id>/status", methods=["POST"])
    @login_required
    @role_required("admin")
    def purchase_requests_status(req_id):
        """
        Смена статуса заявки на закупку (new -> approved -> received).
        При переводе в статус 'received' («Получена») остаток запчасти увеличивается,
        и создаётся запись StockMovement(type='income').
        """
        pr = PurchaseRequest.query.get_or_404(req_id)
        new_status = request.form.get("status", "").strip()

        if new_status not in ("new", "approved", "received"):
            flash("Некорректный статус заявки.", "danger")
            return redirect(url_for("purchase_requests_list"))

        old_status = pr.status
        if old_status == "received":
            flash("Заявка уже получена и оприходована на склад.", "warning")
            return redirect(url_for("purchase_requests_list"))

        pr.status = new_status

        if new_status == "received":
            part = pr.part
            part.quantity += pr.quantity
            movement = StockMovement(
                part_id=part.id,
                user_id=current_user.id,
                type="income",
                quantity=pr.quantity,
                comment=f"Закупка у {pr.supplier.name} (заявка #{pr.id})",
                created_at=datetime.now(),
            )
            db.session.add(movement)
            log_action(
                current_user,
                f"Пополнение склада по заявке #{pr.id}: {part.name} +{pr.quantity} шт. от {pr.supplier.name}",
                "purchase_request",
                pr.id,
                commit=False,
            )

        db.session.commit()
        log_action(
            current_user,
            f"Статус заявки на закупку #{pr.id} изменён: {old_status} -> {new_status}",
            "purchase_request",
            pr.id,
        )
        flash(f"Статус заявки #{pr.id} обновлён на «{new_status}».", "success")
        return redirect(url_for("purchase_requests_list"))

    @app.route("/purchase_requests/<int:req_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def purchase_requests_delete(req_id):
        """Удаление заявки на закупку (только admin)."""
        pr = PurchaseRequest.query.get_or_404(req_id)
        db.session.delete(pr)
        db.session.commit()

        log_action(current_user, f"Удалена заявка на закупку #{req_id}", "purchase_request", req_id)
        flash(f"Заявка #{req_id} удалена.", "info")
        return redirect(url_for("purchase_requests_list"))

    # =========================================================================
    # ПОЛЬЗОВАТЕЛИ И ЖУРНАЛ ДЕЙСТВИЙ (/users, /logs) — ТОЛЬКО ADMIN
    # =========================================================================

    @app.route("/users")
    @login_required
    @role_required("admin")
    def users_list():
        """Список пользователей с поиском по username и full_name."""
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "").strip()

        query = User.query
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(User.username.ilike(like_pattern), User.full_name.ilike(like_pattern))
            )

        pagination = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=Config.PAGE_SIZE, error_out=False
        )
        return render_template("users/list.html", users=pagination.items, pagination=pagination)

    @app.route("/users/<int:user_id>/role", methods=["POST"])
    @login_required
    @role_required("admin")
    def users_change_role(user_id):
        """Смена роли пользователя администратором (admin / master / client)."""
        user = User.query.get_or_404(user_id)
        new_role = request.form.get("role", "").strip()

        if new_role not in ("admin", "master", "client"):
            flash("Указана некорректная роль.", "danger")
            return redirect(url_for("users_list"))

        old_role = user.role
        user.role = new_role
        db.session.commit()

        log_action(
            current_user,
            f"Изменена роль пользователя {user.username}: {old_role} -> {new_role}",
            "user",
            user.id,
        )
        flash(f"Роль пользователя {user.full_name} изменена на «{new_role}».", "success")
        return redirect(url_for("users_list"))

    @app.route("/users/<int:user_id>/block", methods=["POST"])
    @login_required
    @role_required("admin")
    def users_toggle_block(user_id):
        """Блока / разблокировка пользователя администратором."""
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash("Вы не можете заблокировать собственную учётную запись.", "warning")
            return redirect(url_for("users_list"))

        user.is_blocked = not user.is_blocked
        db.session.commit()

        status_text = "заблокирован" if user.is_blocked else "разблокирован"
        log_action(
            current_user,
            f"Пользователь {user.username} {status_text}",
            "user",
            user.id,
        )
        flash(f"Пользователь {user.full_name} {status_text}.", "info")
        return redirect(url_for("users_list"))

    @app.route("/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def users_delete(user_id):
        """Удаление пользователя (с подтверждением в модальном окне)."""
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash("Нельзя удалить собственную учётную запись.", "danger")
            return redirect(url_for("users_list"))

        username = user.username
        db.session.delete(user)
        db.session.commit()

        log_action(current_user, f"Удалён пользователь {username}", "user", user_id)
        flash(f"Пользователь {username} удалён.", "info")
        return redirect(url_for("users_list"))

    @app.route("/logs")
    @login_required
    @role_required("admin")
    def action_logs():
        """Просмотр журнала действий всех пользователей (ActionLog)."""
        page = request.args.get("page", 1, type=int)
        pagination = ActionLog.query.order_by(ActionLog.created_at.desc()).paginate(
            page=page, per_page=Config.PAGE_SIZE, error_out=False
        )
        return render_template("users/logs.html", logs=pagination.items, pagination=pagination)
