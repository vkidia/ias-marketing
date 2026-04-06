# главная страница и дашборд

from flask import render_template
from app.blueprints.main import main_bp


@main_bp.route('/')
def index():
    """Главная страница — редирект на дашборд"""
    return render_template('main/dashboard.html')


@main_bp.route('/dashboard')
def dashboard():
    """Дашборд — главная страница после входа"""
    return render_template('main/dashboard.html')