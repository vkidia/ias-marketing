"""DSS (Decision Support System) вычисляет рекомендации по ключевым показателям."""

# алерты показываем только если лидов достаточно, иначе статистика ненадёжна
_MIN_LEADS = 5
# порядок уровней для сортировки: сначала самые критичные
_LEVEL_ORDER = {'danger': 0, 'warning': 1, 'info': 2, 'success': 3}


def collect_campaign_alerts(campaigns, roi_by_id=None):
    """
    Собирает именованные алерты по бюджету и ROI для списка кампаний.
    roi_by_id: {campaign_id: roi_value}. Если None — берётся c.roi (свойство модели).
    Используется в глобальном и сравнительном DSS, чтобы критичные проблемы
    конкретных кампаний не оставались скрытыми.
    """
    alerts = []
    for c in campaigns:
        if not c.budget or not c.spent:
            continue
        budget = float(c.budget)
        spent = float(c.spent or 0)
        if budget <= 0 or spent <= 0:
            continue
        pct = round(spent / budget * 100)

        has_budget_alert = False
        if spent > budget:
            alerts.append({
                'level': 'danger', 'icon': 'bi-wallet2',
                'title': f'«{c.name}»: бюджет превышен — потрачено {pct}%',
                'text': 'Расходы вышли за рамки бюджета. Проверьте финансирование и рассмотрите приостановку.',
            })
            has_budget_alert = True
        elif spent > budget * 0.85:
            alerts.append({
                'level': 'warning', 'icon': 'bi-wallet2',
                'title': f'«{c.name}»: бюджет почти исчерпан — {pct}%',
                'text': 'Осталось менее 15% бюджета. Подготовьте решение о продлении или завершении.',
            })

        if not has_budget_alert and c.status == 'active':
            roi = roi_by_id.get(c.id) if roi_by_id is not None else getattr(c, 'roi', None)
            if roi is not None and roi < 0 and spent > budget * 0.5:
                alerts.append({
                    'level': 'warning', 'icon': 'bi-graph-down-arrow',
                    'title': f'«{c.name}»: убыточна при высоких расходах — ROI {roi}%',
                    'text': 'Потрачено более 50% бюджета при отрицательном ROI. Рассмотрите приостановку.',
                })
    return alerts


def compute_dss(funnel, total_leads, avg_roi, active_campaigns, global_cr, campaign_alerts=None):
    """
    Портфельный DSS — общие показатели + именованные алерты по кампаниям.
    campaign_alerts: результат collect_campaign_alerts(), передаётся из роута.
    """
    dss = []

    if total_leads == 0:
        dss.append({
            'level': 'info', 'icon': 'bi-info-circle',
            'title': 'Нет лидов в системе',
            'text': 'Добавьте первые лиды или запустите кампанию для их привлечения.',
        })
    elif total_leads >= _MIN_LEADS:
        if global_cr is not None and global_cr < 5:
            dss.append({
                'level': 'danger', 'icon': 'bi-exclamation-triangle-fill',
                'title': f'Критически низкая конверсия — {global_cr}%',
                'text': 'Менее 5% лидов доходят до сделки. Проверьте качество входящих заявок и скрипты обработки.',
            })
        elif global_cr is not None and global_cr < 15:
            dss.append({
                'level': 'warning', 'icon': 'bi-exclamation-circle',
                'title': f'Конверсия ниже нормы — {global_cr}%',
                'text': 'Для B2B/B2G норма — от 15%. Усильте квалификацию лидов и работу с ЛПР.',
            })

        lost_pct = round(funnel.get('lost', 0) / total_leads * 100, 1)
        if lost_pct > 40:
            dss.append({
                'level': 'warning', 'icon': 'bi-funnel',
                'title': f'{lost_pct}% лидов теряется',
                'text': 'Слишком много лидов уходит со статусом «Потерян». Проанализируйте причины отказов.',
            })

    if active_campaigns == 0:
        dss.append({
            'level': 'warning', 'icon': 'bi-megaphone',
            'title': 'Нет активных кампаний',
            'text': 'Запустите хотя бы одну кампанию для генерации новых лидов.',
        })

    if avg_roi is not None and avg_roi < 0:
        dss.append({
            'level': 'danger', 'icon': 'bi-graph-down-arrow',
            'title': f'Средний ROI отрицательный — {avg_roi}%',
            'text': 'Маркетинговые затраты не окупаются в среднем по всем кампаниям. Пересмотрите бюджеты.',
        })

    if campaign_alerts:
        dss.extend(campaign_alerts)

    if not dss:
        dss.append({
            'level': 'success', 'icon': 'bi-check-circle-fill',
            'title': 'Всё в норме',
            'text': 'Ключевые показатели в допустимых пределах. Продолжайте в том же духе!',
        })
    else:
        # сортируем так чтобы danger шёл первым, success последним
        dss.sort(key=lambda r: _LEVEL_ORDER.get(r['level'], 2))

    return dss


