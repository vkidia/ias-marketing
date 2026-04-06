# Главный модуль: дашборд и главная страница

from flask import Blueprint

# Создаём Blueprint с именем 'main'
# Имя используется в url_for(), например url_for('main.dashboard')
main_bp = Blueprint('main', __name__, template_folder='templates')

# Импортируем маршруты — они автоматически привязываются к main_bp
from app.blueprints.main import routes  # noqa: F401, E402