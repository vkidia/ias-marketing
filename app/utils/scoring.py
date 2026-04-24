"""
Lead Scoring — шкала 0–100.
Вызывается перед каждым db.session.commit() при создании/обновлении лида.
"""

# Публичные почтовые сервисы не дают информации об организации, поэтому снижают ценность лида
FREE_EMAIL_DOMAINS = {'gmail.com', 'mail.ru', 'yandex.ru', 'yahoo.com', 'hotmail.com', 'outlook.com'}
# Домены государственных органов, их наличие повышает B2G оценку
GOV_DOMAINS = {'.gov.ru', '.mos.ru', '.gosuslugi.ru', '.edu.ru'}

# Баллы за канал привлечения: search и tender самые ценные, display и other слабее
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
    Рассчитать скоринг лида по набору признаков.
    Принимает объект Lead (или dict-подобный).
    Возвращает int 0-100.
    """
    score = 0

    # заполненность контактных данных говорит о реальности лида
    if lead.email:
        score += 10
    if lead.phone:
        score += 10
    if lead.company:
        score += 5
    if lead.position:
        score += 5

    # если известен ЛПР (лицо принимающее решения), вероятность сделки выше
    if lead.decision_maker_name:
        score += 10
    if lead.decision_maker_position:
        score += 5

    # landing и form означают осознанный интерес, import и manual менее тёплые
    source_map = {'landing': 20, 'form': 15, 'import': 10, 'manual': 5}
    if lead.source and lead.source in source_map:
        score += source_map[lead.source]

    # наличие UTM-меток говорит о том что лид пришёл по отслеживаемой рекламе
    if lead.utm_source:
        score += 5
    if lead.utm_medium:
        score += 5
    if lead.utm_campaign:
        score += 5

    # канал кампании тоже влияет на качество
    if lead.campaign and lead.campaign.channel:
        score += CHANNEL_SCORES.get(lead.campaign.channel, 0)

    # корпоративный email повышает доверие к лиду
    if lead.email:
        domain = lead.email.split('@')[-1].lower()
        if domain not in FREE_EMAIL_DOMAINS:
            score += 10

    # B2G: client_type
    # Для лендинг-лидов тип выставляется либо самим клиентом, либо автоматически
    # по gov-домену email ещё до вызова scoring (см. api/routes.py).
    if lead.client_type == 'b2g':
        score += 15
    if lead.inn:
        score += 5

    return min(score, 100)


def update_lead_score(lead):
    """Пересчитать и сохранить score в объект лида (без commit)."""
    lead.score = calculate_score(lead)