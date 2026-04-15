import csv
import io

from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user

from app.blueprints.leads import leads_bp
from app.blueprints.leads.forms import LeadForm, LeadImportForm
from app.extensions import db
from app.models.campaign import Campaign
from app.models.lead import Lead, LEAD_STATUSES, CLIENT_TYPES, LEAD_SOURCES, ALLOWED_TRANSITIONS
from app.models.user import User
from app.utils.decorators import role_required
from app.utils.scoring import update_lead_score


# ─── вспомогательные запросы ────────────────────────────────────────────────

def _assignable_users():
    """Пользователи sales и admin — для поля «Ответственный»."""
    return db.session.scalars(
        db.select(User)
        .where(User.is_active == True, User.role.in_(('sales', 'admin')))
        .order_by(User.full_name, User.username)
    ).all()


def _available_campaigns():
    """Все кампании кроме archived — для поля «Кампания»."""
    return db.session.scalars(
        db.select(Campaign)
        .where(Campaign.status != 'archived')
        .order_by(Campaign.name)
    ).all()


def _fill_choices(form):
    """Заполнить динамические choices формы."""
    form.campaign_id.choices = [('', '— без кампании —')] + [
        (str(c.id), c.name) for c in _available_campaigns()
    ]
    form.assigned_to.choices = [('', '— не назначен —')] + [
        (str(u.id), u.full_name or u.username) for u in _assignable_users()
    ]


def _apply_form_to_lead(form, lead):
    """Перенести данные формы в объект Lead (без commit)."""
    lead.first_name             = form.first_name.data
    lead.last_name              = form.last_name.data or None
    lead.email                  = form.email.data
    lead.phone                  = form.phone.data or None
    lead.position               = form.position.data or None
    lead.company                = form.company.data or None
    lead.inn                    = form.inn.data or None
    lead.city                   = form.city.data or None
    lead.client_type            = form.client_type.data
    lead.decision_maker_name     = form.decision_maker_name.data or None
    lead.decision_maker_position = form.decision_maker_position.data or None
    lead.source                 = form.source.data or None
    lead.utm_source             = form.utm_source.data or None
    lead.utm_medium             = form.utm_medium.data or None
    lead.utm_campaign           = form.utm_campaign.data or None
    lead.deal_amount            = form.deal_amount.data or None
    lead.notes                  = form.notes.data or None
    lead.campaign_id            = int(form.campaign_id.data) if form.campaign_id.data else None
    lead.assigned_to            = int(form.assigned_to.data) if form.assigned_to.data else None
    return lead


# ─── маршруты ───────────────────────────────────────────────────────────────

PER_PAGE = 20


@leads_bp.route('/')
@login_required
def index():
    status_filter      = request.args.get('status',      '')
    campaign_filter    = request.args.get('campaign_id', '')
    client_type_filter = request.args.get('client_type', '')
    search             = request.args.get('q', '').strip()
    page               = request.args.get('page', 1, type=int)

    query = db.select(Lead).order_by(Lead.created_at.desc())

    if status_filter in LEAD_STATUSES:
        query = query.where(Lead.status == status_filter)
    if campaign_filter.isdigit():
        query = query.where(Lead.campaign_id == int(campaign_filter))
    if client_type_filter in CLIENT_TYPES:
        query = query.where(Lead.client_type == client_type_filter)
    if search:
        like = f'%{search}%'
        query = query.where(db.or_(
            Lead.first_name.ilike(like),
            Lead.last_name.ilike(like),
            Lead.email.ilike(like),
            Lead.company.ilike(like),
        ))

    pagination = db.paginate(query, page=page, per_page=PER_PAGE, error_out=False)
    leads      = pagination.items
    campaigns  = db.session.scalars(db.select(Campaign).order_by(Campaign.name)).all()

    # Счётчики по статусам для всей выборки (без пагинации)
    all_leads = db.session.scalars(query).all()

    return render_template(
        'leads/list.html',
        leads=leads,
        all_leads=all_leads,
        pagination=pagination,
        campaigns=campaigns,
        statuses=LEAD_STATUSES,
        client_types=CLIENT_TYPES,
        current_status=status_filter,
        current_campaign=campaign_filter,
        current_client_type=client_type_filter,
        search=search,
    )


@leads_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'marketing', 'sales')
def create():
    form = LeadForm()
    _fill_choices(form)

    if form.validate_on_submit():
        lead = _apply_form_to_lead(form, Lead())
        db.session.add(lead)
        update_lead_score(lead)   # lazy-load lead.campaign через auto-flush
        db.session.commit()
        flash(f'Лид «{lead.full_name}» создан. Score: {lead.score}.', 'success')
        return redirect(url_for('leads.detail', id=lead.id))

    return render_template('leads/form.html', form=form, lead=None)


