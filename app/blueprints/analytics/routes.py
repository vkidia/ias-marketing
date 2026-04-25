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
from app.utils.dss import compute_dss, collect_campaign_alerts

RU_MONTHS = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
    7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек',
}

# лёгкая структура для хранения агрегированных метрик одной кампании
CampaignStats = namedtuple(
    'CampaignStats',
    ['lead_count', 'converted_count', 'revenue', 'cpl', 'roi', 'conversion_rate'],
)


def _last_n_months(n=6):
    # возвращает список дат первых дней последних N месяцев в хронологическом порядке
    # логика с while нужна чтобы корректно перейти через январь в предыдущий год
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


def _lead_health_stats(campaign_ids=None):
    """
    Один запрос: считает показатели здоровья лидов для DSS.
    campaign_ids=None → по всем кампаниям.
    Возвращает (sla_breach, stagnant_contacted, stagnant_qualified, unassigned, missing_amounts).
    """
    from app.utils.dss import _STAGNATION_DAYS
    now = datetime.datetime.utcnow()
    sla_cutoff          = now - datetime.timedelta(hours=24)
    contacted_cutoff    = now - datetime.timedelta(days=_STAGNATION_DAYS['contacted'])
    qualified_cutoff    = now - datetime.timedelta(days=_STAGNATION_DAYS['qualified'])

    base = db.select(Lead.id, Lead.status, Lead.created_at, Lead.status_changed_at,
                     Lead.assigned_to, Lead.deal_amount)
    if campaign_ids is not None:
        base = base.where(Lead.campaign_id.in_(campaign_ids))
    else:
        base = base.where(Lead.campaign_id.isnot(None))

    rows = db.session.execute(base).all()

    sla_breach = stagnant_c = stagnant_q = unassigned = missing_amounts = 0
    for r in rows:
        # SLA: в статусе 'new' дольше 24 часов
        if r.status == 'new' and r.created_at and r.created_at < sla_cutoff:
            sla_breach += 1

        # Стагнация: contacted/qualified без движения N дней
        last_change = r.status_changed_at or r.created_at
        if r.status == 'contacted' and last_change and last_change < contacted_cutoff:
            stagnant_c += 1
        elif r.status == 'qualified' and last_change and last_change < qualified_cutoff:
            stagnant_q += 1

        # Нераспределённые активные лиды
        if r.status not in ('converted', 'lost') and r.assigned_to is None:
            unassigned += 1

        # Конвертированные без суммы сделки
        if r.status == 'converted' and (r.deal_amount is None or r.deal_amount == 0):
            missing_amounts += 1

    return sla_breach, stagnant_c, stagnant_q, unassigned, missing_amounts


