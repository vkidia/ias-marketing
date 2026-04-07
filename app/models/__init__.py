# импорт, чтобы Flask-Migrate видел все модели при миграции
from app.models.user import User
from app.models.campaign import Campaign
from app.models.lead import Lead, LeadHistory
from app.models.landing import LandingPage

__all__ = ['User', 'Campaign', 'Lead', 'LeadHistory', 'LandingPage']