# coding=utf-8


""" 启动脚本

选项：
    --coverage 代码覆盖测试，检查代码覆盖情况，统计单元测试检查了多少程序功能，说明

数据库常用命令：
    db.create_all() # 数据库初始化
    db.drop_all() # 删除数据库
    db.session.add(someDbModel) # 添加和修改行数据
    db.session.delete(someDbModel)  # 删除行数据
    db.session.commit() # 提交会话

    python manage.py db upgrade


管理常用命令：
    注册新用户命令：
        python manage.py shell
        u = User(email='john@example.com', username='john', password='cat')
        db.session.add(u)
        db.session.commit()

"""


import os

# 覆盖检测
# coverage.coverage()用于启动覆盖检测引擎。
#   branch=True选项开启分支覆盖分析，除了跟踪哪行代码已经执行外，还要检查每条语句的True分支
#   和False分支是否都执行了。
#   include选项用来限制程序包中文件的分析范围，只对这些文件中的代码进行覆盖检查。如果不指定
#   include选项，虚拟环境中安装的全部扩展和测试代码都会包含进覆盖报告中，给报告添加很多杂项。
COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage
    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

if os.path.exists('.env'):
    print('Importing environment from .env...')
    for line in open('.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

from app import create_app, db
from app.models import User, Follow, Role, Permission, Post, Comment
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell

# 从环境变量FLASKY_CONFIG中读取配置名，否则使用默认配置
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
# 初始化Flask-Migrate
migrate = Migrate(app, db)


def make_shell_context():
    """ 初始化Flask-Script
    """
    return dict(
        app=app, db=db, User=User, Follow=Follow, Role=Role,
        Permission=Permission, Post=Post, Comment=Comment
    )
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)


@manager.command
def test(converage=False):
    """Run the unit tests.

    执行完所有测试后，函数会在终端输出报告，同时生成一个HTML文件。

    """
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import sys
        os.environ['FLASK_COVERAGE'] = '1'
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coerage')
        COV.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        COV.erase()


@manager.command
def profile(length=25, profile_dir=None):
    """Start the application under the code profiler.
    在请求分析器的监视下运行程序

    使用python manage.py profile启动程序后，终端会显示每条请求的分析数据，其中包含运行最慢
    的25个函数。--length选项可以修改报告中显示的函数数量。如果指定了--profile-dir选项，每条
    请求的分析数据就会保存到指定目录下的一个文件中。

    """
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
        profile_dir=profile_dir)
    app.run()


@manager.command
def deploy():
    """Run deployment tasks.
    部署命令

    每次安装或升级程序时只需运行deploy命令就能完成所有操作。

    """
    from flask_migrate import upgrade
    from app.models import Role, User

    # 把数据库迁移到最新修订版本
    upgrade()

    # 创建用户角色
    Role.insert_roles()

    # 让所有用户都关注自己
    User.add_self_follows()


if __name__ == '__main__':
    manager.run()
