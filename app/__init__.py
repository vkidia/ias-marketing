from flask import Flask
from app.config import config_by_name
from app.extensions import db, migrate, login_manager


def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # импортируем модели ДО регистрации blueprints,
    # чтобы Flask-Migrate их видел
    with app.app_context():
        from app.models import User, Campaign, Lead, LeadHistory, LandingPage  # noqa

    # blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.campaigns import campaigns_bp
    from app.blueprints.leads import leads_bp
    from app.blueprints.analytics import analytics_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(campaigns_bp, url_prefix='/campaigns')
    app.register_blueprint(leads_bp, url_prefix='/leads')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(api_bp, url_prefix='/api')

    # обработчики ошибок
    from app.blueprints.errors import register_error_handlers
    register_error_handlers(app)

    # Flask-Login: загрузка пользователя
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Войдите в систему для доступа к этой странице.'
    login_manager.login_message_category = 'warning'

    return app