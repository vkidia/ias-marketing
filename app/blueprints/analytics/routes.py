import datetime
from collections import namedtuple

from flask import jsonify, render_template, request, send_file
from flask_login import login_required
from sqlalchemy import case, func

from app.blueprints.analytics import analytics_bp
from app.extensions import db
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.utils.decorators import role_required
from app.utils.dss import compute_dss, compute_campaign_dss, collect_campaign_alerts

RU_MONTHS = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
    7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек',
}

CampaignStats = namedtuple(
    'CampaignStats',
    ['lead_count', 'converted_count', 'revenue', 'cpl', 'roi', 'conversion_rate'],
)


def _last_n_months(n=6):
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


def _aggregate_campaign_metrics():
    """Один запрос вместо N*4: считает лиды, конверсии и выручку по всем кампаниям."""
    rows = db.session.execute(
        db.select(
            Lead.campaign_id,
            func.count(Lead.id).label('lead_count'),
            func.count(case((Lead.status == 'converted', 1))).label('converted_count'),
            func.coalesce(
                func.sum(case((Lead.status == 'converted', Lead.deal_amount), else_=0)),
                0,
            ).label('revenue'),
        )
        .where(Lead.campaign_id.isnot(None))
        .group_by(Lead.campaign_id)
    ).all()
    return {r.campaign_id: r for r in rows}


def _build_chart_data(campaign_id=None):
    """Данные для четырёх графиков. campaign_id=None → глобально, иначе по кампании."""
    filt = (Lead.campaign_id == campaign_id) if campaign_id else None

    # Воронка
    q = db.select(Lead.status, func.count(Lead.id).label('cnt')).group_by(Lead.status)
    if filt is not None:
        q = q.where(filt)
    funnel = {r.status: r.cnt for r in db.session.execute(q).all()}
    for s in ('new', 'contacted', 'qualified', 'converted', 'lost'):
        funnel.setdefault(s, 0)

    # Динамика по месяцам
    months_range = _last_n_months(6)
    start_dt = datetime.datetime(months_range[0].year, months_range[0].month, 1)
    q = (
        db.select(
            func.date_trunc('month', Lead.created_at).label('month'),
            func.count(Lead.id).label('cnt'),
        )
        .where(Lead.created_at >= start_dt, Lead.created_at.isnot(None))
        .group_by(func.date_trunc('month', Lead.created_at))
        .order_by(func.date_trunc('month', Lead.created_at))
    )
    if filt is not None:
        q = q.where(filt)
    monthly_raw = db.session.execute(q).all()
    monthly_dict = {r.month.date().replace(day=1): r.cnt for r in monthly_raw}
    monthly_labels = [f"{RU_MONTHS[m.month]} {m.year}" for m in months_range]
    monthly_data = [monthly_dict.get(m, 0) for m in months_range]

    # Каналы
    q = (
        db.select(Campaign.channel, func.count(Lead.id).label('cnt'))
        .join(Lead, Lead.campaign_id == Campaign.id)
        .where(Campaign.channel.isnot(None))
        .group_by(Campaign.channel)
        .order_by(func.count(Lead.id).desc())
    )
    if campaign_id:
        q = q.where(Campaign.id == campaign_id)
    channel_rows = db.session.execute(q).all()

    # B2B / B2G
    q = db.select(Lead.client_type, func.count(Lead.id).label('cnt')).group_by(Lead.client_type)
    if filt is not None:
        q = q.where(filt)
    type_dict = {r.client_type: r.cnt for r in db.session.execute(q).all()}

    return {
        'funnel': funnel,
        'monthly_labels': monthly_labels,
        'monthly_data': monthly_data,
        'channel_labels': [r.channel for r in channel_rows],
        'channel_data': [r.cnt for r in channel_rows],
        'b2b_count': type_dict.get('b2b', 0),
        'b2g_count': type_dict.get('b2g', 0),
    }


