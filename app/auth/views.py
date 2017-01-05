# coding=utf-8

""" 认证模块视图文件


"""

from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required
from flask_login import current_user

from . import auth
from .forms import LoginForm, RegistrationForm, ChangePasswordForm
from .forms import PasswordResetRequestForm, PasswordResetForm, ChangeEmailForm
from .. import db
from ..email import send_email
from ..models import User

@auth.before_app_request
def before_request():
    """ 在before_app_request处理程序中过滤未确认的账户

    before_request钩子只能应用到属于蓝本的请求上。若想在蓝本中使用针对程序全局请求的钩子，
    必须使用before_app_request修饰器。

    同时满足以下3个条件时，before_app_request处理程序会拦截请求。

    1) 用户已登录(current_user.is_authenticated()必须返回True)。
    2) 用户的账户还未确认。
    3) 请求的端点(使用request.endpoint获取）不在认证蓝本中。访问认证路由要获取权限，因为
    这些路由的作用是让用户确认账户或执行其他账户管理操作。

    如果请求满足以上3个条件，则会被重定向到/auth/unconfirmed路由，显示一个确认用户相关信
    息的页面。

    确认用户登录后，调用User.ping()方法更新已登录用户访问时间。

    :return:
        重定向到/auth/unconfirmed路由
    """
    if current_user.is_authenticated:
        current_user.ping()
        if (not current_user.confirmed
                and request.endpoint[:5] != 'auth.'
                and request.endpoint != 'static'):
            return redirect(url_for('auth.unconfirmed'))


@auth.route('/unconfirmed')
def unconfirmed():
    """ 未确认账户路由

    :return:
        如账户为匿名用户或已确认，则重定向到主页面，否则返回未确认页面。
    """
    if current_user.is_anonymours or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """ 登入路由

    当请求类型是GET时，视图函数直接渲染模版，即显示表单。

    当表单在POST请求中提交时，Flask-WTF中的validate_on_submit()函数会验证表单数据，然后尝试登入用户。
    提交登录密码的POST请求最后进行两类重定向：
        用户访问未授权的URL时，会显示登录表单，Flask-Login会把原地址保存在查询字符串的next参数中，
        这个参数可从request.args字典中读取。如果查询字符串中没有next参数，则重定向到首页。
        如果用户输入的电子邮件或密码不正确，则调用Flash函数提示用户“用户名或密码错误”，
        然后再次渲染表单让用户重新登录。

    首先使用表单中填写的email从数据库中加载用户。如果电子邮件地址对应的用户存在，
    再调用用户对象的verify_password()方法，其参数是表单中填写的密码。
        如果密码正确，则调用Flask-Login中的login_user()函数，在用户会话中把用户标记为已登录。

    login_user()函数的参数是要登录的用户，已经可选的“记住我”布尔值，“记住我”也在表单中填写。
        如果值为False，那么关闭浏览器后用户会话就过期，下次用户访问时要重新登录。
        如果值为True,那么会在用户浏览器中写入一个长期有效的cookie，使用这个cookie可以复现用户会话。
    输入：
        无。

    返回值：
        如验证通过，则跳转到主页面或者请求参数中下一参数指向的页面。
        如验证失败，则返回登录页面。

    异常：
        无。
    """
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_pasword(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('main.index'))
        flash('Invalid username or password')
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    """ 登出用户路由

    调用Flask-Login中的logout_user()函数，删除并重设用户会话。
    随后调用Flash提示用户登出消息，然后重定向到首页，完成登出。

    """
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """ 用户注册路由

    根据用户提交的注册信息，包括email,username,password向注册表中新增用户。
    新用户添加后，生成激活口令，调用User.email方法将口令发到用户邮箱，然后重定向到用户登录页面。
    如果注册信息验证不通过，则返回用户注册页面。

    默认情况下，url_for()生成相对URL，例如url_for('auth.confirm', token='abc')返回的字符
    串是'/auth/confirm/abc'。这显然不是能够在电子邮件中发送的正确URL。相对URL在网页的上下文中
    可以正常使用，因为通过添加当前页面的主机名和端口号，浏览器会将其转换为绝对URL。但通过电子邮件
    发送URL时，并没有这种上下文。添加到url_for()函数中的_external=True参数要求程序生成完整的
    URL，其中包含协议，主机名和端口。

    """
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        # 生成确认令牌需要user.id字段，所以需要先提交数据库变化，赋予新用户id值。
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email, 'Confirm Your Account',
                   'auth/email/confirm', user=user, token=token)
        flash('A confirmation email has been sent to you by email.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    """ 确认账户视图

    先检查已登录的用户是否已经确认过，如果确认过，则重定向到首页。这样处理可以避免用户不小心
    多次点击确认令牌。

    令牌确认在User模型中完成，所以视图只需调用confirm()方法即可，然后再根据确认结果显示不同
    的Flash消息。确认成功后，User模型中confirmed属性的值会被修改并添加到会话中，请求处理完
    后，这两个操作被提交到数据库。

    使用login_required修饰器会保护这个路由，因此，用户点击确认邮件中的链接后，要先登录，然后
    才能执行这个视图函数。

    :param token:
    :return:
    """
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        flash('You have confirmed your account. Thanks!')
    else:
        flash('The confirmation link is invalid or has expired.')
    return redirect(url_for('main.index'))


@auth.route('/confirm')
@login_required
def resend_confirmation():
    """ 重新发送账户确认邮件

    这个路由为current_user（即已登录的用户，也就是目标用户）重做了一遍注册路由中的操作。
    这个路由也用login_required保护，确保访问时程序知道请求再次发送邮件的是哪个用户。

    :return:
    """
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, 'Confirm Your Account',
               'auth/email/confirm', user=current_user, token=token)
    flash('A new confirmation email has been sent to your by email.')
    return redirect(url_for('main.index'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            flash('Your password has been updated.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid password')
    return render_template("auth/change_password.html", form=form)


@auth.route('/rest', methods=['GET', 'POST'])
def password_reset_request():
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email, 'Rest Your Passowrd',
                       'auth/email/reset_password',
                       user=user, token=token,
                       next=request.args.get('next'))
        flash('An email with instructions to reset your password has been '
              'send to you.')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    if not current_user.is_anonymous:
        return redirect(url_for('mian.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return redirect(url_for('main.index'))
        if user.reset_password(token, form.password.data):
            flash('Your password has been updated.')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html', form=form)


@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email, 'Confirm your email address',
                       'auth/email/change_email',
                       user=current_user, token=token)
            flash('An email with instructions to confirm your new email '
                  'address has been sent to you.')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')
    return render_template("auth/change_email.html", form=form)


@auth.route('/change-email/<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        flash('Your email address has been updated.')
    else:
        flash('Invalid request.')
    return redirect(url_for('main.index'))