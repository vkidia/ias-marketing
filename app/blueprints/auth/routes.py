# Маршруты авторизации — будут реализованы в Спринте 1

from app.blueprints.auth import auth_bp


@auth_bp.route('/login')
def login():
    return 'Страница входа — будет в Спринте 1'


@auth_bp.route('/logout')
def logout():
    return 'Выход — будет в Спринте 1'