# ── Маршруты ────────────────────────────────────────────────────────────────

@analytics_bp.route('/')
@login_required
def index():
    chart_data = _build_chart_data()
    funnel = chart_data['funnel']
    total_leads = sum(funnel.values())
    converted = funnel['converted']

    all_campaigns = db.session.scalars(
        db.select(Campaign).order_by(Campaign.created_at.desc())
    ).all()
    active_campaigns = sum(1 for c in all_campaigns if c.status == 'active')

    # Метрики кампаний одним агрегирующим запросом
    raw_metrics = _aggregate_campaign_metrics()
    campaign_stats = {}
    roi_values = []

    for c in all_campaigns:
        m = raw_metrics.get(c.id)
        lead_count = m.lead_count if m else 0
        converted_count = m.converted_count if m else 0
        revenue = float(m.revenue) if m else 0.0
        spent = float(c.spent or 0)
        cpl = round(spent / lead_count, 2) if lead_count and spent else None
        roi = round((revenue - spent) / spent * 100, 1) if spent else None
        conv_rate = round(converted_count / lead_count * 100, 1) if lead_count else 0.0
        campaign_stats[c.id] = CampaignStats(
            lead_count=lead_count,
            converted_count=converted_count,
            revenue=revenue,
            cpl=cpl,
            roi=roi,
            conversion_rate=conv_rate,
        )
        if roi is not None:
            roi_values.append(roi)

    avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None
    total_spent = sum(float(c.spent or 0) for c in all_campaigns)
    global_cpl = round(total_spent / total_leads) if total_leads else None
    global_cr = round(converted / total_leads * 100, 1) if total_leads else None

    top_campaigns = sorted(
        [c for c in all_campaigns if campaign_stats[c.id].lead_count > 0],
        key=lambda c: campaign_stats[c.id].conversion_rate,
        reverse=True,
    )[:5]

    roi_by_id = {c.id: campaign_stats[c.id].roi for c in all_campaigns}
    campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)

    dss = compute_dss(
        funnel=funnel,
        total_leads=total_leads,
        avg_roi=avg_roi,
        active_campaigns=active_campaigns,
        global_cr=global_cr,
        campaign_alerts=campaign_alerts,
    )

    # Список кампаний для селектора (только те, у которых есть лиды или активные)
    selector_campaigns = [
        {'id': c.id, 'name': c.name}
        for c in all_campaigns
        if campaign_stats[c.id].lead_count > 0 or c.status == 'active'
    ]

    return render_template(
        'analytics/dashboard.html',
        total_leads=total_leads,
        converted=converted,
        active_campaigns=active_campaigns,
        avg_roi=avg_roi,
        global_cpl=global_cpl,
        global_cr=global_cr,
        dss=dss,
        chart_data=chart_data,
        campaign_stats=campaign_stats,
        top_campaigns=top_campaigns,
        all_campaigns=all_campaigns,
        selector_campaigns=selector_campaigns,
    )


