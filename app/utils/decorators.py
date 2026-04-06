# декораторы для проверки прав доступа

from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    """
    Декоратор: разрешает доступ только пользователям с указанными ролями.

    Пример использования:
        @role_required('admin', 'marketing')
        def create_campaign():
            ...  # сюда попадут только admin и marketing
    """
    def decorator(f):
        @wraps(f)  # сохраняем имя оригинальной функции (для отладки)
        def decorated_function(*args, **kwargs):
            # Если пользователь не авторизован — 401 Unauthorized
            if not current_user.is_authenticated:
                abort(401)
            # Если роль не подходит — 403 Forbidden
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator