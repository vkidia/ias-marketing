# конфигурации приложения для разных режимов работы.
# create_app() выбирает нужный класс по имени ('development', 'production', 'testing')

import os

class BaseConfig:
    """Базовые настройки — общие для всех режимов"""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    """Режим разработки: DEBUG включён, база данных PostgreSQL"""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://ias_user:ias_password@localhost:5432/ias_marketing'
    )


class ProductionConfig(BaseConfig):
    """Продакшен: DEBUG выключен. DATABASE_URL ОБЯЗАН быть в окружении."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


class TestingConfig(BaseConfig):
    """Тесты: используем SQLite в памяти — быстро и не трогает реальную БД."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
}