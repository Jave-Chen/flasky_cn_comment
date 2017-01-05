# coding=utf-8

""" 错误处理模块文件。

    使用errorhandler装饰器,只有在蓝本中的错误才能触发处理程序。
    要想注册程序全局的错误处理程序，必须使用app_errorhandler.
"""

from flask import render_template, request, jsonify
from . import main


@main.app_errorhandler(403)
def forbidden(e):
    """ 禁止（403）错误处理

    处理403错误，如接收到的数据为JSON格式，则返回JSON格式数据；如为HTML格式则返回403页面。

    参数：
        e: 全局异常。

    返回：
        response: JSON格式数据响应,数据内容：error=forbidden, status_code=403。
        render_template('403.html')：HTML格式页面，同时设置返回状态码为403。

    异常：
        无。
    """
    if (request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accept_html):
        response = jsonify({'error': 'forbidden'})
        response.status_code = 403
        return response
    return render_template('403.html'), 403


@main.app_errorhandler(404)
def page_not_found(e):
    """ 页面未找到（404）错误处理

    处理404错误，如接收到的数据为JSON格式，则返回JSON格式数据；如为HTML格式则返回404页面。

    参数：
        e: 全局异常。

    返回：
        response: JSON格式数据响应,数据内容：error=forbidden, status_code=404。
        render_template('404.html')：HTML格式页面，同时设置返回状态码为404。

    异常：
        无。
    """
    if (request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accept_html):
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    """ 内部错误（500）错误处理

    处理500错误，如接收到的数据为JSON格式，则返回JSON格式数据；如为HTML格式则返回500页面。

    参数：
        e: 全局异常。

    返回：
        response: JSON格式数据响应,数据内容：error=internal server error, status_code=500。
        render_template('500.html')：HTML格式页面，同时设置返回状态码为500。

    异常：
        无。
    """
    if (request.accept_mimetypes.accept_json
            and not request.accept_mimetypes.accpent_html):
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500
