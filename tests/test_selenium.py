# coding=utf-8

""" selenium测试文件

"""

import re
import threading
import time
import unittest

from selenium import webdriver

from app import create_app, db
from app.models import Role, User, Post


class SeleniumTestCase(unittest.TestCase):
    """ Selenium单元测试类

    setUpClass()方法使用Selenium提供的webdriver API启动一个Firefox实例，并创建一个程序
    和数据库，其中写入一个共测试使用的初始数据。然后调用标准的app.run()方法在一个线程中启动程
    序。完成所有测试后，程序会收到一个发往/shutdown的请求，进而停止后台线程。随后，关闭浏览器，
    删除测试数据。

    setUp()方法在每个测试运行之前执行，如果Selenium无法利用startUpClass()方法启动Web浏览
    器就跳过测试。

    """
    client = None

    @classmethod
    def setUpClass(cls):
        # 启动Firefox
        try:
            cls.client = webdriver.Firefox()
        except:
            pass

        # 如果无法启动浏览器，则跳过这些测试
        if cls.client:
            # 创建程序
            cls.app = create_app('testing')
            cls.app_context = cls.app.app_context()
            cls.app_context.push()

            # 禁止日志，保持输出简洁
            import logging
            logger = logging.getLogger('werkzeug')
            logger.setLevel("ERROR")

            # 创建数据库，并使用一些虚拟数据填充
            db.create_all()
            Role.insert_roles()
            User.generate_fake(10)
            Post.generate_fake(10)

            # 添加管理员
            admin_role = Role.query.filter_by(permissions=0xff).first()
            admin = User(email='john@example.com',
                         username='john',
                         password='cat',
                         role=admin_role,
                         confirmed=True)
            db.session.add(admin)
            db.session.commit()

            # 在一个线程中启动Flask服务器
            threading.Thread(target=cls.app.run).start()

            # give the server a second to ensure it is up
            time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        if cls.client:
            # 关闭Flask服务器和浏览器
            cls.client.get('http://localhost:5000/shutdown')
            cls.client.close()

            # 销毁数据库
            db.drop_all()
            db.session.remove()

            # 删除程序上下文
            cls.app_context.pop()

    def setUp(self):
        if not self.client:
            self.skipTest('Web browser not available')

    def tearDown(self):
        pass

    def test_admin_home_page(self):
        """

        使用setUpClass()方法中创建的管理员账户登录，然后打开资料页。与使用Flask测试客户端
        不同，使用Selenium进行测试时，测试向Web浏览器发出指令且从不直接和程序交互。发给浏览器
        的指令和真实用户使用鼠标或键盘执行的操作几乎一样。

        这个测试首先调用get()方法访问程序的首页。在浏览器中，这个操作就是在地址栏总数输入URL。
        为了验证这一步操作的结果，测试代码检查页面源码中是否包含"Hello,Stranger!"这个欢迎消
        息。

        为了访问登录页面，测试使用find_element_by_link_text()方法查找"Log In"链接，然后
        在这个链接上调用click()方法，从而在浏览器中触发一次真正的点击。

        测试使用find_element_by_name()方法通过名字找到表单中的电子邮件和密码字段，然后再使
        用send_keys()方法在各字段中填入值。表单的提交通过在提交按钮上调用click()方法完成。
        此外，还要检查针对用户定制的欢迎消息，以确保登录成功且浏览器显示的是首页。

        最后一部分是找到导航条中的"Profile"链接，然后点击。为证实治疗页已经加载，测试要在页面
        源码中搜索内容为用户名的标题。

        :return:
        """
        # 进入首页
        self.client.get('http://localhost:5000/')
        self.assertTrue(re.search('Hello,\s+Stranger!',
                                  self.client.page_source))

        # 进入登录页面
        self.client.find_element_by_link_text('Log In').click()
        self.assertTrue('<h1>Login</h1>' in self.client.page_source)

        # 登录
        self.client.find_element_by_link_name(
            'email').send_keys('john@example.com')
        self.client.find_element_by_link_name('password').send_keys('cat')
        self.client.find_element_by_link_name('submit').click()
        self.assertTrue(re.search('Hello,\s+john!', self.client.page_source))

        # 进入用户个人资料页面
        self.client.find_element_by_link_text('Profile').click()
        self.assertTrue('<h1>john</h1>' in self.client.page_source)