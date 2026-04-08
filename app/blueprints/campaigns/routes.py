from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.blueprints.campaigns import campaigns_bp
from app.blueprints.campaigns.forms import CampaignForm
from app.extensions import db
from app.models.campaign import Campaign, CAMPAIGN_STATUSES, CAMPAIGN_CHANNELS
from app.utils.decorators import role_required


@campaigns_bp.route('/')
@login_required
def index():
    status_filter  = request.args.get('status',  '')
    channel_filter = request.args.get('channel', '')

    query = db.select(Campaign).order_by(Campaign.created_at.desc())
    if status_filter in CAMPAIGN_STATUSES:
        query = query.where(Campaign.status == status_filter)
    if channel_filter in CAMPAIGN_CHANNELS:
        query = query.where(Campaign.channel == channel_filter)

    campaigns = db.session.scalars(query).all()

    return render_template(
        'campaigns/list.html',
        campaigns=campaigns,
        statuses=CAMPAIGN_STATUSES,
        channels=CAMPAIGN_CHANNELS,
        current_status=status_filter,
        current_channel=channel_filter,
    )


@campaigns_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'marketing')
def create():
    form = CampaignForm()
    if form.validate_on_submit():
        campaign = Campaign(
            name=form.name.data,
            description=form.description.data or None,
            status=form.status.data,
            channel=form.channel.data or None,
            target_audience=form.target_audience.data or None,
            budget=form.budget.data or 0,
            spent=form.spent.data or 0,
            utm_source=form.utm_source.data or None,
            utm_medium=form.utm_medium.data or None,
            utm_campaign=form.utm_campaign.data or None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            created_by=current_user.id,
        )
        db.session.add(campaign)
        db.session.commit()
        flash(f'Кампания «{campaign.name}» создана.', 'success')
        return redirect(url_for('campaigns.detail', id=campaign.id))
    return render_template('campaigns/form.html', form=form, campaign=None)


@campaigns_bp.route('/<int:id>')
@login_required
def detail(id):
    campaign = db.session.get(Campaign, id) or abort(404)
    return render_template('campaigns/detail.html', campaign=campaign, leads=campaign.leads)


@campaigns_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'marketing')
def edit(id):
    campaign = db.session.get(Campaign, id) or abort(404)
    form = CampaignForm(obj=campaign)
    if form.validate_on_submit():
        form.populate_obj(campaign)
        # Пустые строки из SelectField → NULL
        campaign.channel         = campaign.channel         or None
        campaign.target_audience = campaign.target_audience or None
        campaign.utm_source      = campaign.utm_source      or None
        campaign.utm_medium      = campaign.utm_medium      or None
        campaign.utm_campaign    = campaign.utm_campaign    or None
        campaign.description     = campaign.description     or None
        db.session.commit()
        flash(f'Кампания «{campaign.name}» обновлена.', 'success')
        return redirect(url_for('campaigns.detail', id=campaign.id))
    return render_template('campaigns/form.html', form=form, campaign=campaign)


@campaigns_bp.route('/<int:id>/archive', methods=['POST'])
@login_required
@role_required('admin', 'marketing')
def archive(id):
    campaign = db.session.get(Campaign, id) or abort(404)
    if campaign.status == 'archived':
        flash('Кампания уже архивирована.', 'warning')
        return redirect(url_for('campaigns.detail', id=id))
    campaign.status = 'archived'
    db.session.commit()
    flash(f'Кампания «{campaign.name}» перемещена в архив.', 'success')
    return redirect(url_for('campaigns.index'))


@campaigns_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'marketing')
def delete(id):
    campaign = db.session.get(Campaign, id) or abort(404)
    if not campaign.can_delete():
        flash('Нельзя удалить кампанию с лидами. Сначала архивируйте её.', 'danger')
        return redirect(url_for('campaigns.detail', id=id))
    name = campaign.name
    db.session.delete(campaign)
    db.session.commit()
    flash(f'Кампания «{name}» удалена.', 'success')
    return redirect(url_for('campaigns.index'))
