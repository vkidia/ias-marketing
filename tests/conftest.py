import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.campaign import Campaign
from app.models.lead import Lead


@pytest.fixture(scope='session')
def app():
    flask_app = create_app('testing')
    flask_app.config.update({
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool,
        },
    })
    # Временный контекст только для создания таблиц
    with flask_app.app_context():
        _db.create_all()
    yield flask_app
    with flask_app.app_context():
        _db.drop_all()


@pytest.fixture(autouse=True)
def clean_tables(app):
    yield
    with app.app_context():
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(db):
    user = User(
        username='admin',
        email='admin@test.com',
        full_name='Admin User',
        role='admin',
        is_active=True,
        is_approved=True,
    )
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def logged_in_client(client, admin_user):
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'password123',
    })
    return client
