"""DSS (Decision Support System) — вычисление рекомендаций по ключевым показателям."""


def compute_dss(funnel, total_leads, avg_roi, active_campaigns, global_cr, b2g_count, bad_campaigns):
    """
    Возвращает список рекомендаций вида:
      {'level': 'danger'|'warning'|'info'|'success', 'icon': 'bi-...', 'title': '...', 'text': '...'}
    """
    dss = []

    if total_leads == 0:
        dss.append({
            'level': 'info', 'icon': 'bi-info-circle',
            'title': 'Нет лидов в системе',
            'text': 'Добавьте первые лиды или запустите кампанию для их привлечения.',
        })
    else:
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

        lost_pct = round(funnel['lost'] / total_leads * 100, 1)
        if lost_pct > 40:
            dss.append({
                'level': 'warning', 'icon': 'bi-funnel',
                'title': f'{lost_pct}% лидов теряется',
                'text': 'Слишком много лидов уходит со статусом «Потерян». Проанализируйте причины отказов.',
            })

        if b2g_count == 0:
            dss.append({
                'level': 'info', 'icon': 'bi-building',
                'title': 'Нет B2G лидов',
                'text': 'Государственный сектор — перспективный канал для IT-компании. Рассмотрите участие в тендерах.',
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

    if bad_campaigns:
        names = ', '.join(f'«{c.name}»' for c in bad_campaigns[:3])
        dss.append({
            'level': 'warning', 'icon': 'bi-currency-dollar',
            'title': 'Активные кампании с отрицательным ROI',
            'text': f'{names} — уже потрачено более 50% бюджета при убытке. Рассмотрите приостановку.',
        })

    if not dss:
        dss.append({
            'level': 'success', 'icon': 'bi-check-circle-fill',
            'title': 'Всё в норме',
            'text': 'Ключевые показатели в допустимых пределах. Продолжайте в том же духе!',
        })

    return dss