def _funnel_step_rates(campaign_ids=None):
    """
    Из lead_history считает реальные step-конверсии воронки.
    Возвращает dict {'new_contacted': float, 'contacted_qualified': float,
                     'qualified_converted': float} или пустой dict при нехватке данных.
    """
    from app.models.lead import LeadHistory

    q = (
        db.select(
            LeadHistory.old_status,
            LeadHistory.new_status,
            func.count(LeadHistory.id).label('cnt'),
        )
        .join(Lead, Lead.id == LeadHistory.lead_id)
        .group_by(LeadHistory.old_status, LeadHistory.new_status)
    )
    if campaign_ids is not None:
        q = q.where(Lead.campaign_id.in_(campaign_ids))
    else:
        q = q.where(Lead.campaign_id.isnot(None))

    rows = db.session.execute(q).all()

    # строим матрицу переходов: {old: {new: count}}
    transitions = {}
    for r in rows:
        transitions.setdefault(r.old_status, {})[r.new_status] = r.cnt

    steps = {}
    _MIN_TRANSITIONS = 5  # меньше — статистика ненадёжна

    def _rate(from_status, to_status):
        frm = transitions.get(from_status, {})
        total = sum(frm.values())
        if total < _MIN_TRANSITIONS:
            return None
        return round(frm.get(to_status, 0) / total, 3)

    r1 = _rate('new',       'contacted')
    r2 = _rate('contacted', 'qualified')
    r3 = _rate('qualified', 'converted')
    if r1 is not None: steps['new_contacted']       = r1
    if r2 is not None: steps['contacted_qualified'] = r2
    if r3 is not None: steps['qualified_converted'] = r3
    return steps


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
    total_spent = 0.0
    total_revenue = 0.0

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
        total_spent   += spent
        total_revenue += revenue

    # взвешенный ROI: (суммарная выручка - суммарные расходы) / расходы
    avg_roi    = round((total_revenue - total_spent) / total_spent * 100, 1) if total_spent else None
    global_cpl = round(total_spent / total_leads) if total_leads else None
    global_cr  = round(converted / total_leads * 100, 1) if total_leads else None

    b2b_count = chart_data.get('b2b_count', 0)
    b2g_count = chart_data.get('b2g_count', 0)
    b2g_ratio = round(b2g_count / (b2b_count + b2g_count), 3) if (b2b_count + b2g_count) else 0.0

    # топ 5 кампаний по конверсии, только те у которых есть хотя бы один лид
    top_campaigns = sorted(
        [c for c in all_campaigns if campaign_stats[c.id].lead_count > 0],
        key=lambda c: campaign_stats[c.id].conversion_rate,
        reverse=True,
    )[:5]

    roi_by_id = {c.id: campaign_stats[c.id].roi for c in all_campaigns}
    campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)

    sla, stagnant_c, stagnant_q, unassigned, missing_amounts = _lead_health_stats()
    funnel_steps = _funnel_step_rates()

    dss = compute_dss(
        mode='all',
        funnel=funnel,
        total_leads=total_leads,
        roi=avg_roi,
        cr=global_cr,
        active_count=active_campaigns,
        campaign_count=len(all_campaigns),
        campaign_alerts=campaign_alerts,
        b2g_ratio=b2g_ratio,
        sla_breach=sla,
        stagnant_contacted=stagnant_c,
        stagnant_qualified=stagnant_q,
        unassigned=unassigned,
        missing_amounts=missing_amounts,
        funnel_steps=funnel_steps,
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

        b2b = chart_data.get('b2b_count', 0)
        b2g = chart_data.get('b2g_count', 0)
        b2g_ratio = round(b2g / (b2b + b2g), 3) if (b2b + b2g) else 0.0

        today = datetime.date.today()
        campaign_age_days = (today - campaign.start_date).days if campaign.start_date else None

        sla, stagnant_c, stagnant_q, unassigned, missing_amounts = _lead_health_stats([campaign_id])
        funnel_steps = _funnel_step_rates([campaign_id])

        dss = compute_dss(
            mode='single',
            funnel=funnel,
            total_leads=total_leads,
            roi=roi,
            cr=cr,
            spent=spent,
            budget=budget,
            b2g_ratio=b2g_ratio,
            campaign_age_days=campaign_age_days,
            sla_breach=sla,
            stagnant_contacted=stagnant_c,
            stagnant_qualified=stagnant_q,
            unassigned=unassigned,
            missing_amounts=missing_amounts,
            funnel_steps=funnel_steps,
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
        total_spent = 0.0
        total_revenue = 0.0
        roi_by_id = {}
        for c in all_campaigns:
            m = raw.get(c.id)
            revenue = float(m.revenue) if m else 0.0
            spent = float(c.spent or 0)
            total_spent   += spent
            total_revenue += revenue
            if spent:
                roi_by_id[c.id] = round((revenue - spent) / spent * 100, 1)
        cr = round(converted / total_leads * 100, 1) if total_leads else None
        avg_roi    = round((total_revenue - total_spent) / total_spent * 100, 1) if total_spent else None
        global_cpl = round(total_spent / total_leads) if total_leads else None

        b2b = chart_data.get('b2b_count', 0)
        b2g = chart_data.get('b2g_count', 0)
        b2g_ratio = round(b2g / (b2b + b2g), 3) if (b2b + b2g) else 0.0

        campaign_alerts = collect_campaign_alerts(all_campaigns, roi_by_id)
        sla, stagnant_c, stagnant_q, unassigned, missing_amounts = _lead_health_stats()
        funnel_steps = _funnel_step_rates()

        dss = compute_dss(
            mode='all',
            funnel=funnel,
            total_leads=total_leads,
            roi=avg_roi,
            cr=cr,
            active_count=active_campaigns,
            campaign_count=len(all_campaigns),
            campaign_alerts=campaign_alerts,
            b2g_ratio=b2g_ratio,
            sla_breach=sla,
            stagnant_contacted=stagnant_c,
            stagnant_qualified=stagnant_q,
            unassigned=unassigned,
            missing_amounts=missing_amounts,
            funnel_steps=funnel_steps,
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
    total_spent = 0.0
    total_revenue = 0.0
    roi_by_id = {}
    for c in campaigns_selected:
        m = raw.get(c.id)
        revenue = float(m.revenue) if m else 0.0
        spent = float(c.spent or 0)
        total_spent   += spent
        total_revenue += revenue
        if spent:
            roi_by_id[c.id] = round((revenue - spent) / spent * 100, 1)

    avg_roi    = round((total_revenue - total_spent) / total_spent * 100, 1) if total_spent else None
    global_cpl = round(total_spent / total_leads) if total_leads and total_spent else None
    active_count = sum(1 for c in campaigns_selected if c.status == 'active')

    b2b = type_dict.get('b2b', 0)
    b2g = type_dict.get('b2g', 0)
    b2g_ratio = round(b2g / (b2b + b2g), 3) if (b2b + b2g) else 0.0

    campaign_alerts = collect_campaign_alerts(campaigns_selected, roi_by_id)
    sla, stagnant_c, stagnant_q, unassigned, missing_amounts = _lead_health_stats(campaign_ids)
    funnel_steps = _funnel_step_rates(campaign_ids)

    dss = compute_dss(
        mode='group',
        funnel=funnel,
        total_leads=total_leads,
        roi=avg_roi,
        cr=cr,
        active_count=active_count,
        campaign_count=len(campaigns_selected),
        campaign_alerts=campaign_alerts,
        b2g_ratio=b2g_ratio,
        sla_breach=sla,
        stagnant_contacted=stagnant_c,
        stagnant_qualified=stagnant_q,
        unassigned=unassigned,
        missing_amounts=missing_amounts,
        funnel_steps=funnel_steps,
    )
    metrics = {
        'total_leads': total_leads,
        'converted': converted,
        'cr': cr,
        'roi': avg_roi,
        'cpl': int(global_cpl) if global_cpl else None,
        'active_campaigns': active_count,
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
@role_required('admin', 'marketing', 'sales', 'viewer')
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
