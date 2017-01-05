# coding=utf-8

from flask import jsonify
from app.exceptions import ValidationError
from . import api


def bad_request(message):
    """ 400错误处理程序

    :param message:
    :return:
    """
    response = jsonify({'error': 'bad request', 'message': message})
    response.status_code = 400
    return response


def unauthorized(message):
    """ 401错误处理程序

    :param message:
    :return:
    """
    response = jsonify({'error': 'unauthorized', 'message': message})
    response.status_code = 401
    return response


def forbidden(message):
    """ 403错误处理

    :param message:
    :return:
    """
    response = jsonify({'error': 'forbidden', 'message': message})
    response.status_code = 403
    return response


@api.errorhandler(ValidationError)
def validation_error(e):
    """ API中ValidationError异常的处理程序

    使用的errorhandler修饰器和注册HTTP状态码处理程序时使用的是同一个，只不过此时接收的参数是
    Exception类，只要抛出了指令类的异常，就会调用被修饰的函数。这个修饰器从API蓝本中调用，所
    以只有当处理蓝本中的路由时抛出了异常才会调用这个处理程序。

    :param e:
    :return:
    """
    return bad_request(e.args[0])