from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp

class RegisterForm(FlaskForm):
    email = StringField('Gmail', validators=[
        DataRequired(), Email(),
        Regexp(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', message="Only Gmail allowed.")
    ])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Gmail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class UsernameForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), Length(min=3, max=20),
        Regexp(r'^[A-Za-z0-9_]+$', message="Letters, numbers, underscores only.")
    ])
    submit = SubmitField('Set Username')
