"""
seed.py - заполнение базы демо-данными для МаркетПульс (профиль: АО БАРС Груп).

Запуск:
    python seed.py
    python seed.py --reset   # сначала очищает все данные

Создаёт:
    4 пользователя  (admin, marketing, sales, viewer)
    5 кампаний      (email, форум, тендеры, поиск, реферал)
    8 явных лидов + 82 генерируемых = 90 лидов
"""

import argparse
import random
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from faker import Faker
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.campaign import Campaign
from app.models.lead import Lead, LeadHistory

fake = Faker('ru_RU')
random.seed(42)
fake.seed_instance(42)

# ------------------------------------------------------------------------------
# Пользователи
# ------------------------------------------------------------------------------

USERS = [
    {'username': 'admin',     'email': 'admin@marketpulse.ru',     'full_name': 'Любовь Конькова',    'role': 'admin',     'password': '12345678'},
    {'username': 'marketing', 'email': 'marketing@marketpulse.ru', 'full_name': 'Мария Новикова',     'role': 'marketing', 'password': 'marketing123'},
    {'username': 'sales',     'email': 'sales@marketpulse.ru',     'full_name': 'Дмитрий Козлов',     'role': 'sales',     'password': 'sales123'},
    {'username': 'viewer',    'email': 'viewer@marketpulse.ru',    'full_name': 'Екатерина Лебедева', 'role': 'viewer',    'password': 'viewer123'},
]

# ------------------------------------------------------------------------------
# Кампании
# Важно для аналитики:
#   - Email стартует с ноября 2025 - чтобы 6-месячный график не имел пустых столбцов
#   - Тендеры: channel='tender' (отдельный канал в модели)
#   - Каждая не-черновая кампания получает хотя бы 1 явный конвертированный лид
# ------------------------------------------------------------------------------

CAMPAIGNS = [
    {
        'name':            'Email-рассылка: главврачи и ИТ-директора ЛПУ',
        'description':     'Прогревающая цепочка писем для руководителей ЛПУ и профильных ИТ-специалистов.',
        'status':          'active',
        'channel':         'email',
        'target_audience': 'b2g',
        'budget':          65000,
        'spent':           52400,
        'utm_source':      'email',
        'utm_medium':      'newsletter',
        'utm_campaign':    'email_lpu_2025_2026',
        'start_date':      datetime.date(2025, 11, 1),   # старт с ноября для графика
        'end_date':        datetime.date(2026, 4, 30),
    },
    {
        'name':            'Форум «Цифровое здравоохранение 2026»',
        'description':     'Участие в отраслевом форуме: стенд, доклады, нетворкинг с представителями региональных минздравов и ЛПУ.',
        'status':          'completed',
        'channel':         'other',
        'target_audience': 'b2g',
        'budget':          280000,
        'spent':           274500,
        'utm_source':      'event',
        'utm_medium':      'offline',
        'utm_campaign':    'event_zdrav_forum_2026',
        'start_date':      datetime.date(2025, 12, 10),  # старт с декабря для графика
        'end_date':        datetime.date(2026, 2, 28),
    },
    {
        'name':            'Тендеры: здравоохранение и образование',
        'description':     'Мониторинг и участие в закупках по 44-ФЗ и 223-ФЗ через ЕИС и Сбербанк-АСТ.',
        'status':          'active',
        'channel':         'tender',            # выделенный канал
        'target_audience': 'b2g',
        'budget':          120000,
        'spent':           58000,
        'utm_source':      'tender',
        'utm_medium':      'direct',
        'utm_campaign':    'tender_zdrav_edu_2026',
        'start_date':      datetime.date(2026, 1, 15),
        'end_date':        datetime.date(2026, 12, 31),
    },
    {
        'name':            'Яндекс.Директ: МИС и образовательные платформы',
        'description':     'Контекстная реклама по запросам о МИС, электронном журнале и цифровизации учреждений.',
        'status':          'paused',
        'channel':         'search',
        'target_audience': 'mixed',
        'budget':          150000,
        'spent':           87400,
        'utm_source':      'yandex',
        'utm_medium':      'cpc',
        'utm_campaign':    'search_mis_edu_2026',
        'start_date':      datetime.date(2026, 2, 10),
        'end_date':        datetime.date(2026, 6, 30),
    },
    {
        'name':            'Партнёрские продажи через интеграторов',
        'description':     'Привлечение клиентов через сеть региональных ИТ-партнёров и интеграторов.',
        'status':          'draft',
        'channel':         'referral',
        'target_audience': 'b2b',
        'budget':          50000,
        'spent':           0,                  # draft — ещё не тратили
        'utm_source':      'referral',
        'utm_medium':      'partner',
        'utm_campaign':    'referral_partners_2026',
        'start_date':      datetime.date(2026, 4, 1),
        'end_date':        datetime.date(2026, 12, 31),
    },
]

