"""
test_scoring.py — тесты алгоритма скоринга лидов.
Полный лид → высокий score, минимальный лид → низкий score.
"""
from types import SimpleNamespace

import pytest
from app.utils.scoring import calculate_score


def make_lead(**kwargs):
    defaults = dict(
        email=None, phone=None, company=None, position=None,
        decision_maker_name=None, decision_maker_position=None,
        source=None,
        utm_source=None, utm_medium=None, utm_campaign=None,
        campaign=None,
        client_type='b2b',
        inn=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_campaign(channel='search'):
    return SimpleNamespace(channel=channel)


class TestFullVsMinimalLead:
    def test_full_lead_high_score(self):
        """Лид со всеми полями должен получить высокий score."""
        lead = make_lead(
            email='director@company.gov.ru',
            phone='+79001234567',
            company='ООО Ромашка',
            position='Менеджер',
            decision_maker_name='Иванов И.И.',
            decision_maker_position='Директор',
            source='landing',
            utm_source='google', utm_medium='cpc', utm_campaign='spring',
            campaign=make_campaign('search'),
            client_type='b2g',
            inn='7743013722',
        )
        score = calculate_score(lead)
        assert score >= 85, f"Ожидался score ≥ 85, получен {score}"

    def test_minimal_lead_low_score(self):
        """Лид только с обязательным email — низкий score."""
        lead = make_lead(email='user@gmail.com')
        score = calculate_score(lead)
        assert score <= 15, f"Ожидался score ≤ 15, получен {score}"


class TestEmailDomainBonus:
    def test_free_email_no_domain_bonus(self):
        """Gmail / Yandex / mail.ru не дают бонус за корпоративный домен."""
        for free_email in ('test@gmail.com', 'test@yandex.ru', 'test@mail.ru'):
            lead_free = make_lead(email=free_email)
            lead_corp = make_lead(email='test@company.ru')
            assert calculate_score(lead_corp) > calculate_score(lead_free), \
                f"Корпоративный email должен давать бонус vs {free_email}"

    def test_corporate_email_bonus(self):
        """Корпоративный email добавляет +10 к score."""
        lead_corp = make_lead(email='ceo@bigcorp.ru')
        lead_free = make_lead(email='ceo@gmail.com')
        assert calculate_score(lead_corp) - calculate_score(lead_free) == 10


class TestB2GBonus:
    def test_b2g_client_type_bonus(self):
        """client_type=b2g добавляет +15 vs b2b при прочих равных."""
        lead_b2g = make_lead(email='x@corp.ru', client_type='b2g')
        lead_b2b = make_lead(email='x@corp.ru', client_type='b2b')
        assert calculate_score(lead_b2g) - calculate_score(lead_b2b) == 15

    def test_gov_domain_bonus(self):
        """Государственный домен (.gov.ru) даёт +10 к score."""
        lead_gov = make_lead(email='user@agency.gov.ru', client_type='b2b')
        lead_reg = make_lead(email='user@agency.com',    client_type='b2b')
        assert calculate_score(lead_gov) - calculate_score(lead_reg) == 10
