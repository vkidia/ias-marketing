"""DSS (Decision Support System) — единая функция рекомендаций для всех режимов выборки."""

# минимум лидов для статистики по конверсии и потерям
_MIN_LEADS = 5

# порядок уровней для сортировки: сначала самые критичные
_LEVEL_ORDER = {'danger': 0, 'warning': 1, 'info': 2, 'success': 3}

# пороги стагнации: дней без движения по стадии до алерта
_STAGNATION_DAYS = {'contacted': 14, 'qualified': 21}

# максимум именных алертов по кампаниям до сворачивания остальных
_MAX_CAMPAIGN_ALERTS = 3


def _sort(dss):
    dss.sort(key=lambda r: _LEVEL_ORDER.get(r['level'], 2))
    return dss


def compute_dss(
    mode,
    funnel,
    total_leads,
    roi,
    cr,
    *,
    # бюджет — для single-режима
    spent=None,
    budget=None,
    # портфельные — для all/group
    active_count=None,
    campaign_count=None,
    campaign_alerts=None,
    # контекст аудитории
    b2g_ratio=0.0,
    # зрелость кампании — только single
    campaign_age_days=None,
    # здоровье лидов (все режимы)
    sla_breach=0,
    stagnant_contacted=0,
    stagnant_qualified=0,
    unassigned=0,
    missing_amounts=0,
    # узкие места воронки (все режимы)
    funnel_steps=None,
):
    """
    Единая точка DSS. mode: 'single' | 'group' | 'all'.

    funnel_steps: {'new_contacted': float, 'contacted_qualified': float,
                   'qualified_converted': float} — доли переходов 0..1.
    campaign_alerts: список именных алертов из collect_campaign_alerts().
    """
    dss = []

    # 1. Нет лидов вообще 
    if total_leads == 0:
        dss.append({
            'level': 'info', 'icon': 'bi-info-circle',
            'title': 'Нет лидов' + (' в кампании' if mode == 'single' else ' в системе'),
            'text': 'Добавьте лиды или настройте источник привлечения заявок.',
        })
        # ранний выход — остальные проверки бессмысленны
        return dss

    # 2. Бюджет (только single)
    if mode == 'single' and budget and spent:
        if spent > budget:
            pct = round(spent / budget * 100)
            dss.append({
                'level': 'danger', 'icon': 'bi-wallet2',
                'title': f'Бюджет превышен - потрачено {pct}%',
                'text': 'Расходы вышли за рамки установленного бюджета. Проверьте финансирование кампании.',
            })
        elif spent > budget * 0.85:
            pct = round(spent / budget * 100)
            dss.append({
                'level': 'warning', 'icon': 'bi-wallet2',
                'title': f'Бюджет почти исчерпан — {pct}%',
                'text': 'Осталось менее 15% бюджета. Подготовьте решение о продлении или завершении кампании.',
            })

    # 3. Конверсия 
    if total_leads >= _MIN_LEADS and cr is not None:
        # B2G аудитория — смягчаем пороги и объясняем контекст
        if b2g_ratio > 0.6:
            cr_danger  = 2
            cr_warning = 8
        else:
            cr_danger  = 5
            cr_warning = 15

        # Для молодой кампании (< 21 дня) подавляем CR-предупреждения
        age_too_young = mode == 'single' and campaign_age_days is not None and campaign_age_days < 21

        if not age_too_young:
            if cr < cr_danger:
                dss.append({
                    'level': 'danger', 'icon': 'bi-exclamation-triangle-fill',
                    'title': f'Критически низкая конверсия — {cr}%',
                    'text': f'Менее {cr_danger}% лидов доходят до сделки. '
                            'Проверьте качество входящих заявок и скрипты обработки.',
                })
            elif cr < cr_warning:
                dss.append({
                    'level': 'warning', 'icon': 'bi-exclamation-circle',
                    'title': f'Конверсия ниже нормы — {cr}%',
                    'text': f'Норма для B2B — от {cr_warning}%. '
                            'Усильте квалификацию лидов и работу с ЛПР.',
                })
        else:
            dss.append({
                'level': 'info', 'icon': 'bi-clock-history',
                'title': f'Кампания запущена {campaign_age_days} дн. назад',
                'text': 'Статистика конверсии ещё формируется. '
                        'Оценка CR будет доступна после 21 дня работы.',
            })

    # 4. Потери лидов 
    if total_leads >= _MIN_LEADS:
        lost_pct = round(funnel.get('lost', 0) / total_leads * 100, 1)
        if lost_pct > 40:
            dss.append({
                'level': 'warning', 'icon': 'bi-funnel',
                'title': f'{lost_pct}% лидов теряется',
                'text': 'Слишком много лидов уходит со статусом «Потерян». '
                        'Проанализируйте причины отказов.',
            })

    # 5. ROI
    roi_alert_fired = False
    if roi is not None and roi < 0:
        if mode == 'single':
            # для одной кампании градуируем по расходу бюджета
            if budget and spent and spent > budget * 0.5:
                dss.append({
                    'level': 'danger', 'icon': 'bi-graph-down-arrow',
                    'title': f'Кампания убыточна — ROI {roi}%',
                    'text': 'Потрачено более 50% бюджета при отрицательном ROI. '
                            'Рассмотрите приостановку.',
                })
            else:
                dss.append({
                    'level': 'warning', 'icon': 'bi-graph-down-arrow',
                    'title': f'Отрицательный ROI — {roi}%',
                    'text': 'Затраты пока не окупаются. Следите за динамикой конверсий.',
                })
        else:
            dss.append({
                'level': 'danger', 'icon': 'bi-graph-down-arrow',
                'title': f'Средний ROI отрицательный — {roi}%',
                'text': 'Маркетинговые затраты не окупаются в среднем по портфелю. '
                        'Пересмотрите бюджеты или приостановите убыточные кампании.',
            })
            roi_alert_fired = True

    # 6. Нет активных кампаний (all / group) 
    if mode == 'all' and active_count == 0:
        dss.append({
            'level': 'warning', 'icon': 'bi-megaphone',
            'title': 'Нет активных кампаний',
            'text': 'Запустите хотя бы одну кампанию для генерации новых лидов.',
        })
    elif mode == 'group' and active_count == 0:
        dss.append({
            'level': 'info', 'icon': 'bi-megaphone',
            'title': 'В выборке нет активных кампаний',
            'text': 'Все выбранные кампании завершены или приостановлены — '
                    'данные отражают историческую статистику.',
        })

    # 7. SLA breach — лиды > 24 ч в статусе «Новый» 
    if sla_breach > 0:
        level = 'danger' if sla_breach > 5 else 'warning'
        dss.append({
            'level': level, 'icon': 'bi-alarm',
            'title': f'{sla_breach} лид{"ов" if sla_breach > 4 else "а" if sla_breach > 1 else ""} не обработан{"о" if sla_breach > 1 else ""} более 24 часов',
            'text': 'Быстрая реакция критична в B2B. '
                    'Назначьте ответственных и свяжитесь с лидами немедленно.',
        })

    #  8. Стагнация по стадиям 
    if stagnant_contacted > 0:
        dss.append({
            'level': 'warning', 'icon': 'bi-hourglass-split',
            'title': f'{stagnant_contacted} лид{"ов" if stagnant_contacted > 4 else "а" if stagnant_contacted > 1 else ""} завис{"ло" if stagnant_contacted > 1 else ""} на стадии «На связи»',
            'text': f'Без движения более {_STAGNATION_DAYS["contacted"]} дней. '
                    'Проведите повторный контакт или закройте неперспективные заявки.',
        })
    if stagnant_qualified > 0:
        dss.append({
            'level': 'warning', 'icon': 'bi-hourglass-split',
            'title': f'{stagnant_qualified} квалифицированн{"ых" if stagnant_qualified > 1 else "ый"} лид{"ов" if stagnant_qualified > 4 else "а" if stagnant_qualified > 1 else ""} без продвижения',
            'text': f'Более {_STAGNATION_DAYS["qualified"]} дней в стадии «Квалифицирован». '
                    'Передайте в продажи или проведите встречу с ЛПР.',
        })

    # 9. Нераспределённые лиды 
    if unassigned > 0:
        dss.append({
            'level': 'warning', 'icon': 'bi-person-x',
            'title': f'{unassigned} активн{"ых" if unassigned > 1 else "ый"} лид{"ов" if unassigned > 4 else "а" if unassigned > 1 else ""} без ответственного',
            'text': 'Лиды без назначенного менеджера часто теряются. '
                    'Распределите их немедленно.',
        })

    # 10. Сделки без суммы — ROI ненадёжен 
    if missing_amounts > 0:
        dss.append({
            'level': 'info', 'icon': 'bi-currency-exchange',
            'title': f'{missing_amounts} закрыт{"ых" if missing_amounts > 1 else "ая"} сделк{"и" if missing_amounts > 4 else "а" if missing_amounts > 1 else "а"} без суммы',
            'text': 'ROI рассчитывается только по сделкам с заполненной суммой. '
                    'Внесите суммы для точного расчёта.',
        })

    # 11. Узкое место воронки (из LeadHistory) 
    if funnel_steps:
        steps = [
            ('new_contacted',       'new → contacted',       'первого касания — лиды остаются необработанными'),
            ('contacted_qualified', 'contacted → qualified', 'квалификации — мало лидов проходят отбор'),
            ('qualified_converted', 'qualified → converted', 'закрытия — квалифицированные лиды не доходят до сделки'),
        ]
        # находим худший шаг с достаточной статистикой
        worst_key, worst_label, worst_desc, worst_rate = None, None, None, 1.0
        for key, label, desc in steps:
            rate = funnel_steps.get(key)
            if rate is not None and rate < worst_rate:
                worst_key, worst_label, worst_desc, worst_rate = key, label, desc, rate

        if worst_key and worst_rate < 0.30:
            pct = round(worst_rate * 100)
            dss.append({
                'level': 'warning', 'icon': 'bi-filter-circle',
                'title': f'Узкое место: {worst_label} — {pct}% переходов',
                'text': f'Основные потери на этапе {worst_desc}. '
                        'Проработайте скрипты и процессы на этом шаге.',
            })

    # 12. Именные алерты по кампаниям (all / group)
    if campaign_alerts is not None:
        # дедупликация: если ROI-алерт портфеля уже есть — убираем дублирующие ROI-алерты кампаний
        if roi_alert_fired:
            shown = [a for a in campaign_alerts if 'graph' not in a['icon'].lower()]
        else:
            shown = list(campaign_alerts)

        # кап: максимум _MAX_CAMPAIGN_ALERTS именных алертов, остальные сворачиваем
        if len(shown) > _MAX_CAMPAIGN_ALERTS:
            overflow = len(shown) - _MAX_CAMPAIGN_ALERTS
            dss.extend(shown[:_MAX_CAMPAIGN_ALERTS])
            dss.append({
                'level': shown[_MAX_CAMPAIGN_ALERTS]['level'],
                'icon': 'bi-three-dots',
                'title': f'Ещё {overflow} кампани{"я" if overflow == 1 else "и" if overflow < 5 else "й"} с аналогичными проблемами',
                'text': 'Откройте каждую кампанию отдельно для детального анализа.',
            })
        else:
            dss.extend(shown)

    # 13. Всё в норме
    if not dss:
        label = 'Кампания работает эффективно' if mode == 'single' else 'Всё в норме'
        dss.append({
            'level': 'success', 'icon': 'bi-check-circle-fill',
            'title': label,
            'text': 'Ключевые показатели в допустимых пределах. Продолжайте в том же темпе!',
        })
    else:
        _sort(dss)

    return dss