@analytics_bp.route('/api/data')
@analytics_bp.route('/api/data/<int:campaign_id>')
@login_required
def api_data(campaign_id=None):
    chart_data = _build_chart_data(campaign_id=campaign_id)
    funnel = chart_data['funnel']
    total_leads = sum(funnel.values())
    converted = funnel['converted']

    if campaign_id:
        campaign = db.session.get(Campaign, campaign_id)
        if not campaign:
            return jsonify({'error': 'not found'}), 404
        raw = _aggregate_campaign_metrics()
        m = raw.get(campaign_id)
        lead_count = m.lead_count if m else 0
        revenue = float(m.revenue) if m else 0.0
        spent = float(campaign.spent or 0)
        budget = float(campaign.budget or 0)
        cr = round(converted / lead_count * 100, 1) if lead_count else 0.0
        cpl = round(spent / lead_count) if lead_count and spent else None
        roi = round((revenue - spent) / spent * 100, 1) if spent else None
        dss = compute_campaign_dss(
            funnel=funnel,
            total_leads=total_leads,
            roi=roi,
            cr=cr,
            spent=spent,
            budget=budget,
        )
        metrics = {
            'total_leads': lead_count,
            'converted': converted,
            'cr': cr,
            'roi': roi,
            'cpl': int(cpl) if cpl else None,
            'active_campaigns': None,
        }
    else:
        all_campaigns = db.session.scalars(db.select(Campaign)).all()
        active_campaigns = sum(1 for c in all_campaigns if c.status == 'active')
        raw = _aggregate_campaign_metrics()
        roi_values, total_spent, roi_by_id = [], 0.0, {}
        for c in all_campaigns:
            m = raw.get(c.id)
            revenue = float(m.revenue) if m else 0.0
            spent = float(c.spent or 0)
            total_spent += spent
            if spent:
                roi_c = round((revenue - spent) / spent * 100, 1)
                roi_values.append(roi_c)
                roi_by_id[c.id] = roi_c
        cr = round(converted / total_leads * 100, 1) if total_leads else None
        avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None
        global_cpl = round(total_spent / total_leads) if total_leads else None
        campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)
        dss = compute_dss(
            funnel=funnel,
            total_leads=total_leads,
            avg_roi=avg_roi,
            active_campaigns=active_campaigns,
            global_cr=cr,
            campaign_alerts=campaign_alerts,
        )
        metrics = {
            'total_leads': total_leads,
            'converted': converted,
            'cr': cr,
            'roi': avg_roi,
            'cpl': int(global_cpl) if global_cpl else None,
            'active_campaigns': active_campaigns,
        }

    return jsonify({**chart_data, 'metrics': metrics, 'dss': dss})


