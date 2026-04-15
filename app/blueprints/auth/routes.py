from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, RegisterForm
from app.extensions import db
from app.models.user import User


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            db.select(User).where(User.username == form.username.data)
        )
        if user and user.check_password(form.password.data):
            if not user.is_approved:
                flash('Ваш аккаунт ещё не одобрен администратором.', 'warning')
                return redirect(url_for('auth.login'))
            if not user.is_active:
                flash('Ваш аккаунт деактивирован. Обратитесь к администратору.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        flash('Неверный логин или пароль.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        # первый пользователь в системе автоматически получает роль admin
        user_count = db.session.scalar(db.select(db.func.count(User.id))) or 0
        is_first_user = (user_count == 0)
        role = 'admin' if is_first_user else 'viewer'
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            role=role,
            is_active=is_first_user,
            is_approved=is_first_user,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        if is_first_user:
            flash('Аккаунт создан! Вы первый — вам присвоена роль admin.', 'success')
        else:
            flash(
                'Заявка отправлена. Войти можно будет после того, как администратор одобрит аккаунт.',
                'info'
            )
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)