from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField, SubmitField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError

from app.models.campaign import CAMPAIGN_STATUSES, CAMPAIGN_CHANNELS, TARGET_AUDIENCES


class CampaignForm(FlaskForm):
    name = StringField('Название', validators=[
        DataRequired(message='Название обязательно'),
        Length(max=200, message='Не более 200 символов')
    ])
    description = TextAreaField('Описание', validators=[Optional()])

    status = SelectField('Статус', choices=[
        ('draft',     'Черновик'),
        ('active',    'Активная'),
        ('paused',    'Приостановлена'),
        ('completed', 'Завершена'),
        ('archived',  'Архив'),
    ], default='draft')

    channel = SelectField('Канал', choices=[
        ('',         '— не выбрано —'),
        ('email',    'Email'),
        ('social',   'Соцсети'),
        ('search',   'Поиск'),
        ('display',  'Медийная'),
        ('referral', 'Реферальный'),
        ('tender',   'Тендер'),
        ('other',    'Другое'),
    ], validators=[Optional()])

    target_audience = SelectField('Целевая аудитория', choices=[
        ('',      '— не выбрано —'),
        ('b2b',   'B2B'),
        ('b2g',   'B2G'),
        ('mixed', 'Смешанная'),
    ], validators=[Optional()])

    budget = DecimalField('Бюджет (₽)', validators=[
        Optional(), NumberRange(min=0, message='Бюджет не может быть отрицательным')
    ], places=2, default=0)

    spent = DecimalField('Потрачено (₽)', validators=[
        Optional(), NumberRange(min=0, message='Сумма не может быть отрицательной')
    ], places=2, default=0)

    utm_source   = StringField('UTM Source',   validators=[Optional(), Length(max=100)])
    utm_medium   = StringField('UTM Medium',   validators=[Optional(), Length(max=100)])
    utm_campaign = StringField('UTM Campaign', validators=[Optional(), Length(max=100)])

    start_date = DateField('Дата начала',    validators=[Optional()])
    end_date   = DateField('Дата окончания', validators=[Optional()])

    submit = SubmitField('Сохранить')

    def validate_end_date(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError('Дата окончания не может быть раньше даты начала')
