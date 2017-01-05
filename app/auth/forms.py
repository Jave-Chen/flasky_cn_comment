# coding=utf-8

""" 认证用户表单文件

"""

from flask_wtf import Form
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms import ValidationError
from wtforms.validators import DataRequired, Length, Email, Regexp, EqualTo

from ..models import User


class LoginForm(Form):
    """ 登录表单类

    属性：
        email: 文本字段，用户登录电子邮件地址
        password: 密码字段，用户登录密码
        remember_me：复选框, “记住我”复选框
        submit: 提交按钮，登录按钮

    """
    # 使用Length()和Email()验证
    email = StringField('Email', validators=[DataRequired(), Length(1, 64),
                                             Email()])
    # Password类表示属性为type="password"的<input>元素
    password = PasswordField('Password', validators=[DataRequired()])
    # BooleanField类表示复选框
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log in')


class RegistrationForm(Form):
    """ 用户注册表单

    使用WTForms提供的Regexp验证函数，确保username字段只包含字母、数字、
    下划线和点号。这个验证函数中正则表达式后面的两个参数分别是正则表达式的旗标和验证
    失效时显示的错误消息。

    密码要输入两次。此时要验证两个密码字段中的值是否一致，这种验证可使用WTForms提供
    的另一验证函数实现，即EqualTo。这个验证函数要附属到两个密码字段中的一个上，另一
    个字段则作为参数传入。

    这个表单还有两个自定义的验证函数，以方法的形式实现。如果表单类中定义了以validate_
    开头且后面跟着字段名的方法，这个方法和常规的验证函数一起调用。
    validate_email，validate_username 分别验证email和username字段，确保填写的
    值在数据库中没出现过。自定义的验证函数要想表示验证失败，可以抛出ValidationError
    异常，其参数就是错误消息。

    属性:
        email: 文本字段，注册电子邮件名称
        username: 文本字段，注册用户名
        password: 密码字段，注册密码
        password2: 密码字段，确认密码
        submit: 提交按钮，注册提交

    方法：
        validate_email: 验证邮箱名是否已注册
        validate_username: 验证用户名是否已注册

    """
    email = StringField('Email', validators=[DataRequired(), Length(1, 64),
                                             Email()])
    username = StringField('Username',
                           validators=[DataRequired(),
                                       Length(1, 64),
                                       Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                              'Usernames must have only '
                                              'letters, numbers,'
                                              'dots or underscores')])
    password = PasswordField('Password',
                             validators=[DataRequired(),
                                         EqualTo('password2',
                                                 message='Password must match.')])
    password2 = PasswordField('Confirm password', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already in use.')


class ChangePasswordForm(Form):
    old_password = PasswordField('Old password', validators=[DataRequired()])
    password = PasswordField('New password',
                             validators=[DataRequired(),
                                         EqualTo('password2',
                                                 message='Password must match')])
    password2 = PasswordField('Confirm new password',
                              validators=[DataRequired()])
    submit = SubmitField('Update Password')


class PasswordResetRequestForm(Form):
    email = StringField('Email',
                        validators=[DataRequired(), Length(1, 64), Email()])
    submit = SubmitField('Reset Password')


class PasswordResetForm(Form):
    email = StringField('Email',
                        validators=[DataRequired(), Length(1, 64), Email()])
    password = PasswordField('New Password',
                             validators=[DataRequired(),
                                         EqualTo('password2',
                                                 message='Password must match')])
    password2 = PasswordField('Confirm password', validators=[DataRequired()])
    submit = SubmitField('Reset Password')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError('Unknown email address.')


class ChangeEmailForm(Form):
    email = StringField('New Email',
                        validators=[DataRequired(), Length(1, 64), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Update Email Address')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')
