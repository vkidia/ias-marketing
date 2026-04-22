"""
test_campaigns.py — тесты кампаний:
  - создание кампании сохраняется в БД
  - ROI рассчитывается правильно (положительный, нулевые затраты, отрицательный)
"""
import pytest
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.extensions import db


@pytest.fixture
def campaign(db, admin_user):
    c = Campaign(
        name='Тестовая кампания',
        channel='email',
        status='active',
        target_audience='b2b',
        budget=10000,
        spent=1000,
        created_by=admin_user.id,
    )
    db.session.add(c)
    db.session.commit()
    return c


class TestCreateCampaign:
    def test_create_campaign_persisted(self, db, admin_user):
        """Созданная кампания должна сохраняться в БД."""
        c = Campaign(
            name='Новая кампания',
            channel='search',
            status='draft',
            target_audience='b2g',
            budget=5000,
            spent=0,
            created_by=admin_user.id,
        )
        db.session.add(c)
        db.session.commit()

        found = db.session.get(Campaign, c.id)
        assert found is not None
        assert found.name == 'Новая кампания'
        assert found.channel == 'search'


class TestCampaignROI:
    def test_roi_positive(self, db, campaign):
        """ROI = (выручка - затраты) / затраты * 100."""
        lead = Lead(
            first_name='Клиент',
            email='client@corp.ru',
            campaign_id=campaign.id,
            status='converted',
            deal_amount=3000,
            client_type='b2b',
        )
        db.session.add(lead)
        db.session.commit()

        # spent=1000, revenue=3000 → ROI = 200.0%
        assert campaign.roi == 200.0

    def test_roi_zero_spent(self, db, admin_user):
        """Если затраты равны нулю, ROI должен быть None."""
        c = Campaign(
            name='Без затрат',
            channel='social',
            status='draft',
            target_audience='b2b',
            budget=0,
            spent=0,
            created_by=admin_user.id,
        )
        db.session.add(c)
        db.session.commit()
        assert c.roi is None

    def test_roi_negative(self, db, campaign):
        """Затраты превышают выручку → отрицательный ROI."""
        lead = Lead(
            first_name='Клиент',
            email='client@corp.ru',
            campaign_id=campaign.id,
            status='converted',
            deal_amount=500,
            client_type='b2b',
        )
        db.session.add(lead)
        db.session.commit()

        # spent=1000, revenue=500 → ROI = -50.0%
        assert campaign.roi == -50.0
