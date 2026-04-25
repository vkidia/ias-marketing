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

    # взвешенный ROI: суммарная выручка минус суммарные расходы / расходы
    total_spent = total_revenue = 0.0
    roi_by_id = {}
    for c in all_campaigns:
        spent   = float(c.spent or 0)
        revenue = float(c.revenue or 0)
        total_spent   += spent
        total_revenue += revenue
        if spent:
            roi_by_id[c.id] = round((revenue - spent) / spent * 100, 1)
    avg_roi = round((total_revenue - total_spent) / total_spent * 100, 1) if total_spent else None

    global_cr = round(converted / total_leads * 100, 1) if total_leads else None
    campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)

    dss = compute_dss(
        mode='all',
        funnel=funnel,
        total_leads=total_leads,
        roi=avg_roi,
        cr=global_cr,
        active_count=active_campaigns,
        campaign_count=len(all_campaigns),
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
