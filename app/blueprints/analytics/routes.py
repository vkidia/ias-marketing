import datetime

from flask import render_template, send_file
from flask_login import login_required
from sqlalchemy import func

from app.blueprints.analytics import analytics_bp
from app.extensions import db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.utils.decorators import role_required
from app.utils.dss import compute_dss

RU_MONTHS = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
    7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек',
}


def _last_n_months(n=6):
    """Возвращает список datetime.date(y, m, 1) для последних n месяцев."""
    today = datetime.date.today()
    months = []
    for i in range(n - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(datetime.date(y, m, 1))
    return months


@analytics_bp.route('/')
@login_required
def index():
    # ── Воронка (один запрос) ────────────────────────────────────
    funnel_rows = db.session.execute(
        db.select(Lead.status, func.count(Lead.id).label('cnt'))
        .group_by(Lead.status)
    ).all()
    funnel = {r.status: r.cnt for r in funnel_rows}
    for s in ('new', 'contacted', 'qualified', 'converted', 'lost'):
        funnel.setdefault(s, 0)

    total_leads = sum(funnel.values())
    converted   = funnel['converted']

    # ── Кампании ────────────────────────────────────────────────
    active_campaigns = db.session.scalar(
        db.select(func.count(Campaign.id)).where(Campaign.status == 'active')
    ) or 0

    all_campaigns = db.session.scalars(
        db.select(Campaign).order_by(Campaign.created_at.desc())
    ).all()

    roi_values = [c.roi for c in all_campaigns if c.roi is not None]
    avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None

    # ── Глобальные CPL и Conversion Rate ─────────────────────────
    total_spent = sum(float(c.spent or 0) for c in all_campaigns)
    global_cpl = round(total_spent / total_leads) if total_leads else None
    global_cr  = round(converted / total_leads * 100, 1) if total_leads else None

    top_campaigns = sorted(
        [c for c in all_campaigns if c.lead_count > 0],
        key=lambda c: c.conversion_rate,
        reverse=True,
    )[:5]

    # ── Динамика лидов за 6 месяцев ─────────────────────────────
    months_range = _last_n_months(6)
    start_dt = datetime.datetime(months_range[0].year, months_range[0].month, 1)

    monthly_raw = db.session.execute(
        db.select(
            func.date_trunc('month', Lead.created_at).label('month'),
            func.count(Lead.id).label('cnt'),
        )
        .where(Lead.created_at >= start_dt, Lead.created_at.isnot(None))
        .group_by(func.date_trunc('month', Lead.created_at))
        .order_by(func.date_trunc('month', Lead.created_at))
    ).all()

    monthly_dict = {r.month.date().replace(day=1): r.cnt for r in monthly_raw}
    monthly_labels = [f"{RU_MONTHS[m.month]} {m.year}" for m in months_range]
    monthly_data   = [monthly_dict.get(m, 0) for m in months_range]

    # ── Разбивка по каналам ──────────────────────────────────────
    channel_rows = db.session.execute(
        db.select(Campaign.channel, func.count(Lead.id).label('cnt'))
        .join(Lead, Lead.campaign_id == Campaign.id)
        .where(Campaign.channel.isnot(None))
        .group_by(Campaign.channel)
        .order_by(func.count(Lead.id).desc())
    ).all()
    channel_labels = [r.channel for r in channel_rows]
    channel_data   = [r.cnt for r in channel_rows]

    # ── Разбивка B2B / B2G ───────────────────────────────────────
    type_rows = db.session.execute(
        db.select(Lead.client_type, func.count(Lead.id).label('cnt'))
        .group_by(Lead.client_type)
    ).all()
    type_dict = {r.client_type: r.cnt for r in type_rows}
    b2b_count = type_dict.get('b2b', 0)
    b2g_count = type_dict.get('b2g', 0)

    # ── DSS-рекомендации ──────────────────────────────────────────
    bad_campaigns = [
        c for c in all_campaigns
        if c.status == 'active'
        and c.roi is not None and c.roi < 0
        and c.budget and float(c.spent or 0) > float(c.budget) * 0.5
    ]
    dss = compute_dss(
        funnel=funnel,
        total_leads=total_leads,
        avg_roi=avg_roi,
        active_campaigns=active_campaigns,
        global_cr=global_cr,
        b2g_count=b2g_count,
        bad_campaigns=bad_campaigns,
    )

    return render_template(
        'analytics/dashboard.html',
        # KPI
        total_leads=total_leads,
        converted=converted,
        active_campaigns=active_campaigns,
        avg_roi=avg_roi,
        global_cpl=global_cpl,
        global_cr=global_cr,
        # DSS
        dss=dss,
        # Воронка
        funnel=funnel,
        # Динамика
        monthly_labels=monthly_labels,
        monthly_data=monthly_data,
        # Каналы
        channel_labels=channel_labels,
        channel_data=channel_data,
        # B2B/B2G
        b2b_count=b2b_count,
        b2g_count=b2g_count,
        # Таблицы
        top_campaigns=top_campaigns,
        all_campaigns=all_campaigns,
    )


@analytics_bp.route('/export/excel')
@login_required
@role_required('admin', 'marketing')
def export_excel():
    from app.utils.export import export_leads_excel
    from sqlalchemy.orm import joinedload

    leads = db.session.scalars(
        db.select(Lead)
        .options(joinedload(Lead.campaign), joinedload(Lead.assignee))
        .order_by(Lead.created_at.desc())
    ).all()
    campaigns = db.session.scalars(
        db.select(Campaign).order_by(Campaign.name)
    ).all()

    buf = export_leads_excel(leads, campaigns)
    filename = f"marketpulse_{datetime.date.today()}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
