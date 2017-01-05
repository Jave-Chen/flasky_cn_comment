# coding=utf-8

"""创建main蓝本文件。

创建main蓝本，并在工厂函数create_app()中注册到程序上。
在末尾导入程序的路由模块app/main/views.py和错误处理模块app/main/errors.py，避免循环导入依赖。因为在views.py和errors.py中还要导入蓝本main。

"""
from flask import Blueprint

# Blueprint两个必须参数：蓝本的名字和蓝本所在的包或模块。
# 大多数情况，第二个参数使用Python的__name__变量。
main = Blueprint('main', __name__)

from . import views, errors
from ..models import Permission


@main.app_context_processor
def inject_permissions():
    """ 把Permission类加入模版上下文

    在模版中可能也想要检查权限，所以Permission类为所有位定义了常亮以便于获取。为了
    避免每次调用render_template()时都多添加一个模版参数，可以使用上下文处理器。上
    下文处理能让变量在所有模版中全局可访问。

    :return:
    """
    return dict(Permission=Permission)