@analytics_bp.route('/api/compare')
@login_required
def api_compare():
    ids_param = request.args.get('ids', '')
    try:
        campaign_ids = [int(x) for x in ids_param.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'invalid ids'}), 400

    if not campaign_ids:
        return api_data()
    if len(campaign_ids) == 1:
        return api_data(campaign_id=campaign_ids[0])

    months_range = _last_n_months(6)
    start_dt = datetime.datetime(months_range[0].year, months_range[0].month, 1)
    COLORS = ['#0d6efd', '#198754', '#fd7e14', '#dc3545', '#6610f2', '#0dcaf0', '#20c997', '#6c757d']

    campaigns_selected = [db.session.get(Campaign, cid) for cid in campaign_ids]
    campaigns_selected = [c for c in campaigns_selected if c]

    datasets = []
    for i, campaign in enumerate(campaigns_selected):
        q = (
            db.select(
                func.date_trunc('month', Lead.created_at).label('month'),
                func.count(Lead.id).label('cnt'),
            )
            .where(
                Lead.campaign_id == campaign.id,
                Lead.created_at >= start_dt,
                Lead.created_at.isnot(None),
            )
            .group_by(func.date_trunc('month', Lead.created_at))
            .order_by(func.date_trunc('month', Lead.created_at))
        )
        monthly_raw = db.session.execute(q).all()
        monthly_dict = {r.month.date().replace(day=1): r.cnt for r in monthly_raw}
        color = COLORS[i % len(COLORS)]
        datasets.append({
            'label': campaign.name,
            'data': [monthly_dict.get(m, 0) for m in months_range],
            'borderColor': color,
            'backgroundColor': color + '20',
            'fill': False,
            'tension': 0.35,
            'pointRadius': 5,
            'pointHoverRadius': 7,
            'pointBackgroundColor': color,
        })

    q = (
        db.select(Lead.status, func.count(Lead.id).label('cnt'))
        .where(Lead.campaign_id.in_(campaign_ids))
        .group_by(Lead.status)
    )
    funnel = {r.status: r.cnt for r in db.session.execute(q).all()}
    for s in ('new', 'contacted', 'qualified', 'converted', 'lost'):
        funnel.setdefault(s, 0)

    q = (
        db.select(Lead.client_type, func.count(Lead.id).label('cnt'))
        .where(Lead.campaign_id.in_(campaign_ids))
        .group_by(Lead.client_type)
    )
    type_dict = {r.client_type: r.cnt for r in db.session.execute(q).all()}

    q = (
        db.select(Campaign.channel, func.count(Lead.id).label('cnt'))
        .join(Lead, Lead.campaign_id == Campaign.id)
        .where(Campaign.id.in_(campaign_ids), Campaign.channel.isnot(None))
        .group_by(Campaign.channel)
        .order_by(func.count(Lead.id).desc())
    )
    channel_rows = db.session.execute(q).all()

    # Агрегированные метрики и DSS для портфеля выбранных кампаний
    total_leads = sum(funnel.values())
    converted = funnel['converted']
    cr = round(converted / total_leads * 100, 1) if total_leads else None

    raw = _aggregate_campaign_metrics()
    roi_values, total_spent, roi_by_id = [], 0.0, {}
    for c in campaigns_selected:
        m = raw.get(c.id)
        revenue = float(m.revenue) if m else 0.0
        spent = float(c.spent or 0)
        total_spent += spent
        if spent:
            roi_c = round((revenue - spent) / spent * 100, 1)
            roi_values.append(roi_c)
            roi_by_id[c.id] = roi_c

    avg_roi = round(sum(roi_values) / len(roi_values), 1) if roi_values else None
    global_cpl = round(total_spent / total_leads) if total_leads and total_spent else None
    active_campaigns = sum(1 for c in campaigns_selected if c.status == 'active')
    campaign_alerts = collect_campaign_alerts(campaigns_selected, roi_by_id)

    dss = compute_dss(
        funnel=funnel,
        total_leads=total_leads,
        avg_roi=avg_roi,
        active_campaigns=active_campaigns,
        global_cr=cr,
        campaign_alerts=campaign_alerts,
    )
    metrics = {
        'total_leads': total_leads,
        'converted': converted,
        'cr': cr,
        'roi': avg_roi,
        'cpl': int(global_cpl) if global_cpl else None,
        'active_campaigns': active_campaigns,
    }

    return jsonify({
        'mode': 'compare',
        'monthly_labels': [f"{RU_MONTHS[m.month]} {m.year}" for m in months_range],
        'monthly_datasets': datasets,
        'funnel': funnel,
        'b2b_count': type_dict.get('b2b', 0),
        'b2g_count': type_dict.get('b2g', 0),
        'channel_labels': [r.channel for r in channel_rows],
        'channel_data': [r.cnt for r in channel_rows],
        'metrics': metrics,
        'dss': dss,
    })


@analytics_bp.route('/export/excel')
@login_required
@role_required('admin', 'marketing')
def export_excel():
    from app.utils.export import export_leads_excel
    from sqlalchemy.orm import joinedload

    ids_param = request.args.get('campaign_ids', '')
    try:
        campaign_ids = [int(x) for x in ids_param.split(',') if x.strip()] if ids_param else []
    except ValueError:
        campaign_ids = []

    lead_q = (
        db.select(Lead)
        .options(joinedload(Lead.campaign), joinedload(Lead.assignee))
        .order_by(Lead.created_at.desc())
    )
    camp_q = db.select(Campaign).order_by(Campaign.name)
    if campaign_ids:
        lead_q = lead_q.where(Lead.campaign_id.in_(campaign_ids))
        camp_q = camp_q.where(Campaign.id.in_(campaign_ids))

    leads = db.session.scalars(lead_q).all()
    campaigns = db.session.scalars(camp_q).all()

    single_name = campaigns[0].name if len(campaign_ids) == 1 and campaigns else None
    buf = export_leads_excel(leads, list(campaigns), single_campaign_name=single_name)
    filename = f"marketpulse_{datetime.date.today()}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
