from app.extensions import db
from sqlalchemy import CheckConstraint, Index, Numeric

CAMPAIGN_STATUSES = ('draft', 'active', 'paused', 'completed', 'archived')
CAMPAIGN_CHANNELS = ('email', 'social', 'search', 'display', 'referral', 'tender', 'other')
TARGET_AUDIENCES  = ('b2b', 'b2g', 'mixed')


class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    status          = db.Column(db.String(20), nullable=False, default='draft')
    channel         = db.Column(db.String(50))
    target_audience = db.Column(db.String(20))
    budget          = db.Column(Numeric(12, 2), default=0)
    spent           = db.Column(Numeric(12, 2), default=0)
    landing_url     = db.Column(db.String(500))
    utm_source      = db.Column(db.String(100))
    utm_medium      = db.Column(db.String(100))
    utm_campaign    = db.Column(db.String(100))
    start_date      = db.Column(db.Date)
    end_date        = db.Column(db.Date)
    created_by      = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_at      = db.Column(db.DateTime, server_default=db.func.now())
    updated_at      = db.Column(db.DateTime, onupdate=db.func.now())

    # связи
    creator       = db.relationship(
        'User', back_populates='campaigns_created',
        foreign_keys=[created_by]
    )
    leads         = db.relationship(
        'Lead', back_populates='campaign', lazy='select'
    )
    landing_pages = db.relationship(
        'LandingPage', back_populates='campaign',
        cascade='all, delete-orphan', passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(f"status IN {CAMPAIGN_STATUSES}",         name='ck_campaigns_status'),
        CheckConstraint(f"channel IN {CAMPAIGN_CHANNELS}",        name='ck_campaigns_channel'),
        CheckConstraint(f"target_audience IN {TARGET_AUDIENCES}", name='ck_campaigns_audience'),
        CheckConstraint("budget >= 0",                            name='ck_campaigns_budget_positive'),
        CheckConstraint("spent >= 0",                             name='ck_campaigns_spent_positive'),
        Index('ix_campaigns_status',     'status'),
        Index('ix_campaigns_channel',    'channel'),
        Index('ix_campaigns_created_at', 'created_at'),
    )

    # вычисляемые метрики (не хранятся в БД)

    @property
    def lead_count(self):
        from app.models.lead import Lead
        return db.session.scalar(
            db.select(db.func.count(Lead.id)).where(Lead.campaign_id == self.id)
        ) or 0

    @property
    def cpl(self):
        """Cost per lead."""
        if self.lead_count and self.spent:
            return round(float(self.spent) / self.lead_count, 2)
        return None

    @property
    def revenue(self):
        """Сумма deal_amount всех converted лидов кампании."""
        from app.models.lead import Lead
        return db.session.scalar(
            db.select(db.func.sum(Lead.deal_amount))
            .where(Lead.campaign_id == self.id, Lead.status == 'converted')
        ) or 0

    @property
    def conversion_rate(self):
        """Процент конверсии: converted / total * 100."""
        if not self.lead_count:
            return 0
        from app.models.lead import Lead
        converted = db.session.scalar(
            db.select(db.func.count(Lead.id))
            .where(Lead.campaign_id == self.id, Lead.status == 'converted')
        ) or 0
        return round(converted / self.lead_count * 100, 1)

    @property
    def roi(self):
        """ROI = (выручка - затраты) / затраты * 100. None если spent=0."""
        if not self.spent or float(self.spent) == 0:
            return None
        return round((float(self.revenue) - float(self.spent)) / float(self.spent) * 100, 1)

    def can_delete(self):
        """Кампанию можно удалить только если у неё нет лидов."""
        return self.lead_count == 0

    def __repr__(self):
        return f'<Campaign {self.name} [{self.status}]>'