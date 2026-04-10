from flask import jsonify, request

from app.blueprints.api import api_bp
from app.extensions import db
from app.models.campaign import Campaign
from app.models.landing import LandingPage
from app.models.lead import Lead, LEAD_SOURCES
from app.utils.scoring import update_lead_score


@api_bp.route('/health')
def health():
    """Проверка работоспособности API"""
    return jsonify({'status': 'ok'})


@api_bp.route('/campaigns')
def campaigns():
    """Список активных кампаний (для внешних систем)."""
    rows = db.session.scalars(
        db.select(Campaign)
        .where(Campaign.status == 'active')
        .order_by(Campaign.name)
    ).all()
    return jsonify([
        {
            'id':           c.id,
            'name':         c.name,
            'channel':      c.channel,
            'utm_source':   c.utm_source,
            'utm_medium':   c.utm_medium,
            'utm_campaign': c.utm_campaign,
        }
        for c in rows
    ])


@api_bp.route('/leads', methods=['POST'])
def create_lead():
    """
    Принять лид из внешней формы (лендинга или CRM-интеграции).

    Обязательные поля: first_name, email
    Опциональные: last_name, phone, company, position, city, inn,
                  client_type, utm_source, utm_medium, utm_campaign,
                  landing_slug (для привязки к кампании)

    Возвращает: {id, score, status}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Ожидается JSON'}), 400

    first_name = (data.get('first_name') or '').strip()
    email      = (data.get('email')      or '').strip().lower()

    if not first_name:
        return jsonify({'ok': False, 'error': 'Поле first_name обязательно'}), 422
    if not email or '@' not in email:
        return jsonify({'ok': False, 'error': 'Некорректный email'}), 422

    # определить campaign_id через landing_slug
    campaign_id = None
    landing_slug = (data.get('landing_slug') or '').strip()
    if landing_slug:
        lp = db.session.scalars(
            db.select(LandingPage).where(LandingPage.slug == landing_slug)
        ).first()
        if lp:
            campaign_id = lp.campaign_id

    client_type = (data.get('client_type') or 'b2b').lower().strip()
    if client_type not in ('b2b', 'b2g'):
        client_type = 'b2b'

    lead = Lead(
        first_name   = first_name,
        last_name    = (data.get('last_name')  or '').strip() or None,
        email        = email,
        phone        = (data.get('phone')      or '').strip() or None,
        company      = (data.get('company')    or '').strip() or None,
        position     = (data.get('position')   or '').strip() or None,
        city         = (data.get('city')       or '').strip() or None,
        inn          = (data.get('inn')        or '').strip() or None,
        client_type  = client_type,
        source       = 'landing',
        utm_source   = (data.get('utm_source')   or '').strip() or None,
        utm_medium   = (data.get('utm_medium')   or '').strip() or None,
        utm_campaign = (data.get('utm_campaign') or '').strip() or None,
        campaign_id  = campaign_id,
    )

    db.session.add(lead)
    db.session.flush()          # получаем id до commit, нужен для scoring (lazy campaign)
    update_lead_score(lead)
    db.session.commit()

    return jsonify({'ok': True, 'id': lead.id, 'score': lead.score, 'status': lead.status}), 201
