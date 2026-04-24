from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.blueprints.admin import admin_bp
from app.extensions import db
from app.models.user import User, ROLES
from app.models.campaign import Campaign
from app.models.lead import Lead, LeadHistory
from app.utils.decorators import role_required


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users():
    # ожидающие одобрения показываются отдельно вверху страницы
    pending_users = db.session.scalars(
        db.select(User)
        .where(User.is_approved == False)
        .order_by(User.created_at.asc())
    ).all()

    # одобренные пользователи сортируются по роли, чтобы admin шёл первым
    all_users = db.session.scalars(
        db.select(User)
        .where(User.is_approved == True)
        .order_by(User.role, User.username)
    ).all()

    return render_template(
        'admin/users.html',
        pending_users=pending_users,
        users=all_users,
        roles=ROLES,
    )


@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@login_required
@role_required('admin')
def approve(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.is_approved:
        flash(f'Пользователь «{user.username}» уже одобрен.', 'warning')
        return redirect(url_for('admin.users'))

    user.is_approved = True
    user.is_active   = True
    db.session.commit()
    flash(f'Пользователь «{user.username}» одобрен и может войти в систему.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reject', methods=['POST'])
@login_required
@role_required('admin')
def reject(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.is_approved:
        flash('Нельзя отклонить уже одобренного пользователя.', 'danger')
        return redirect(url_for('admin.users'))

    # Проверяем что пользователь не успел ничего создать (защита от гонок)
    has_campaigns = db.session.scalar(
        db.select(db.func.count(Campaign.id)).where(Campaign.created_by == user.id)
    ) or 0
    has_leads = db.session.scalar(
        db.select(db.func.count(Lead.id)).where(Lead.assigned_to == user.id)
    ) or 0
    has_history = db.session.scalar(
        db.select(db.func.count(LeadHistory.id)).where(LeadHistory.changed_by == user.id)
    ) or 0

    if has_campaigns or has_leads or has_history:
        flash('Невозможно удалить: у пользователя есть связанные данные.', 'danger')
        return redirect(url_for('admin.users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Заявка пользователя «{username}» отклонена и удалена.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@role_required('admin')
def change_role(user_id):
    user = db.session.get(User, user_id) or abort(404)
    # нельзя сменить роль себе, иначе можно случайно лишить себя прав admin
    if user.id == current_user.id:
        flash('Нельзя изменить собственную роль.', 'warning')
        return redirect(url_for('admin.users'))

    new_role = request.form.get('role', '')
    # проверяем что роль пришла валидная, а не произвольная строка из формы
    if new_role not in ROLES:
        flash('Недопустимая роль.', 'danger')
        return redirect(url_for('admin.users'))

    old_role = user.role
    user.role = new_role
    db.session.commit()
    flash(f'Роль пользователя «{user.username}» изменена: {old_role} → {new_role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def toggle_active(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash('Нельзя деактивировать собственный аккаунт.', 'warning')
        return redirect(url_for('admin.users'))
    if not user.is_approved:
        flash('Нельзя деактивировать неодобренного пользователя. Используйте «Отклонить».', 'warning')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()
    state = 'активирован' if user.is_active else 'деактивирован'
    flash(f'Пользователь «{user.username}» {state}.', 'success')
    return redirect(url_for('admin.users'))
