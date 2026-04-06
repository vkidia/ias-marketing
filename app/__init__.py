# create_app() — функция-фабрика, которая создаёт и настраивает Flask-приложение.

from flask import Flask, render_template
from app.extensions import db, migrate, login_manager


def create_app(config_name='development'):
    """
    Создаёт и возвращает настроенное Flask-приложение.
    config_name: 'development' | 'production' | 'testing'
    """

    app = Flask(__name__)

    # --- Выбираем конфигурацию по имени ---
    config_map = {
        'development': 'app.config.DevelopmentConfig',
        'production':  'app.config.ProductionConfig',
        'testing':     'app.config.TestingConfig',
        'default':     'app.config.DevelopmentConfig',
    }
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # --- Подключаем расширения к приложению ---
    # init_app() "привязывает" расширение к конкретному app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # --- Регистрируем blueprints (модули приложения) ---
    # Blueprint — это "комната" в приложении со своими маршрутами.
    # url_prefix задаёт начало URL для всех маршрутов модуля.

    from app.blueprints.main import main_bp
    app.register_blueprint(main_bp)  # маршруты: /  /dashboard

    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')  # /auth/login  /auth/logout

    from app.blueprints.campaigns import campaigns_bp
    app.register_blueprint(campaigns_bp, url_prefix='/campaigns')

    from app.blueprints.leads import leads_bp
    app.register_blueprint(leads_bp, url_prefix='/leads')

    from app.blueprints.analytics import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    from app.blueprints.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # --- Обработчики ошибок ---
    # Если страница не найдена — показываем красивую страницу 404
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    # Если доступ запрещён — показываем страницу 403
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    return app