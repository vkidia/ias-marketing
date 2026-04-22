"""
test_auth.py — тесты аутентификации:
  - вход с правильным паролем
  - вход с неправильным паролем
  - вход с неодобренным аккаунтом
  - доступ к защищённым страницам без авторизации
  - выход из системы
"""
import pytest
from app.models.user import User
from app.extensions import db


class TestLogin:
    def test_login_correct_password(self, client, admin_user):
        """Правильные логин/пароль → редирект на dashboard (302)."""
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/auth/login' not in response.headers.get('Location', '')

    def test_login_wrong_password(self, client, admin_user):
        """Неправильный пароль → остаёмся на странице входа (200)."""
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'wrongpassword',
        })
        assert response.status_code == 200
        assert 'Неверный логин или пароль' in response.get_data(as_text=True)

    def test_login_unapproved_user(self, client, db):
        """Пользователь без одобрения администратора не может войти."""
        user = User(
            username='pending',
            email='pending@test.com',
            full_name='Pending User',
            role='viewer',
            is_active=False,
            is_approved=False,
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

        response = client.post('/auth/login', data={
            'username': 'pending',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/auth/login' in response.headers.get('Location', '')


class TestProtectedAccess:
    def test_access_without_auth_redirects_to_login(self, client):
        """Запрос к защищённой странице без авторизации → редирект на /auth/login."""
        response = client.get('/leads/')
        assert response.status_code == 302
        assert '/auth/login' in response.headers.get('Location', '')

    def test_logout(self, logged_in_client):
        """После выхода доступ к защищённым страницам перекрыт."""
        logout_response = logged_in_client.get('/auth/logout')
        assert logout_response.status_code == 302

        protected_response = logged_in_client.get('/leads/')
        assert protected_response.status_code == 302
        assert '/auth/login' in protected_response.headers.get('Location', '')
