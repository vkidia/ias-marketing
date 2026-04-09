from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange, ValidationError


class LeadForm(FlaskForm):
    # Контактное лицо
    first_name = StringField('Имя', validators=[
        DataRequired(message='Имя обязательно'),
        Length(max=100, message='Не более 100 символов'),
    ])
    last_name = StringField('Фамилия', validators=[
        Optional(), Length(max=100),
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email обязателен'),
        Email(message='Введите корректный email'),
        Length(max=120),
    ])
    phone = StringField('Телефон', validators=[Optional(), Length(max=20)])
    position = StringField('Должность контактного лица', validators=[Optional(), Length(max=100)])

    # Организация
    company = StringField('Организация', validators=[Optional(), Length(max=200)])
    inn     = StringField('ИНН',         validators=[Optional(), Length(max=12)])
    city    = StringField('Город',       validators=[Optional(), Length(max=100)])

    client_type = SelectField('Тип клиента', choices=[
        ('b2b', 'B2B'),
        ('b2g', 'B2G'),
    ], default='b2b')

    # ЛПР
    decision_maker_name     = StringField('ФИО ЛПР',       validators=[Optional(), Length(max=200)])
    decision_maker_position = StringField('Должность ЛПР', validators=[Optional(), Length(max=100)])

    # Воронка
    source = SelectField('Источник', choices=[
        ('',        '— не указан —'),
        ('landing', 'Лендинг'),
        ('form',    'Форма'),
        ('import',  'Импорт'),
        ('manual',  'Вручную'),
    ], validators=[Optional()])

    # UTM (заполняются вручную при ручном создании)
    utm_source   = StringField('UTM Source',   validators=[Optional(), Length(max=100)])
    utm_medium   = StringField('UTM Medium',   validators=[Optional(), Length(max=100)])
    utm_campaign = StringField('UTM Campaign', validators=[Optional(), Length(max=100)])

    # Привязки — choices заполняются в роуте динамически
    campaign_id = SelectField('Кампания',       validators=[Optional()])
    assigned_to = SelectField('Ответственный',  validators=[Optional()])

    deal_amount = DecimalField('Сумма сделки (₽)', validators=[
        Optional(),
        NumberRange(min=0, message='Сумма не может быть отрицательной'),
    ], places=2)

    notes = TextAreaField('Заметки', validators=[Optional()])

    submit = SubmitField('Сохранить')

    def validate_inn(self, field):
        if field.data:
            if not field.data.isdigit():
                raise ValidationError('ИНН — только цифры')
            if len(field.data) not in (10, 12):
                raise ValidationError('ИНН — 10 или 12 цифр')


class LeadImportForm(FlaskForm):
    csv_file = FileField('CSV-файл', validators=[
        FileAllowed(['csv'], 'Только CSV файлы (.csv)'),
    ])
    campaign_id = SelectField('Привязать к кампании', validators=[Optional()])
    submit = SubmitField('Импортировать')
