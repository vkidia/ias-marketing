from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User
from app.extensions import db


class LoginForm(FlaskForm):
    username    = StringField('Логин', validators=[DataRequired(message='Введите логин')])
    password    = PasswordField('Пароль', validators=[DataRequired(message='Введите пароль')])
    remember_me = BooleanField('Запомнить меня')
    submit      = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username   = StringField('Логин',   validators=[
        DataRequired(), Length(min=3, max=80, message='Логин: 3–80 символов')
    ])
    email      = StringField('Email',   validators=[
        DataRequired(), Email(message='Некорректный email'), Length(max=120)
    ])
    full_name  = StringField('Полное имя', validators=[Length(max=200)])
    password   = PasswordField('Пароль', validators=[
        DataRequired(), Length(min=6, message='Пароль: минимум 6 символов')
    ])
    password2  = PasswordField('Повторите пароль', validators=[
        DataRequired(), EqualTo('password', message='Пароли не совпадают')
    ])
    submit     = SubmitField('Зарегистрироваться')

    def validate_username(self, field):
        user = db.session.scalar(db.select(User).where(User.username == field.data))
        if user:
            raise ValidationError('Этот логин уже занят.')

    def validate_email(self, field):
        user = db.session.scalar(db.select(User).where(User.email == field.data))
        if user:
            raise ValidationError('Этот email уже зарегистрирован.')