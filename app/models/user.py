from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint

ROLES = ('admin', 'marketing', 'sales', 'viewer')


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    full_name     = db.Column(db.String(200))
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default='viewer')
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, server_default=db.func.now())

    # обратные связи
    campaigns_created = db.relationship(
        'Campaign', back_populates='creator',
        foreign_keys='Campaign.created_by', lazy='select'
    )
    leads_assigned = db.relationship(
        'Lead', back_populates='assignee',
        foreign_keys='Lead.assigned_to', lazy='select'
    )

    __table_args__ = (
        CheckConstraint(f"role IN {ROLES}", name='ck_users_role'),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'