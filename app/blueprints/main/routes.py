# главная страница и дашборд

from flask import render_template, redirect, url_for
from flask_login import login_required
from app.blueprints.main import main_bp

@main_bp.route('/')
def index():
    """Главная страница — редирект на дашборд"""
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required  # ← декоратор ПЕРЕД функцией и ПОСЛЕ route
def dashboard():
    """Дашборд — главная страница после входа"""
    return render_template('main/dashboard.html')