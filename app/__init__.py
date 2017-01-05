# coding=utf-8
""" 程序包的构造文件

导入和创建程序使用的扩展类，创建程序实例后对扩展类初始化，并注册蓝图。

    导入模块说明：
    flask_login: 管理用户认证状态的扩展。不依赖特定的认证机制。
        使用该扩展需要User模型实现以下方法：
        is_authenticated() 用户是否已经登录
        is_active() 允许/禁用用户账户
        is_anonymous() 是否匿名用户（普通用户返回False）
        get_id() 返回用户的唯一标识符，使用Unicode编码字符串
        这4个方法可以在模型类中作为方法直接实现。也可以使用Flask-login提供的UserMixin类，
        该类包含这些方法的默认实现。

    Flask-PageDown:
        为Flask包装的PageDown，把PageDown集成到Flask-WTF表单中。PageDown是使用
        JavaScript实现的客户端Markdown到HTML的转换程序。


"""
from flask import Flask
from flask_bootstrap import Bootstrap  # 前端框架
# 管理已登录用户的用户会话
from flask_login import LoginManager  # 登录扩展
from flask_mail import Mail  # 邮件扩展
from flask_moment import Moment  # 时间本地化扩展
from flask_pagedown import PageDown  # 分页扩展
from flask_sqlalchemy import SQLAlchemy  # 数据管理扩展

# 从程序根目录导入 config.py ，直接使用文件名。
from config import config

# 创建扩展类
bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
pagedown = PageDown()

# session_protection 属性值可以设置为None, 'basic', 'strong',
# 提供不同的安全等级防止用户会话遭篡改。
# 设为'strong'时，Flask-Login会记录客户端IP地址和浏览器的用户代理信息，
# 如果发现异动就登出用户。
# login_view 属性设置登录页面的端点。
# 因为登录路由在蓝本中定义，所以要在登录页面前面加上蓝本的名字。
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'


def create_app(config_name):
    """ 实例工厂函数。

    根据配置类的实例名称创建实例，然后：初始化扩展类；根据配置启用SSL；注册main, auth, api 蓝图。

    参数：
        config_name: 实例名称，通过配置类配置。

    返回：
        实例名为config_name的Flask实例。

    异常：
        无。
    """
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    pagedown.init_app(app)

    # 重定向到HTTPS
    if (not app.debug
            and not app.testing
            and not app.config['SSL_DISABLE']):
        from flask_sslify import SSLify
        sslify = SSLify(app)

    # 注册主蓝图。
    # 注册蓝图时，测序将注册整个main包。如果包的下级模块出错，则注册时将报错。
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # 注册认证蓝图。
    # 注册蓝本时程序完成初始化。
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # 注册API蓝本
    from .api_1_0 import api as api_1_0_blueprint
    app.register_blueprint(api_1_0_blueprint, url_prefix='/api/v1.0')

    return app
