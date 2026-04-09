import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def _header_style():
    fill = PatternFill('solid', fgColor='2563EB')
    font = Font(bold=True, color='FFFFFF')
    align = Alignment(horizontal='center', vertical='center')
    return fill, font, align


def _auto_width(ws, n_rows, n_cols):
    for col in range(1, n_cols + 1):
        max_len = max(
            (len(str(ws.cell(row=r, column=col).value or ''))
             for r in range(1, n_rows + 2)),
            default=8,
        )
        ws.column_dimensions[get_column_letter(col)].width = min(max_len + 2, 40)


def export_leads_excel(leads, campaigns):
    """
    Возвращает BytesIO с Excel-файлом:
      Лист 1 — все лиды (все поля)
      Лист 2 — сводная таблица по кампаниям (CPL, ROI, Conversion Rate)
    """
    wb = openpyxl.Workbook()
    fill, font, align = _header_style()

    # ── Лист 1: Лиды ──────────────────────────────────────────────
    ws = wb.active
    ws.title = 'Лиды'

    lead_headers = [
        'ID', 'Имя', 'Фамилия', 'Email', 'Телефон', 'Должность',
        'Компания', 'ИНН', 'Город', 'Тип клиента',
        'ЛПР (ФИО)', 'ЛПР (Должность)',
        'Статус', 'Score', 'Источник',
        'UTM Source', 'UTM Medium', 'UTM Campaign',
        'Кампания', 'Ответственный',
        'Сумма сделки', 'Заметки',
        'Создан', 'Конвертирован',
    ]

    for col, h in enumerate(lead_headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = font
        cell.fill = fill
        cell.alignment = align

    ws.freeze_panes = 'A2'
    ws.row_dimensions[1].height = 22

    for row, lead in enumerate(leads, 2):
        ws.cell(row=row, column=1,  value=lead.id)
        ws.cell(row=row, column=2,  value=lead.first_name)
        ws.cell(row=row, column=3,  value=lead.last_name)
        ws.cell(row=row, column=4,  value=lead.email)
        ws.cell(row=row, column=5,  value=lead.phone)
        ws.cell(row=row, column=6,  value=lead.position)
        ws.cell(row=row, column=7,  value=lead.company)
        ws.cell(row=row, column=8,  value=lead.inn)
        ws.cell(row=row, column=9,  value=lead.city)
        ws.cell(row=row, column=10, value=lead.client_type.upper())
        ws.cell(row=row, column=11, value=lead.decision_maker_name)
        ws.cell(row=row, column=12, value=lead.decision_maker_position)
        ws.cell(row=row, column=13, value=lead.status)
        ws.cell(row=row, column=14, value=lead.score)
        ws.cell(row=row, column=15, value=lead.source)
        ws.cell(row=row, column=16, value=lead.utm_source)
        ws.cell(row=row, column=17, value=lead.utm_medium)
        ws.cell(row=row, column=18, value=lead.utm_campaign)
        ws.cell(row=row, column=19,
                value=lead.campaign.name if lead.campaign else None)
        ws.cell(row=row, column=20,
                value=(lead.assignee.full_name or lead.assignee.username)
                       if lead.assignee else None)
        ws.cell(row=row, column=21,
                value=float(lead.deal_amount) if lead.deal_amount else None)
        ws.cell(row=row, column=22, value=lead.notes)
        ws.cell(row=row, column=23,
                value=lead.created_at.strftime('%d.%m.%Y %H:%M')
                       if lead.created_at else None)
        ws.cell(row=row, column=24,
                value=lead.converted_at.strftime('%d.%m.%Y')
                       if lead.converted_at else None)

    _auto_width(ws, len(leads), len(lead_headers))

    # ── Лист 2: Кампании ──────────────────────────────────────────
    ws2 = wb.create_sheet('Кампании')

    camp_headers = [
        'ID', 'Название', 'Статус', 'Канал', 'Аудитория',
        'Бюджет', 'Потрачено', 'Лидов',
        'Конверсия %', 'CPL', 'Выручка', 'ROI %',
        'Дата начала', 'Дата конца',
    ]

    for col, h in enumerate(camp_headers, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = font
        cell.fill = fill
        cell.alignment = align

    ws2.freeze_panes = 'A2'
    ws2.row_dimensions[1].height = 22

    for row, c in enumerate(campaigns, 2):
        ws2.cell(row=row, column=1,  value=c.id)
        ws2.cell(row=row, column=2,  value=c.name)
        ws2.cell(row=row, column=3,  value=c.status)
        ws2.cell(row=row, column=4,  value=c.channel)
        ws2.cell(row=row, column=5,  value=c.target_audience)
        ws2.cell(row=row, column=6,  value=float(c.budget) if c.budget else 0)
        ws2.cell(row=row, column=7,  value=float(c.spent) if c.spent else 0)
        ws2.cell(row=row, column=8,  value=c.lead_count)
        ws2.cell(row=row, column=9,  value=c.conversion_rate)
        ws2.cell(row=row, column=10, value=c.cpl)
        ws2.cell(row=row, column=11, value=float(c.revenue) if c.revenue else 0)
        ws2.cell(row=row, column=12, value=c.roi)
        ws2.cell(row=row, column=13,
                value=c.start_date.strftime('%d.%m.%Y') if c.start_date else None)
        ws2.cell(row=row, column=14,
                value=c.end_date.strftime('%d.%m.%Y') if c.end_date else None)

    _auto_width(ws2, len(campaigns), len(camp_headers))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