# ------------------------------------------------------------------------------
# Имена: русские + татарские с разделением по полу
# ------------------------------------------------------------------------------

TATAR_MALE_FIRST = [
    'Азат', 'Айрат', 'Айдар', 'Алмаз', 'Булат', 'Данияр', 'Зиннур',
    'Ильдар', 'Ильнар', 'Ильяс', 'Камил', 'Линар', 'Марат', 'Наиль',
    'Нияз', 'Радик', 'Рамиль', 'Ренат', 'Рустем', 'Тимур', 'Фарид', 'Шамиль',
]

TATAR_FEMALE_FIRST = [
    'Алсу', 'Альбина', 'Амина', 'Венера', 'Гузель', 'Диляра', 'Зульфия',
    'Зухра', 'Лейла', 'Лилия', 'Ляйсан', 'Миляуша', 'Нилуфар',
    'Регина', 'Резеда', 'Рузиля', 'Сабина', 'Танзиля', 'Чулпан',
    'Эльвира', 'Эльмира', 'Язгуль',
]

TATAR_MALE_LAST = [
    'Абдуллин', 'Ахметов', 'Валиев', 'Гарипов', 'Гафуров', 'Гизатуллин',
    'Галимов', 'Закиров', 'Зарипов', 'Зиятдинов', 'Каримов', 'Латыпов',
    'Мухаметзянов', 'Нигматуллин', 'Нуриев', 'Садыков', 'Сафин',
    'Фатхуллин', 'Фазлыев', 'Хайруллин', 'Хамидуллин', 'Хасанов',
    'Хузин', 'Шарипов', 'Яруллин',
]

TATAR_FEMALE_LAST = [
    'Абдуллина', 'Ахметова', 'Валиева', 'Гарипова', 'Гафурова', 'Гизатуллина',
    'Галимова', 'Закирова', 'Зарипова', 'Зиятдинова', 'Каримова', 'Латыпова',
    'Мухаметзянова', 'Нигматуллина', 'Нуриева', 'Садыкова', 'Сафина',
    'Фатхуллина', 'Фазлыева', 'Хайруллина', 'Хамидуллина', 'Хасанова',
    'Хузина', 'Шарипова', 'Яруллина',
]

# ------------------------------------------------------------------------------
# Справочники для генерации лидов
# ------------------------------------------------------------------------------

B2G_POSITIONS = [
    # ИТ и цифровизация (универсальные)
    'Начальник отдела информационных технологий',
    'Заместитель директора по цифровизации',
    'Начальник управления информатизации',
    'Директор по ИТ',
    'Руководитель проектов цифровизации',
    # Закупки (универсальные)
    'Руководитель контрактной службы',
    'Главный специалист по госзакупкам',
    'Специалист по тендерам',
    # Здравоохранение
    'Заместитель главного врача по АСУ',
    'Главный врач',
    # Финансы и экономика
    'Заместитель министра по цифровизации',
    'Начальник планово-экономического отдела',
    # Образование
    'Проректор по цифровому развитию',
]

B2B_POSITIONS = [
    'Директор по ИТ',
    'Технический директор',
    'Коммерческий директор',
    'Генеральный директор',
    'Руководитель отдела разработки',
    'Менеджер по работе с партнёрами',
    'Директор по развитию',
    'Операционный директор',
]

