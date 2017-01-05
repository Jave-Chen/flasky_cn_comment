# coding=utf-8

""" 表单文件
"""

from flask_wtf import Form
from flask_pagedown.fields import PageDownField
from wtforms import StringField, TextAreaField, BooleanField
from wtforms import SelectField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Length, Email, Regexp

from ..models import Role, User


class NameForm(Form):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')


class EditProfileForm(Form):
    """ 普通用户资料编辑表单

    表单中所有字段都是可选的，因此长度验证函数允许长度为0。

    """
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')


class EditProfileAdminForm(Form):
    """ 管理员使用的资料编辑表单

    除了普通用户的资料信息字段之外，管理员在表单中还要能编辑用户的电子邮件，用户名、确认状态和角色。

    属性：
        role: 用户角色。WTForms对HTML表单控件<select>进行SelectField包装，从而实现下拉列表,
            用来在这个表单中选择用户角色。

    方法：
        email和username字段的构造方式和认证表单中的一样，但处理验证时需要更加小心。
        验证这两个字段时，首先要检查字段的值是否发生了变化，如果有变化，就要保证新值
        不和其他用户的相应字段值重复；如果字段值没有变化，则应该跳过验证。
        表单构造函数接收用户对象作为参数，并将其保存在成员变量中，随后自定义的验证方法
        要使用这个用户对象。
    """
    email = StringField(
        'Email',
        validators=[DataRequired(), Length(1, 64), Email()]
    )
    username = StringField(
        'Username',
        validators=[
            DataRequired(),
            Length(1, 64),
            Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                'Usernames must have only letters, '
                'numbers, dots or underscores')
        ]
    )
    confirmed = BooleanField('Confirmed')
    role = SelectField('Role', coerce=int)
    name = StringField('Real name', validators=[Length(0, 64)])
    location = StringField('Location', validators=[Length(0, 64)])
    about_me = TextAreaField('About me')
    submit = SubmitField('Submit')

    def __init__(self, user, *args, **kwargs):
        """

        :param user:
        :param args:
        :param kwargs:

        SelectField实例必须在其choices属性中设置各选项。选项必须是一个由元组
        组成的列表，各元组都包含两个元素：选项的标识符和显示在控件中的文本字符串。
        choices列表在表单的构造函数中设定，其值从Role模型中获取，使用一个查询按
        照角色名的字母顺序排列所有角色。元组中的标识符是角色的id，因为这是个整数，
        所以在SelectField构造函数中添加coerce=int参数，从而把字段的值转换为整
        数，而不使用默认的字符串。
        """
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)
            for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if (field.data != self.user.email
                and User.query.filter_by(email=field.data).first()):
            raise ValidationError('Email already registered.')

    def validate_username(self, field):
        if (field.data != self.user.username
                and User.query.filter_by(username=field.data).first()):
            raise ValidationError('Username already in use.')


class PostForm(Form):
    """ 博客文章表单

    使用PageDownField将多行文件控件转换为Markdown富文本编辑器。

    """
    body = PageDownField("What's on your mind?", validators=[DataRequired()])
    submit = SubmitField('Submit')


class CommentForm(Form):
    """ 评论输入表单

    属性：
        body: 评论内容
        submit: 提交按钮

    """
    body = StringField('Enter your comment', validators=[DataRequired()])
    submit = SubmitField('Submit')
