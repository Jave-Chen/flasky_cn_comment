# coding = utf-8

""" 单元测试文件
"""

from flask import current_app
import unittest

from app import create_app, db


class BasicsTestCase(unittest.TestCase):
    """ 基本测试类
    """
    def setup(self):
        """ 创建测试环境

        使用测试配置创建程序，激活上下文；创建一个全新的数据库。
        数据库和程序上下文在tearDown方法中删除。

        """
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        self.assertTrue(current_app.config['TESTING'])