# B2G: здравоохранение, образование, госфинансы, соцзащита, ЖКХ, АПК
B2G_COMPANIES = [
    # Здравоохранение
    'ГБУЗ "ГКБ №7 им. Н.И. Пирогова"',
    'ГБУЗ "Республиканская клиническая больница"',
    'ГБУЗ "Областная клиническая больница №1"',
    'ГБУЗ "Городская поликлиника №13"',
    'ГБУЗ "Детская городская больница №3"',
    'ГБУЗ "Онкологический диспансер №2"',
    'Минздрав РТ',
    'Минздрав Новосибирской обл.',
    'Минздрав Свердловской обл.',
    'Департамент здравоохранения г. Москвы',
    'Комитет по здравоохранению СПб',
    # Образование
    'Минобрнауки РТ',
    'Департамент образования Новосибирской обл.',
    'ГБПОУ "Казанский медицинский колледж"',
    'ГБПОУ "Казанский строительный колледж"',
    'ГБОУ "Школа №1547"',
    'ГАОУ ВО "Московский политех"',
    'Казанский федеральный университет',
    # Госфинансы
    'Министерство финансов РТ',
    'Министерство финансов Новосибирской обл.',
    'Федеральное казначейство по РТ',
    'Министерство экономического развития РТ',
    # Цифровизация
    'Министерство цифрового развития РТ',
    'ГКУ "Центр информационных технологий РТ"',
    'ФКУ "Центр информационных технологий"',
    # Социальная защита
    'МБУ "Центр социального обслуживания населения"',
    'Министерство труда и соцзащиты РТ',
    # ЖКХ
    'МУП "Казанские энергетические системы"',
    'Комитет ЖКХ администрации г. Казани',
    # АПК
    'Министерство сельского хозяйства и продовольствия РТ',
    # Прочее
    'Администрация Вахитовского района г. Казани',
    'Комитет по госзакупкам СПб',
    'Управление Росреестра по Московской обл.',
]

# B2B: IT-интеграторы, частные клиники, агросектор, строительство
B2B_COMPANIES = [
    'ООО "СофтИнтегра"',
    'ООО "РегионИнтегро"',
    'ЗАО "ТехноМедиа"',
    'ООО "ПромИТ"',
    'АО "МедИнтегратор"',
    'ООО "ДигиталКлиник"',
    'ООО "МедикаПро"',
    'ООО "Клиника Здоровье Плюс"',
    'ООО "АльфаМед"',
    'ООО "ОбразованиеПлюс"',
    'АНО ДПО "Учебный центр Прогресс"',
    'ООО "АгроДигитал"',
    'АО "АгроТех"',
    'ООО "СтройАвтоматизация"',
    'АО "ЦифраСтрой"',
]

# Казань встречается чаще - штаб-квартира БАРС Груп
CITIES = [
    'Казань', 'Казань', 'Казань',
    'Москва', 'Москва',
    'Санкт-Петербург',
    'Новосибирск', 'Екатеринбург', 'Нижний Новгород',
    'Самара', 'Ростов-на-Дону', 'Краснодар',
    'Уфа', 'Томск', 'Красноярск', 'Калининград', 'Южно-Сахалинск',
]

NOTES_TEMPLATES = [
    'Запросил демо МИС на следующей неделе.',
    'Ждёт согласования бюджета у руководства.',
    'Уточняет требования по интеграции с ЕГИСЗ.',
    'Провели презентацию - позитивный настрой.',
    'Интересует модуль электронного журнала.',
    'Участвовал в форуме, подошёл к стенду.',
    'Конкурент предложил аналогичное решение.',
    'Готовится тендерная документация.',
    'Запросил КП с учётом 44-ФЗ.',
    'Хочет пилот на 3 месяца перед контрактом.',
    'Интересует облачная версия БАРС.МИС.',
    'Обсуждает переход с устаревшей системы.',
    'Нужна интеграция с региональной ЕГИСЗ.',
    'Запрашивает референсный список внедрений.',
    'Интересует система электронного документооборота.',
    'Рассматривает БАРС.Финансы для бюджетного учёта.',
    None,
]

# Российские домены для email (без западных)
RU_DOMAINS = ['yandex.ru', 'yandex.ru', 'mail.ru', 'mail.ru', 'gmail.com', 'bk.ru', 'inbox.ru']

# ------------------------------------------------------------------------------
# 8 явных лидов
# Распределены по кампаниям так, чтобы каждая не-черновая кампания
# имела хотя бы 1 converted лид -> revenue > 0 -> ROI считается корректно
# Индексы кампаний: 0=email, 1=forum, 2=tender, 3=search, 4=referral(draft)
# ------------------------------------------------------------------------------

