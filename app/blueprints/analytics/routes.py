# маршруты аналитики — будут реализованы в Спринте 4

from app.blueprints.analytics import analytics_bp


@analytics_bp.route('/')
def index():
    return 'Аналитика — будет в Спринте 4'