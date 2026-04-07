"""
Lead Scoring — шкала 0–100.
Вызывается перед каждым db.session.commit() при создании/обновлении лида.
"""

FREE_EMAIL_DOMAINS = {'gmail.com', 'mail.ru', 'yandex.ru', 'yahoo.com', 'hotmail.com', 'outlook.com'}
GOV_DOMAINS = {'.gov.ru', '.mos.ru', '.gosuslugi.ru', '.edu.ru'}

CHANNEL_SCORES = {
    'search':   20,
    'referral': 18,
    'email':    15,
    'social':   12,
    'display':   8,
    'tender':   20,  # tender = B2G, приравниваем к search
    'other':     5,
}


def calculate_score(lead) -> int:
    """
    Принимает объект Lead (или dict-подобный).
    Возвращает int 0–100.
    """
    score = 0

    # контактные данные 
    if lead.email:
        score += 10
    if lead.phone:
        score += 10
    if lead.company:
        score += 5
    if lead.position:
        score += 5

    # ЛПР
    if lead.decision_maker_name:
        score += 10
    if lead.decision_maker_position:
        score += 5

    # источник 
    source_map = {'landing': 20, 'form': 15, 'import': 10, 'manual': 5}
    if lead.source and lead.source in source_map:
        score += source_map[lead.source]

    # UTM
    if lead.utm_source:
        score += 5
    if lead.utm_medium:
        score += 5
    if lead.utm_campaign:
        score += 5

    # канал кампании
    if lead.campaign and lead.campaign.channel:
        score += CHANNEL_SCORES.get(lead.campaign.channel, 0)

    # email-анализ
    if lead.email:
        domain = lead.email.split('@')[-1].lower()
        if domain not in FREE_EMAIL_DOMAINS:
            score += 10  # корпоративный email

    # B2G признаки
    if lead.client_type == 'b2g':
        score += 15
    if lead.email:
        domain = lead.email.split('@')[-1].lower()
        if any(domain.endswith(gov) for gov in GOV_DOMAINS):
            score += 10
    if lead.inn:
        score += 5

    return min(score, 100)


def update_lead_score(lead):
    """Пересчитать и сохранить score в объект лида (без commit)."""
    lead.score = calculate_score(lead)