EXPLICIT_LEADS = [
    # 1. Здравоохранение, Казань | email -> CONVERTED (даёт revenue для CPL/ROI email)
    {
        'first_name': 'Сергей',
        'last_name':  'Михайлов',
        'email':      's.mihaylov@gkb7.kazan.ru',
        'phone':      '+7 843 555-01-01',
        'position':   'Заместитель главного врача по АСУ',
        'company':    'ГБУЗ "ГКБ №7 им. Н.И. Пирогова"',
        'inn':        '1655123456',
        'city':       'Казань',
        'client_type': 'b2g',
        'source':     'form',
        'campaign_idx': 0,
        'notes':      'Запросил демо МИС на следующей неделе.',
        'final_status': 'converted',
        'created_at': datetime.datetime(2025, 11, 20, 10, 30),
    },
    # 2. Здравоохранение, Казань (татарское имя) | forum -> CONVERTED (revenue для форума)
    {
        'first_name': 'Ильнур',
        'last_name':  'Хайруллин',
        'email':      'i.hajrullin@minzdrav-rt.ru',
        'phone':      '+7 843 555-02-02',
        'position':   'Начальник отдела информатизации',
        'company':    'Минздрав РТ',
        'inn':        '1655654321',
        'city':       'Казань',
        'client_type': 'b2g',
        'source':     'manual',
        'campaign_idx': 1,
        'notes':      'Участвовал в форуме, подошёл к стенду.',
        'final_status': 'converted',
        'created_at': datetime.datetime(2025, 12, 18, 14, 0),
    },
    # 3. Образование, Казань | tender -> CONVERTED (revenue для тендеров)
    {
        'first_name': 'Андрей',
        'last_name':  'Волков',
        'email':      'a.volkov@kmk.kazan.ru',
        'phone':      '+7 843 555-03-03',
        'position':   'Руководитель контрактной службы',
        'company':    'ГБПОУ "Казанский медицинский колледж"',
        'inn':        '1655789012',
        'city':       'Казань',
        'client_type': 'b2g',
        'source':     'landing',
        'campaign_idx': 2,
        'notes':      'Запросил КП с учётом 44-ФЗ.',
        'final_status': 'converted',
        'created_at': datetime.datetime(2026, 1, 20, 9, 15),
    },
    # 4. Образование, Новосибирск (татарское имя) | search -> new
    {
        'first_name': 'Диляра',
        'last_name':  'Зиятдинова',
        'email':      'd.ziyatdinova@edu.novosibirsk.ru',
        'phone':      '+7 383 555-04-04',
        'position':   'Заместитель директора по цифровизации',
        'company':    'Департамент образования Новосибирской обл.',
        'inn':        '5406345678',
        'city':       'Новосибирск',
        'client_type': 'b2g',
        'source':     'form',
        'campaign_idx': 3,
        'notes':      'Уточняет требования по интеграции с ЕГИСЗ.',
        'final_status': 'new',
        'created_at': datetime.datetime(2026, 3, 1, 11, 0),
    },
    # 5. Здравоохранение, Екатеринбург | tender -> lost
    {
        'first_name': 'Виктор',
        'last_name':  'Соколов',
        'email':      'v.sokolov@okb1.ekb.ru',
        'phone':      '+7 343 555-05-05',
        'position':   'Главный специалист по госзакупкам',
        'company':    'ГБУЗ "Областная клиническая больница №1"',
        'inn':        '6658901234',
        'city':       'Екатеринбург',
        'client_type': 'b2g',
        'source':     'import',
        'campaign_idx': 2,
        'notes':      'Готовится тендерная документация.',
        'final_status': 'lost',
        'created_at': datetime.datetime(2026, 1, 25, 16, 45),
    },
    # 6. Госфинансы, Казань (татарское имя) | search -> CONVERTED (revenue для поиска)
    {
        'first_name': 'Айрат',
        'last_name':  'Латыпов',
        'email':      'a.latypov@minfin-rt.ru',
        'phone':      '+7 843 555-06-06',
        'position':   'Начальник отдела информационных технологий',
        'company':    'Министерство финансов РТ',
        'inn':        '1654567890',
        'city':       'Казань',
        'client_type': 'b2g',
        'source':     'landing',
        'campaign_idx': 3,
        'notes':      'Рассматривает БАРС.Финансы для бюджетного учёта.',
        'final_status': 'converted',
        'created_at': datetime.datetime(2026, 2, 18, 12, 0),
    },
    # 7. IT-интегратор, Санкт-Петербург | referral -> contacted
    {
        'first_name': 'Елена',
        'last_name':  'Захарова',
        'email':      'e.zaharova@softintegra.ru',
        'phone':      '+7 812 555-07-07',
        'position':   'Коммерческий директор',
        'company':    'ООО "СофтИнтегра"',
        'inn':        '7810987654',
        'city':       'Санкт-Петербург',
        'client_type': 'b2b',
        'source':     'manual',
        'campaign_idx': 4,
        'notes':      'Обсуждает переход с устаревшей системы.',
        'final_status': 'contacted',
        'created_at': datetime.datetime(2026, 4, 3, 10, 30),
    },
    # 8. Агросектор, Краснодар | referral -> new
    {
        'first_name': 'Ольга',
        'last_name':  'Черных',
        'email':      'o.chernyh@agrodigital.ru',
        'phone':      '+7 861 555-08-08',
        'position':   'Директор по цифровизации',
        'company':    'ООО "АгроДигитал"',
        'inn':        '2308123456',
        'city':       'Краснодар',
        'client_type': 'b2b',
        'source':     'form',
        'campaign_idx': 4,
        'notes':      'Хочет пилот на 3 месяца перед контрактом.',
        'final_status': 'new',
        'created_at': datetime.datetime(2026, 4, 5, 9, 0),
    },
]

