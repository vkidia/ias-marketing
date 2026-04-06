# модуль управления кампаниями

from flask import Blueprint

campaigns_bp = Blueprint('campaigns', __name__, template_folder='templates')

from app.blueprints.campaigns import routes  # noqa: F401, E402