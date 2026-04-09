from flask import render_template, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from app.blueprints.main import main_bp
from app.extensions import db
from app.models.campaign import Campaign
from app.models.lead import Lead


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Воронка одним запросом
    funnel_rows = db.session.execute(
        db.select(Lead.status, func.count(Lead.id).label('cnt'))
        .group_by(Lead.status)
    ).all()
    funnel = {r.status: r.cnt for r in funnel_rows}
    for s in ('new', 'contacted', 'qualified', 'converted', 'lost'):
        funnel.setdefault(s, 0)

    total_leads = sum(funnel.values())
    converted   = funnel['converted']

    active_campaigns = db.session.scalar(
        db.select(func.count(Campaign.id)).where(Campaign.status == 'active')
    ) or 0

    campaigns = db.session.scalars(db.select(Campaign)).all()
    roi_values = [c.roi for c in campaigns if c.roi is not None]
    avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None

    return render_template(
        'main/dashboard.html',
        total_leads=total_leads,
        converted=converted,
        active_campaigns=active_campaigns,
        avg_roi=avg_roi,
        funnel=funnel,
    )
