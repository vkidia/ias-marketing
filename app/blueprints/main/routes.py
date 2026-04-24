from flask import render_template, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from app.blueprints.main import main_bp
from app.extensions import db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.utils.dss import compute_dss, collect_campaign_alerts


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # воронка одним запросом вместо пяти отдельных count-запросов
    funnel_rows = db.session.execute(
        db.select(Lead.status, func.count(Lead.id).label('cnt'))
        .group_by(Lead.status)
    ).all()
    funnel = {r.status: r.cnt for r in funnel_rows}
    # добавляем нулевые значения для статусов у которых нет лидов, чтобы шаблон не падал
    for s in ('new', 'contacted', 'qualified', 'converted', 'lost'):
        funnel.setdefault(s, 0)

    total_leads = sum(funnel.values())
    converted   = funnel['converted']

    active_campaigns = db.session.scalar(
        db.select(func.count(Campaign.id)).where(Campaign.status == 'active')
    ) or 0

    all_campaigns = db.session.scalars(db.select(Campaign)).all()
    # roi считаем через свойство модели, пропускаем кампании без расходов (roi == None)
    roi_by_id = {c.id: c.roi for c in all_campaigns if c.roi is not None}
    roi_values = list(roi_by_id.values())
    avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None

    global_cr = round(converted / total_leads * 100, 1) if total_leads else None
    campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)

    dss = compute_dss(
        funnel=funnel,
        total_leads=total_leads,
        avg_roi=avg_roi,
        active_campaigns=active_campaigns,
        global_cr=global_cr,
        campaign_alerts=campaign_alerts,
    )

    return render_template(
        'main/dashboard.html',
        total_leads=total_leads,
        converted=converted,
        active_campaigns=active_campaigns,
        avg_roi=avg_roi,
        funnel=funnel,
        dss=dss,
    )
