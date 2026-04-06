# модуль аналитики и экспорта

from flask import Blueprint

analytics_bp = Blueprint('analytics', __name__, template_folder='templates')

from app.blueprints.analytics import routes  # noqa: F401, E402