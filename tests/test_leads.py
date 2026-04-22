"""
test_leads.py — тесты валидации переходов статусов лида.
Нельзя из converted вернуться в new/contacted/qualified.
Lost — тоже терминальный статус.
"""
import pytest
from app.models.lead import Lead, LeadHistory
from app.extensions import db


@pytest.fixture
def lead(db, admin_user):
    l = Lead(
        first_name='Тест',
        email='test@corp.ru',
        client_type='b2b',
        status='new',
    )
    db.session.add(l)
    db.session.commit()
    return l


@pytest.fixture
def converted_lead(db, admin_user):
    l = Lead(
        first_name='Конвертирован',
        email='done@corp.ru',
        client_type='b2b',
        status='converted',
    )
    db.session.add(l)
    db.session.commit()
    return l


@pytest.fixture
def lost_lead(db, admin_user):
    l = Lead(
        first_name='Потерян',
        email='lost@corp.ru',
        client_type='b2b',
        status='lost',
    )
    db.session.add(l)
    db.session.commit()
    return l


class TestValidTransitions:
    def test_new_to_contacted(self, lead):
        """new → contacted разрешён."""
        assert lead.can_transition_to('contacted') is True

    def test_new_to_lost(self, lead):
        """new → lost разрешён."""
        assert lead.can_transition_to('lost') is True


class TestInvalidTransitions:
    def test_converted_to_new_is_forbidden(self, converted_lead):
        """converted → new запрещён."""
        assert converted_lead.can_transition_to('new') is False

    def test_converted_to_contacted_is_forbidden(self, converted_lead):
        """converted → contacted запрещён."""
        assert converted_lead.can_transition_to('contacted') is False

    def test_converted_to_qualified_is_forbidden(self, converted_lead):
        """converted → qualified запрещён."""
        assert converted_lead.can_transition_to('qualified') is False

    def test_lost_is_terminal(self, lost_lead):
        """lost → qualified запрещён."""
        assert lost_lead.can_transition_to('qualified') is False

    def test_transition_to_raises_on_invalid(self, converted_lead, admin_user):
        """transition_to() должен выбросить ValueError при запрещённом переходе."""
        with pytest.raises(ValueError, match='запрещён'):
            converted_lead.transition_to('new', changed_by_id=admin_user.id)


class TestTransitionHistory:
    def test_transition_records_history(self, db, lead, admin_user):
        """Переход статуса должен создавать запись в LeadHistory."""
        lead.transition_to('contacted', changed_by_id=admin_user.id, comment='Первый звонок')
        db.session.commit()

        history = db.session.scalars(
            db.select(LeadHistory).where(LeadHistory.lead_id == lead.id)
        ).all()

        assert len(history) == 1
        assert history[0].old_status == 'new'
        assert history[0].new_status == 'contacted'
        assert history[0].changed_by == admin_user.id