def compute_campaign_dss(funnel, total_leads, roi, cr, spent, budget):
    """DSS для одной кампании — детальный анализ без портфельных метрик."""
    dss = []

    if total_leads == 0:
        dss.append({
            'level': 'info', 'icon': 'bi-info-circle',
            'title': 'Нет лидов в кампании',
            'text': 'Добавьте лиды или настройте источник привлечения заявок.',
        })
        return dss

    if budget and spent:
        if spent > budget:
            pct = round(spent / budget * 100)
            dss.append({
                'level': 'danger', 'icon': 'bi-wallet2',
                'title': f'Бюджет превышен — потрачено {pct}%',
                'text': 'Расходы вышли за рамки установленного бюджета. Проверьте финансирование кампании.',
            })
        elif spent > budget * 0.85:
            pct = round(spent / budget * 100)
            dss.append({
                'level': 'warning', 'icon': 'bi-wallet2',
                'title': f'Бюджет почти исчерпан — {pct}%',
                'text': 'Осталось менее 15% бюджета. Подготовьте решение о продлении или завершении кампании.',
            })

    if total_leads >= _MIN_LEADS:
        if cr < 5:
            dss.append({
                'level': 'danger', 'icon': 'bi-exclamation-triangle-fill',
                'title': f'Критически низкая конверсия — {cr}%',
                'text': 'Менее 5% лидов доходят до сделки. Проверьте качество заявок и скрипты обработки.',
            })
        elif cr < 15:
            dss.append({
                'level': 'warning', 'icon': 'bi-exclamation-circle',
                'title': f'Конверсия ниже нормы — {cr}%',
                'text': 'Норма — от 15%. Усильте квалификацию лидов и работу с ЛПР.',
            })

        lost_pct = round(funnel.get('lost', 0) / total_leads * 100, 1)
        if lost_pct > 40:
            dss.append({
                'level': 'warning', 'icon': 'bi-funnel',
                'title': f'{lost_pct}% лидов теряется',
                'text': 'Много лидов уходит со статусом «Потерян». Проанализируйте причины отказов.',
            })

    if roi is not None and roi < 0:
        if budget and spent and spent > budget * 0.5:
            dss.append({
                'level': 'danger', 'icon': 'bi-graph-down-arrow',
                'title': f'Кампания убыточна — ROI {roi}%',
                'text': 'Потрачено более 50% бюджета при отрицательном ROI. Рассмотрите приостановку.',
            })
        else:
            dss.append({
                'level': 'warning', 'icon': 'bi-graph-down-arrow',
                'title': f'Отрицательный ROI — {roi}%',
                'text': 'Затраты пока не окупаются. Следите за динамикой конверсий.',
            })

    if not dss:
        dss.append({
            'level': 'success', 'icon': 'bi-check-circle-fill',
            'title': 'Кампания работает эффективно',
            'text': 'Ключевые показатели в норме. Продолжайте в том же темпе!',
        })
    else:
        dss.sort(key=lambda r: _LEVEL_ORDER.get(r['level'], 2))

    return dss
