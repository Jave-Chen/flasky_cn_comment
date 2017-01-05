# coding=utf-8

""" 认证功能包

创建认证蓝本对象，从app/auth/views.py中引入路由。

"""

from flask import Blueprint

auth = Blueprint('auth', __name__)

from . import views