# coding=utf-8
# /config.py


"""博客配置文件。

"""


import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    """ 基础配置类

        todo 管理员信息（邮箱，密码，名称）在安装时输入
    """
    # 安全密钥从服务器SECRET_KEY变量获取或在此通过字符串赋值
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SSL_DISABLE = False
    # 数据库相关
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    # 启用缓慢查询记录功能
    SQLALCHEMY_RECORD_QUERIES = True
    # 邮件相关
    MAIL_SERVER = 'smtp.google.email.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # 管理员邮箱名称
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # 管理员邮箱密码
    FLASKY_MAIL_SUBJECT_PREFIX = '[Flasky]'
    FLASKY_MAIL_SENDER = 'Flasky Admin <flasky@example.com>'
    FLASKY_ADMIN = os.environ.get('FLASK_ADMIN')  # 从系统变量获取管理员名称
    FLASKY_POSTS_PER_PAGE = 20  # 每页文章数量
    FLASKY_FOLLOWERS_PER_PAGE = 50  # 每页关注者数量
    FLASKY_COMMENTS_PER_PAGE = 30  # 每页评论数
    FLASKY_SLOW_DB_QUERY_TIME = 0.5

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    """ 开发配置类
        打开调试功能和设定开发数据库

    """
    # 打开调试功能
    DEBUG = True
    # 使用开发数据库
    SQLALCHEMY_DATABASE_URI = (os.environ.get('DEV_DATABASE_URL')
        or 'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite'))


class TestingConfig(Config):
    """ 测试配置类
        设定数据库为存有测试数据的测试库，关闭表单保护
    """
    TESTING = True
    SQLALCHEMY_DATABASE_URI = (os.environ.get('TEST_DATABASE_URL')
        or 'sqlite:///' + os.path.join(basedir, 'data-test.sqlite'))
    # 在测试配置中禁用表单CSRF保护，避免在测试中处理CSRF
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """ 生产配置类

    """
    SQLALCHEMY_DATABASE_URI = (os.environ.get('DATABASE_URL')
        or 'sqlite:///' + os.path.join(basedir, 'data.sqlite'))

    @classmethod
    def init_app(cls, app):
        """ 服务端初始化

        如初始化失败则发送邮件到管理员邮箱。

        配置程序的日志记录器把错误写入电子邮件记录器。

        电子邮件记录器的日志等级被设为logging.ERROR,所以只有发生严重错误时才会发送电子邮件。
        通过添加适当的日志处理程序，可以把较轻缓等级的日志信息写入文件、系统日志或其他的支持方
        法。

        """
        Config.init_app(app)

        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, 'MAIL_USERNAME', None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, 'MAIL_USE_TLS', None):
                secure = ()
        mail_handler = SMTPHandler(
            mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
            fromaddr=cls.FLASKY_MAIL_SENDER,
            toaddrs=[cls.FLASKY_ADMIN],
            subject=cls.FLASKY_MAIL_SUBJECT_PREFIX + ' Application Error',
            credentials=credentials,
            secure=secure
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


class HerokuConfig(ProductionConfig):
    """ Heroku生产配置类

    """
    SSL_DISABLE = bool(os.environ.get('SSL_DISABLE'))

    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # 设置代理
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

        # 日志输出
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.WARNING)
        app.logger.addHander(file_handler)


class UnixConfig(ProductionConfig):
    """ unix生产环境配置

    """

    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # 日志输出
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


# 配置环境字典
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'heroku': HerokuConfig,
    'unix': UnixConfig,

    'default': DevelopmentConfig
}