# ------------------------------------------------------------------------------
# Вспомогательные функции
# ------------------------------------------------------------------------------

_TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _translit(text):
    return ''.join(_TRANSLIT_MAP.get(c, c) for c in text.lower())


def _make_inn(client_type):
    length = 10 if client_type == 'b2g' else random.choice([10, 12])
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])


def _make_name_pair():
    """Возвращает (имя, фамилия) с согласованием по роду. ~25% татарские."""
    use_tatar = random.random() < 0.25
    is_male   = random.random() < 0.55
    if use_tatar:
        if is_male:
            return random.choice(TATAR_MALE_FIRST), random.choice(TATAR_MALE_LAST)
        else:
            return random.choice(TATAR_FEMALE_FIRST), random.choice(TATAR_FEMALE_LAST)
    else:
        if is_male:
            return fake.first_name_male(), fake.last_name_male()
        else:
            return fake.first_name_female(), fake.last_name_female()


def _make_email(first_name, last_name):
    """Транслитерирует имя и фамилию, подставляет российский домен."""
    f      = _translit(first_name[0])
    l      = _translit(last_name)
    suffix = str(random.randint(1, 99)) if random.random() < 0.35 else ''
    return f"{f}.{l}{suffix}@{random.choice(RU_DOMAINS)}"


def _make_lead(campaigns, sales_users, admin_user):
    client_type = random.choices(['b2b', 'b2g'], weights=[35, 65])[0]

    suitable = [c for c in campaigns if c.target_audience in (client_type, 'mixed')]
    campaign  = random.choice(suitable) if suitable else random.choice(campaigns)

    if client_type == 'b2g':
        company  = random.choice(B2G_COMPANIES)
        position = random.choice(B2G_POSITIONS)
    else:
        company  = random.choice(B2B_COMPANIES)
        position = random.choice(B2B_POSITIONS)

    first_name, last_name = _make_name_pair()
    email = _make_email(first_name, last_name)

    start = campaign.start_date or datetime.date(2025, 11, 1)
    end   = min(campaign.end_date or datetime.date(2026, 4, 15), datetime.date(2026, 4, 15))
    if start > end:
        start = end - datetime.timedelta(days=30)
    delta_days     = (end - start).days or 1
    created_offset = random.randint(0, delta_days)
    created_at     = datetime.datetime.combine(
        start + datetime.timedelta(days=created_offset),
        datetime.time(random.randint(8, 18), random.randint(0, 59))
    )

    assignee = random.choice(sales_users + [None, None])

    return Lead(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=fake.phone_number()[:20],
        position=position,
        company=company,
        inn=_make_inn(client_type),
        city=random.choice(CITIES),
        client_type=client_type,
        source=random.choice(['landing', 'form', 'import', 'manual']),
        utm_source=campaign.utm_source,
        utm_medium=campaign.utm_medium,
        utm_campaign=campaign.utm_campaign,
        notes=random.choice(NOTES_TEMPLATES),
        campaign_id=campaign.id,
        assigned_to=assignee.id if assignee else None,
        created_at=created_at,
        status='new',
        score=0,
    )