def collect_campaign_alerts(campaigns, roi_by_id=None):
    """
    Собирает именные алерты по бюджету и ROI для списка кампаний.
    Вызывается из роутов перед compute_dss(); результат передаётся в campaign_alerts.
    """
    alerts = []
    for c in campaigns:
        if not c.budget or not c.spent:
            continue
        budget = float(c.budget)
        spent  = float(c.spent or 0)
        if budget <= 0 or spent <= 0:
            continue
        pct = round(spent / budget * 100)

        has_budget_alert = False
        if spent > budget:
            alerts.append({
                'level': 'danger', 'icon': 'bi-wallet2',
                'title': f'«{c.name}»: бюджет превышен — потрачено {pct}%',
                'text': 'Расходы вышли за рамки бюджета. Проверьте финансирование.',
            })
            has_budget_alert = True
        elif spent > budget * 0.85:
            alerts.append({
                'level': 'warning', 'icon': 'bi-wallet2',
                'title': f'«{c.name}»: бюджет почти исчерпан — {pct}%',
                'text': 'Осталось менее 15% бюджета. Подготовьте решение о продлении.',
            })

        if not has_budget_alert and c.status == 'active':
            roi = roi_by_id.get(c.id) if roi_by_id is not None else getattr(c, 'roi', None)
            if roi is not None and roi < 0 and spent > budget * 0.5:
                alerts.append({
                    'level': 'warning', 'icon': 'bi-graph-down-arrow',
                    'title': f'«{c.name}»: убыточна при высоких расходах — ROI {roi}%',
                    'text': 'Потрачено более 50% бюджета при отрицательном ROI. '
                            'Рассмотрите приостановку.',
                })
    return alerts
