# модуль управления лидами

from flask import Blueprint

leads_bp = Blueprint('leads', __name__, template_folder='templates')

from app.blueprints.leads import routes  # noqa: F401, E402