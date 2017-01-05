# coding=utf-8

""" 客户端测试文件

"""

import re
import unittest
from flask import url_for

from app import create_app, db
from app.models import User, Role


class FlaskClientTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_home_page(self):
        response = self.client.get(url_for('main.index'))
        self.assertTrue(b'Stranger' in response.data)

    def test_register_and_login(self):
        """

        /auth/register路由有两种响应方式。如果注册数据可用，会返回一个重定向，把用户转到登录
        页面。注册不可用的情况下，返回的响应会再次渲染注册表单，而且还包含适当的错误消息。为了
        确认注册成功，测试会检查响应的状态码是否为重定向代码302。

        第二个部分使用住处时使用的电子邮件和密码登录。这一工作通过向/auth/login路由发起POST
        请求完成。这一次，调用post()方法时制定了参数follow_redirects=True，让测试客户端和
        浏览器一样，自动向重定向的URL发起GET请求。制定这个参数后，返回的不是302状态码，返回的
        不是302状态码，而是请求重定向的URL返回的响应。

        成功登录后的响应应该是一个页面，显示一个包含用户名的欢迎消息，并提醒用户需要进行账户确
        认才能获得权限。为此，两个断言语句被用于检查响应是否为这个页面。值得注意的一点是，直接
        搜索字符串'Hello, john!'并没有用，因为这个字符串由动态部分和静态部分组成，而且两部分
        之间有额外的空白。为了避免测试时空白引起的问题，使用更为灵活的正则表达式。

        在确认账户是有一个小障碍。在注册过程中，通过电子邮件讲确认URL发给用户，而在测试中处理
        电子邮件不是一件简单的事。上面这个测试使用的解决方法忽略了注册时生成的令牌，直接在User
        实例上调用方法重新生成一个新令牌。在测试环境中，Flask-Mail会保存邮件正文，所以还有一
        种可行的解决办法，即通过解析邮件正文来提取令牌。

        得到令牌后，测试的第三部分模拟用户点击确认令牌URL。这一过程通过向确认URL发起GET请求并
        附上确认令牌来完成。这个请求的响应是重定向，转到首页，当这里再次指定了参数
        follow_redirects=True，所以测试客户端会自动向重定向发起请求。此外，还有检查响应中
        是否包含欢迎消息和一个向用户说明确认成功的Flash消息。

        最后一步是向退出路由发送GET请求，为了证实成功推出，这段测试在响应中搜索一个Flash消息。

        :return:
        """
        # 注册新账户
        response = self.client.post(url_for('auth.register'), data={
            'email': 'johen@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertTrue(response.status_code == 302)

        # 使用新注册的账户登录
        response = self.client.post(url_for('auth.login'), data={
            'email': 'john@example.com',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertTrue(re.search(b'Hello,\s+john!', response.data))
        self.assertTrue(
            b'You have not confirmed your account yet' in response.data)

        # 发送确认令牌
        user = User.query.filter_by(email='john@example.com').first()
        token = user.generate_confirmation_token()
        response = self.client.get(url_for('auth.confirm', token=token),
                                   follow_redirects=True)
        self.assertTrue(
            b'You have confirmed your account' in response.data)

        # 退出
        response = self.client.get(url_for('auth.logout'), follow_redirects=True)
        self.assertTrue(b'You have been logged out' in response.data)
