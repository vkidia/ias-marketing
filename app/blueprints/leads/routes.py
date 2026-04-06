# маршруты лидов — будут реализованы в Спринте 3

from app.blueprints.leads import leads_bp


@leads_bp.route('/')
def index():
    return 'Список лидов — будет в Спринте 3'