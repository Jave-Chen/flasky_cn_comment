# coding=utf-8

from flask import g, jsonify
from flask_httpauth import HTTPBasicAuth
from ..models import User, AnonymousUser
from . import api
from .errors import unauthorized, forbidden

# 初始化Flask-HTTPAuth
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(email_or_token, password):
    """ 用户认证

    认证方法只在API蓝本中使用，所以Flask-HTTPAuth扩展只在蓝本中初始化，而不像其他扩展那样要
    在程序包中初始化。

    电子邮件和密码使用User模型中现有的方法验证。如果登录密令正确，这个验证就返回True,否则返回
    False。API蓝本也支持匿名用户访问，此时客户端发送的电子邮件字段必须为空。

    验证回调函数把通过认证的用户保存在Flask的全局对象g中，视图函数便能进行访问。匿名登录时，函
    数返回True并把Flask-Login提供的AnonymousUser类实例赋值给g.current_user。

    如果认证密令不正确，服务器向客户端返回401错误。默认情况下，Flask-HTTPAuth自动生成这个状
    态码，但为了和API返回的其他错误保持一致，可以自定义这个错误响应。

    第一个认证参数可以是电子邮件地址或认证令牌。如果这个参数为空，那就和之前一样，假定是匿名用
    户。如果密码为空，那就假定email_or_token参数提供的是令牌。按照令牌的方式进行认证。如果两
    个参数都不为空，家丁使用常规的邮件地址和密码进行认证。在这种实现方式中，基于令牌的认证是可
    选的，由客户端决定是否使用。g.token_used变量为了让视图函数能区分这两种认证方法。

    :param email_or_token:
    :param password:
    :return:
    """
    if email_or_token == '':
        g.current_user = AnonymousUser()
        return True
    if password == '':
        g.current_user = User.verify_auth_token(email_or_token)
        g.token_used = True
        return g.current_user is not None
    user = User.query.filter_by(email=email_or_token).first()
    if not user:
        return False
    g.current_user = user
    g.token_used = False
    return user.verify_password(password)


@auth.error_handler
def auth_error():
    """ Flask-HTTPAuth错误处理程序

    :return:
    """
    return unauthorized('Invalid credentials')


@api.before_request
@auth.login_required
def before_request():
    """

    蓝本中所有路由都要使用相同的方式进行保护，因此在before_request处理程序中使用
    login_required修饰器，应用到整个蓝本。

    API蓝本中的所有路由都能进行自动认证。作为附加认证，before_request还会拒绝已通过认证但没
    有确认账户的用户。

    :return:
    """
    if (not g.current_user.is_anonymous
        and not g.current_user.confirmed):
        return forbidden('Unconfirmed account')


@api.route('/token')
def get_token():
    """ 生成认证令牌

    为了避免客户端使用旧令牌申请新令牌，要在视图函数中检查g.token_used变量的值，如果使用令牌
    进行认证就解决请求。这个视图函数返回JSON格式的响应，其中包含了过期时间为1小时的令牌。JSON
    格式的响应也包含过期时间。

    :return:
    """
    if g.current_user.is_anonymous or g.token_used:
        return unauthorized('Invalid credentials')
    return jsonify({'token': g.current_user.generate_auth_token(
        expiration=3600), 'expiration': 3600})