@leads_bp.route('/<int:id>')
@login_required
def detail(id):
    lead = db.session.get(Lead, id) or abort(404)
    return render_template(
        'leads/detail.html',
        lead=lead,
        allowed_transitions=ALLOWED_TRANSITIONS,
    )


@leads_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'marketing', 'sales')
def edit(id):
    lead = db.session.get(Lead, id) or abort(404)
    form = LeadForm(obj=lead)
    _fill_choices(form)

    # SelectField хранит строки — приводим FK к строке при GET
    if request.method == 'GET':
        form.campaign_id.data = str(lead.campaign_id) if lead.campaign_id else ''
        form.assigned_to.data = str(lead.assigned_to) if lead.assigned_to else ''

    if form.validate_on_submit():
        _apply_form_to_lead(form, lead)
        update_lead_score(lead)
        db.session.commit()
        flash(f'Лид «{lead.full_name}» обновлён. Score: {lead.score}.', 'success')
        return redirect(url_for('leads.detail', id=lead.id))

    return render_template('leads/form.html', form=form, lead=lead)


@leads_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'marketing')
def delete(id):
    lead = db.session.get(Lead, id) or abort(404)
    name = lead.full_name
    db.session.delete(lead)
    db.session.commit()
    flash(f'Лид «{name}» удалён.', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/<int:id>/status', methods=['POST'])
@login_required
@role_required('admin', 'marketing', 'sales')
def change_status(id):
    """AJAX-эндпоинт смены статуса. Принимает JSON, возвращает JSON."""
    lead = db.session.get(Lead, id) or abort(404)
    data       = request.get_json(silent=True) or {}
    new_status = data.get('new_status', '')
    comment    = data.get('comment') or None

    if not lead.can_transition_to(new_status):
        return jsonify({'ok': False,
                        'error': f'Переход {lead.status} → {new_status} запрещён'}), 400

    lead.transition_to(new_status, current_user.id, comment=comment)
    db.session.commit()
    return jsonify({'ok': True, 'new_status': new_status, 'score': lead.score})


@leads_bp.route('/import', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'marketing')
def import_csv():
    form = LeadImportForm()
    form.campaign_id.choices = [('', '— без кампании —')] + [
        (str(c.id), c.name) for c in _available_campaigns()
    ]
    results = None

    if form.validate_on_submit():
        f = form.csv_file.data
        try:
            stream = io.StringIO(f.stream.read().decode('utf-8-sig'))
        except UnicodeDecodeError:
            flash('Ошибка чтения файла. Сохраните CSV в кодировке UTF-8.', 'danger')
            return render_template('leads/import.html', form=form, results=None)

        reader      = csv.DictReader(stream)
        campaign_id = int(form.campaign_id.data) if form.campaign_id.data else None
        created, warnings, errors = [], [], []

        for i, row in enumerate(reader, start=2):
            fn    = row.get('first_name', '').strip()
            email = row.get('email', '').strip().lower()

            if not fn or not email:
                errors.append(f'Строка {i}: нет имени или email — пропущена')
                continue

            # проверка дублей — предупреждение без блокировки
            existing = db.session.scalars(
                db.select(Lead).where(Lead.email == email)
            ).first()
            if existing:
                warnings.append(
                    f'Строка {i}: {email} уже есть в базе'
                    f' (лид #{existing.id} — {existing.full_name})'
                )

            ct  = row.get('client_type', 'b2b').lower().strip()
            ct  = ct if ct in CLIENT_TYPES else 'b2b'

            src = row.get('source', 'import').lower().strip()
            src = src if src in LEAD_SOURCES else 'import'

            # campaign_id из строки CSV перекрывает выбранный в форме
            cid = campaign_id
            if row.get('campaign_id', '').strip().isdigit():
                cid = int(row['campaign_id'])

            lead = Lead(
                first_name  = fn,
                last_name   = row.get('last_name',  '').strip() or None,
                email       = email,
                phone       = row.get('phone',      '').strip() or None,
                company     = row.get('company',    '').strip() or None,
                position    = row.get('position',   '').strip() or None,
                city        = row.get('city',       '').strip() or None,
                inn         = row.get('inn',        '').strip() or None,
                client_type = ct,
                source      = src,
                campaign_id = cid,
            )
            db.session.add(lead)
            update_lead_score(lead)
            created.append(f'{lead.first_name} {lead.last_name or ""} ({lead.email})')

        db.session.commit()
        results = {'created': created, 'warnings': warnings, 'errors': errors}
        if created:
            flash(f'Импорт завершён: создано {len(created)} лидов.', 'success')

    return render_template('leads/import.html', form=form, results=results)
