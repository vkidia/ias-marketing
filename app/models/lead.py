from app.extensions import db
from sqlalchemy import CheckConstraint, Index, Numeric
from sqlalchemy.orm import validates
import datetime

LEAD_STATUSES = ('new', 'contacted', 'qualified', 'converted', 'lost')
LEAD_SOURCES  = ('landing', 'form', 'import', 'manual')
CLIENT_TYPES  = ('b2b', 'b2g')

ALLOWED_TRANSITIONS = {
    'new':       ('contacted', 'lost'),
    'contacted': ('qualified', 'lost'),
    'qualified': ('converted', 'lost'),
    'converted': (),
    'lost':      (),
}


class Lead(db.Model):
    __tablename__ = 'leads'

    id         = db.Column(db.Integer, primary_key=True)

    # контактное лицо
    first_name = db.Column(db.String(100), nullable=False)
    last_name  = db.Column(db.String(100))
    email      = db.Column(db.String(120), nullable=False)
    phone      = db.Column(db.String(20))
    position   = db.Column(db.String(100))

    # организация
    company    = db.Column(db.String(200))
    inn        = db.Column(db.String(12))
    city       = db.Column(db.String(100))
    client_type = db.Column(db.String(10), nullable=False, default='b2b')

    # ЛПР
    decision_maker_name     = db.Column(db.String(200))
    decision_maker_position = db.Column(db.String(100))

    # воронка
    status       = db.Column(db.String(20), nullable=False, default='new')
    score        = db.Column(db.Integer, default=0)
    # source — nullable: лид может прийти до того как выбран источник
    source       = db.Column(db.String(50), nullable=True)
    utm_source   = db.Column(db.String(100))
    utm_medium   = db.Column(db.String(100))
    utm_campaign = db.Column(db.String(100))
    deal_amount  = db.Column(Numeric(12, 2), nullable=True)
    notes        = db.Column(db.Text)

    # FK
    campaign_id  = db.Column(
        db.Integer,
        db.ForeignKey('campaigns.id', ondelete='RESTRICT'),
        nullable=True
    )
    assigned_to  = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # даты
    created_at        = db.Column(db.DateTime, server_default=db.func.now())
    updated_at        = db.Column(db.DateTime, onupdate=db.func.now())
    converted_at      = db.Column(db.DateTime, nullable=True)
    status_changed_at = db.Column(db.DateTime, nullable=True)

    # связи
    campaign = db.relationship(
        'Campaign', back_populates='leads',
        foreign_keys=[campaign_id]
    )
    assignee = db.relationship(
        'User', back_populates='leads_assigned',
        foreign_keys=[assigned_to]
    )
    history  = db.relationship(
        'LeadHistory', back_populates='lead',
        cascade='all, delete-orphan', passive_deletes=True,
        order_by='LeadHistory.created_at.desc()'
    )

    __table_args__ = (
        # source nullable — CHECK только если есть значение
        CheckConstraint(
            f"source IS NULL OR source IN {LEAD_SOURCES}",
            name='ck_leads_source'
        ),
        CheckConstraint(f"status IN {LEAD_STATUSES}",         name='ck_leads_status'),
        CheckConstraint(f"client_type IN {CLIENT_TYPES}",     name='ck_leads_client_type'),
        CheckConstraint("score >= 0 AND score <= 100",        name='ck_leads_score_range'),
        Index('ix_leads_campaign_id',       'campaign_id'),
        Index('ix_leads_assigned_to',       'assigned_to'),
        Index('ix_leads_status',            'status'),
        Index('ix_leads_email',             'email'),
        Index('ix_leads_created_at',        'created_at'),
        Index('ix_leads_client_type',       'client_type'),
        Index('ix_leads_inn',               'inn'),
        Index('ix_leads_status_changed_at', 'status_changed_at'),
    )

    # бизнес-логика воронки 

    def can_transition_to(self, new_status):
        return new_status in ALLOWED_TRANSITIONS.get(self.status, ())

    def transition_to(self, new_status, changed_by_id, comment=None):
        """Сменить статус лида с записью в историю."""
        if not self.can_transition_to(new_status):
            raise ValueError(f"Переход {self.status} → {new_status} запрещён")
        old = self.status
        self.status = new_status
        self.status_changed_at = datetime.datetime.utcnow()
        if new_status == 'converted':
            self.converted_at = datetime.datetime.utcnow()
        db.session.add(LeadHistory(
            lead_id=self.id,
            old_status=old,
            new_status=new_status,
            changed_by=changed_by_id,
            comment=comment
        ))

    # валидаторы 

    @validates('email')
    def validate_email(self, key, value):
        if value and '@' not in value:
            raise ValueError(f'Некорректный email: {value}')
        return value.lower().strip() if value else value

    @validates('inn')
    def validate_inn(self, key, value):
        if value:
            if not value.isdigit():
                raise ValueError('ИНН — только цифры')
            if len(value) not in (10, 12):
                raise ValueError('ИНН — 10 или 12 цифр')
        return value

    @validates('score')
    def validate_score(self, key, value):
        return max(0, min(100, int(value or 0)))

    @property
    def full_name(self):
        parts = [self.first_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def days_in_status(self):
        """Сколько дней лид находится в текущем статусе."""
        if self.status_changed_at:
            return (datetime.datetime.utcnow() - self.status_changed_at).days
        if self.created_at:
            return (datetime.datetime.utcnow() - self.created_at).days
        return 0

    def __repr__(self):
        return f'<Lead {self.first_name} {self.last_name or ""} [{self.status}]>'


class LeadHistory(db.Model):
    __tablename__ = 'lead_history'

    id         = db.Column(db.Integer, primary_key=True)
    lead_id    = db.Column(
        db.Integer,
        db.ForeignKey('leads.id', ondelete='CASCADE'),
        nullable=False
    )
    old_status = db.Column(db.String(20), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    changed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    comment    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    lead    = db.relationship('Lead', back_populates='history')
    changer = db.relationship('User', foreign_keys=[changed_by])

    __table_args__ = (
        Index('ix_lead_history_lead_id',    'lead_id'),
        Index('ix_lead_history_created_at', 'created_at'),
    )

    def __repr__(self):
        return f'<LeadHistory lead={self.lead_id} {self.old_status}→{self.new_status}>'