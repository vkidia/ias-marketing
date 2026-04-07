from app.extensions import db
from sqlalchemy import Index


class LandingPage(db.Model):
    __tablename__ = 'landing_pages'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    url         = db.Column(db.String(500), nullable=False)
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
    )

    def __repr__(self):
        return f'<LandingPage {self.name}>'