def _build_history(lead, admin_id, sales_id):
    transitions    = []
    current_status = 'new'
    current_time   = lead.created_at
    changer_id     = random.choice([admin_id, sales_id])

    def advance(old, new, days_min=1, days_max=10):
        nonlocal current_time
        current_time += datetime.timedelta(
            days=random.randint(days_min, days_max),
            hours=random.randint(0, 8)
        )
        transitions.append((old, new, current_time, changer_id))
        return new

    r = random.random()
    if r < 0.12:
        current_status = advance('new', 'lost', 1, 5)
    elif r < 0.25:
        pass  # остался в new
    else:
        current_status = advance('new', 'contacted', 1, 7)
        r2 = random.random()
        if r2 < 0.15:
            current_status = advance('contacted', 'lost', 1, 5)
        elif r2 < 0.30:
            pass  # завис в contacted
        else:
            current_status = advance('contacted', 'qualified', 2, 10)
            r3 = random.random()
            if r3 < 0.20:
                current_status = advance('qualified', 'lost', 1, 7)
            elif r3 < 0.40:
                pass  # завис в qualified
            else:
                current_status = advance('qualified', 'converted', 3, 14)

    return current_status, transitions, current_time


def _build_explicit_history(lead, final_status, changer_id):
    """Строит историю переходов для явных лидов с фиксированными интервалами."""
    STATUS_CHAIN = ['new', 'contacted', 'qualified', 'converted']
    DAY_OFFSETS  = [4, 7, 10]
    transitions  = []
    current_time = lead.created_at

    if final_status == 'new':
        return 'new', [], current_time

    if final_status == 'lost':
        current_time += datetime.timedelta(days=5, hours=3)
        transitions.append(('new', 'lost', current_time, changer_id))
        return 'lost', transitions, current_time

    target_idx = STATUS_CHAIN.index(final_status)
    for i in range(target_idx):
        current_time += datetime.timedelta(days=DAY_OFFSETS[i], hours=2)
        transitions.append((STATUS_CHAIN[i], STATUS_CHAIN[i + 1], current_time, changer_id))

    return final_status, transitions, current_time


def _calc_score(lead, final_status):
    score = 0
    if lead.company:        score += 20
    if lead.inn:            score += 15
    if lead.phone:          score += 10
    if lead.position:       score += 10
    if lead.city:           score += 5
    if lead.decision_maker_name: score += 15
    if final_status in ('qualified', 'converted'): score += 20
    elif final_status == 'contacted':              score += 10
    if lead.client_type == 'b2g':                 score += 5
    return max(0, min(100, score + random.randint(-5, 10)))


# ------------------------------------------------------------------------------
# Главная функция
# ------------------------------------------------------------------------------

