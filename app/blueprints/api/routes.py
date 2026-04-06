# API-маршруты — будут реализованы в Спринте 5

from flask import jsonify
from app.blueprints.api import api_bp


@api_bp.route('/health')
def health():
    """Проверка работоспособности API"""
    return jsonify({'status': 'ok'})