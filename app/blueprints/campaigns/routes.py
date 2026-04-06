# маршруты кампаний — будут реализованы в Спринте 2

from app.blueprints.campaigns import campaigns_bp


@campaigns_bp.route('/')
def index():
    return 'Список кампаний — будет в Спринте 2'