def seed(reset=False):
    app = create_app('development')
    with app.app_context():

        if reset:
            print('Очистка данных...')
            LeadHistory.query.delete()
            Lead.query.delete()
            Campaign.query.delete()
            User.query.delete()
            db.session.commit()
            print('  OK: данные очищены')

        # Пользователи
        print('\nСоздание пользователей...')
        user_map = {}
        for u_data in USERS:
            existing = User.query.filter_by(username=u_data['username']).first()
            if existing:
                print(f"  ~ {u_data['username']} уже существует, пропускаем")
                user_map[u_data['role']] = existing
                continue
            user = User(
                username=u_data['username'],
                email=u_data['email'],
                full_name=u_data['full_name'],
                role=u_data['role'],
                is_active=True,
                is_approved=True,
            )
            user.set_password(u_data['password'])
            db.session.add(user)
            user_map[u_data['role']] = user
            print(f"  + {u_data['username']} ({u_data['role']}) / {u_data['password']}")

        db.session.flush()

        # Кампании
        print('\nСоздание кампаний...')
        campaigns      = []
        admin_user     = user_map['admin']
        marketing_user = user_map['marketing']

        for i, c_data in enumerate(CAMPAIGNS):
            existing = Campaign.query.filter_by(name=c_data['name']).first()
            if existing:
                print(f"  ~ «{c_data['name']}» уже существует, пропускаем")
                campaigns.append(existing)
                continue
            creator  = admin_user if i % 2 == 0 else marketing_user
            campaign = Campaign(
                name=c_data['name'],
                description=c_data.get('description'),
                status=c_data['status'],
                channel=c_data['channel'],
                target_audience=c_data['target_audience'],
                budget=c_data['budget'],
                spent=c_data['spent'],
                utm_source=c_data.get('utm_source'),
                utm_medium=c_data.get('utm_medium'),
                utm_campaign=c_data.get('utm_campaign'),
                start_date=c_data.get('start_date'),
                end_date=c_data.get('end_date'),
                created_by=creator.id,
            )
            db.session.add(campaign)
            campaigns.append(campaign)
            print(f"  + \"{c_data['name']}\" [{c_data['status']}]")

        db.session.flush()

        # Лиды
        print('\nСоздание лидов...')
        sales_users   = [user_map['sales'], admin_user]
        status_counts = {s: 0 for s in ('new', 'contacted', 'qualified', 'converted', 'lost')}
        total         = 0

        # 8 явных лидов
        print('  Явные лиды:')
        for e in EXPLICIT_LEADS:
            campaign = campaigns[e['campaign_idx']]
            lead = Lead(
                first_name=e['first_name'],
                last_name=e['last_name'],
                email=e['email'],
                phone=e['phone'],
                position=e['position'],
                company=e['company'],
                inn=e['inn'],
                city=e['city'],
                client_type=e['client_type'],
                source=e['source'],
                utm_source=campaign.utm_source,
                utm_medium=campaign.utm_medium,
                utm_campaign=campaign.utm_campaign,
                notes=e['notes'],
                campaign_id=campaign.id,
                assigned_to=user_map['sales'].id,
                created_at=e['created_at'],
                status='new',
                score=0,
            )
            db.session.add(lead)
            db.session.flush()

            final_status, transitions, last_time = _build_explicit_history(
                lead, e['final_status'], admin_user.id
            )
            lead.status            = final_status
            lead.status_changed_at = last_time if transitions else lead.created_at

            if final_status == 'converted':
                lead.converted_at = last_time
                lead.deal_amount  = (
                    round(random.uniform(500000, 2500000), 2)
                    if lead.client_type == 'b2g'
                    else round(random.uniform(150000, 600000), 2)
                )

            lead.score = _calc_score(lead, final_status)

            for (old_s, new_s, ts, changer_id) in transitions:
                db.session.add(LeadHistory(
                    lead_id=lead.id,
                    old_status=old_s,
                    new_status=new_s,
                    changed_by=changer_id,
                    created_at=ts,
                ))

            status_counts[final_status] += 1
            total += 1
            print(f"    + {e['first_name']} {e['last_name']} [{final_status}]")

        # 82 генерируемых лида
        print('  Генерируемые лиды...')
        for _ in range(82):
            lead = _make_lead(campaigns, sales_users, admin_user)
            db.session.add(lead)
            db.session.flush()

            final_status, transitions, last_time = _build_history(
                lead, admin_user.id, user_map['sales'].id
            )
            lead.status            = final_status
            lead.status_changed_at = last_time if transitions else lead.created_at

            if final_status == 'converted':
                lead.converted_at = last_time
                lead.deal_amount  = (
                    round(random.uniform(500000, 2500000), 2)
                    if lead.client_type == 'b2g'
                    else round(random.uniform(150000, 600000), 2)
                )

            lead.score = _calc_score(lead, final_status)

            for (old_s, new_s, ts, changer_id) in transitions:
                db.session.add(LeadHistory(
                    lead_id=lead.id,
                    old_status=old_s,
                    new_status=new_s,
                    changed_by=changer_id,
                    created_at=ts,
                ))

            status_counts[final_status] += 1
            total += 1

        db.session.commit()
        print(f'\n  Итого лидов: {total}')
        for status, cnt in status_counts.items():
            print(f'    {status:12s}: {cnt}')

        print('\nГотово!')
        print('\nУчётные данные:')
        for u in USERS:
            print(f"  {u['username']:12s} / {u['password']:15s}  ({u['role']})")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed демо-данных МаркетПульс')
    parser.add_argument('--reset', action='store_true',
                        help='Очистить таблицы перед заполнением')
    args = parser.parse_args()
    seed(reset=args.reset)
