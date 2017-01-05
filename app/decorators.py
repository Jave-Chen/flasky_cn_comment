# coding=utf-8

""" 装饰器文件

"""


from functools import wraps

from flask import abort
from flask_login import current_user

from .models import Permission


def permission_required(permission):
    """ 常规权限检查装饰器

    :param permission:
    :return: 如果用户不具有指定权限，则返回403错误码，即HTTP“禁止”错误。
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """ 管理员权限检查装饰器

    :param f:
    :return:
    """
    return permission_required(Permission.ADMINISTER)(f)


