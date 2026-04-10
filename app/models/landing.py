from app.extensions import db
from sqlalchemy import Index


class LandingPage(db.Model):
    __tablename__ = 'landing_pages'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    slug        = db.Column(db.String(100), unique=True, nullable=True)
    url         = db.Column(db.String(500), nullable=True)   # внешний URL (опционально)
    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey('campaigns.id', ondelete='CASCADE'),
        nullable=False
    )
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    created_at  = db.Column(db.DateTime, server_default=db.func.now())

    campaign = db.relationship('Campaign', back_populates='landing_pages')

    __table_args__ = (
        Index('ix_landing_pages_campaign_id', 'campaign_id'),
        Index('ix_landing_pages_slug', 'slug', unique=True),
    )

    def __repr__(self):
        return f'<LandingPage {self.name}>'