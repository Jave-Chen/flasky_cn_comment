# coding=utf-8
""" 数据模型类文件


导入模块：
    Flask-Login：管理已登录用户的用户会话
    Werkzeug: 计算密码散列值并进行核对
    itsdangerous: 生成并核对加密安全令牌

    Flask-Mail: 发送与认证相关的电子邮件
    Flask-Bootstrap: HTML模版
    Flask-WTF: web表单

"""

from datetime import datetime

from flask import current_app, request, url_for
# 管理已登录用户的用户会话
from flask_login import UserMixin, AnonymousUserMixin

import hashlib
# 计算密码
from werkzeug.security import generate_password_hash, check_password_hash
# TimedJSONWebSignatureSerializer类生成具有过期时间的JSON Web签名。
# 这个类的构造函数接收的参数是一个密钥，在Flask程序中可使用SECRET_KEY设置。
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach

# 原语句 from app.exceptions import ValidationError
from app.exceptions import ValidationError
from . import db, login_manager


class Permission(object):
    """ 程序权限常量

    操作的权限使用8位表示，现在只用了其中5位，其他3位用于将来的扩充。

    """
    FOLLOW = 0x01   # 关注用户，关注其他用户
    COMMENT = 0x02  # 在他人的文章中发表评论，在他人撰写的文章中发布评论
    WRITE_ARTICLES = 0x04   # 写文章，写原创文章
    MODERATE_COMMENTS = 0x08    # 管理他人发表的评论，查处发表的不当评论
    ADMINISTER = 0x80   # 管理员权限，管理网站


class Role(db.Model):
    """ 角色权限模型

    属性：
        id: 整数,记录序号
        name: 64位字符串，角色权限
        default: 布尔值，默认角色，用户这次时会被设置为default为True的角色。
            所以只有一个角色的default字段设为True其他都设为False。
        permissions: 整数，权限标志位
            用户角色    权限              说明
            匿名        0b00000000(0x00) 未登录的用户。在程序中只有阅读权限
            用户        0b00000111(0x07) 具有发布文章，发表评论和关注其他用户的权限。这是新用户的默认角色
            协管员       0b00001111(0x0f) 增加审查不当评论的权限
            管理员       0b11111111(0xff) 具有所有权限，包括修改其他用户所属角色的权限

    方法：

    """
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        """ 角色表记录更新方法

        在roles数组，或者权限值改变以后，运行该方法对Role表中的记录进行更新。

        方法并不直接创建新角色对象，而是通过角色名查找现有的角色，然后再进行更新。只有当
        数据库中没有某个角色名时才会创建新角色对象。
        要想添加新角色，或者修改角色的权限，修改roles数组，在调用方法即可。
        “匿名”角色不需要在数据库中表示出来，这个角色的作用就是为了表示不在数据库中的用户。

        :return:
        """
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    """ 用户关注模型

    属性:
        follower_id: 关注者ID
        followed_id: 被关注者ID
        timestamp: 关注时间

    SQLAlchemy不能直接使用这个关联表，因为如果这么做程序就无法访问其中的自定义字段。相反地，
    要把这个多对多的关系的左右两侧拆分成两个基本的一对多关系，而且要定义成标准的关系。

    """
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class User(UserMixin, db.Model):
    """ 用户模型

    生成用户密码散列

    类模型：
        UserMixin: Flask-Login提供，默认实现了使用Flask-Login类必须的方法。

    类属性：
        email: 用户使用电子邮件地址登录
        name: 用户的真实姓名
        location: 所在地
        about_me: 自我介绍
        member_since: 注册日期
        last_seen: 最后访问日期，每次访问后使用ping方法刷新
        followed: 关注者
        followers: 被关注者

    followed和followers关系都定义为单独的一对多关系。为了消除外键间的歧义，定义关系时必须使
    用可选参数foreign_keys指定的外键。而且，db.backref()参数并不是指定这两个关系之间的引用
    关系，而是回引Follow模型。

    回引中的lazy参数指定为joined。这个lazy模式可以实现立即从联结查询中加载相关对象。例如，如
    果某个用户关注了100个用户，调用user.follower.all()后会返回一个列表，其中包含100个Follow
    实例，每一个实例的follower和followed回引属性都指向相应的用户。设定为lazy='joined'模式，
    就可在一次数据库查询完成这些操作。如果把lazy设为默认值select，那么首次访问follower和followed
    属性时才会加载对应的用户，而且每个属性都需要一个单独的查询，这就意味着获取全部被关注用户时
    需要增加100次额外的数据库查询。

    这两个关系中，User一侧设定的lazy参数作用不一样。lazy参数都在“一”这一侧设定，返回的结果是
    “多”这一侧中的记录。使用dynamic值，因此关系属性不会直接返回记录，而是返回查询对象，所以在
    执行查询之前还可以添加额外的过滤器。

    cascade参数配置在对象上执行的操作对相关对象的影响。比如，层叠选项可设定为：将用户添加到数
    据库会话后，要自动把所有的关系都添加到会话中。层叠选项的默认值能满足大多数情况的需求，但是
    这个多对多关系来说却不合用。删除对象时，默认的层叠行为是把对象链接的所有相关对象的外键值设
    为空值。当在关联表中，删除记录后正确的行为应该是把指向该记录的实体也删除，因为这样能有效销
    毁联接。这就是层叠项值delete-orphan的作用。设为all,delete-orphan的意思是启用所有默认
    层叠属性，而且还要删除孤儿记录。


    类方法：
        ping: 用户每次访问网站后，更新用户最后访问时间(last_seen）字段。

    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    # datetime.utcnow后没有()，表示default接受函数作为默认值。
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    followed = db.relationship(
        'Follow',
        foreign_keys=[Follow.follower_id],
        backref=db.backref('follower', lazy='joined'),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    followers = db.relationship(
        'Follow',
        foreign_keys=[Follow.followed_id],
        backref=db.backref('followed', lazy='joined'),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        """ 生成虚拟用户

        用户的电子邮件地址和用户名必须是唯一的，但ForgeryPy随机生成这些信息，因此有重
        复的风险。如果发生了这种不太可能的情况，提价数据库会话时会抛出IntegrityError
        异常。这个异常的处理方式是，在继续操作之前回滚会话。在循环生成重复内容不会把用户
        写入数据库，因此生成的虚拟用户总数可能会比预期少。

        """
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(
                email=forgery_py.internet.email_address(),
                username=forgery_py.internet.user_name(True),
                password=forgery_py.lorem_ipsum.word(),
                confirmed=True,
                name=forgery_py.name.full_name(),
                location=forgery_py.address.city(),
                about_me=forgery_py.lorem_ipsum.sentence(),
                member_since=forgery_py.date.date(True)
            )
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        """ 把用户设为自己的关注者

        用户在查看所关注用户可以看到自己的文章。

        因为用户自己关注自己。用户资料页显示的关注者和被关注者的数量都增加了1个。为了显示准确，
        这些数字要减去1，需要在模版中渲染成{{ user.followers.count() - 1 }}和
        {{ user.followed.count() - 1 }}。然后，还要调整关注用户和被关注用户的列表，不显
        示自己。

        """
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

    def __init__(self, **kwargs):
        """ 用户类初始化
            处理管理员角色，用户角色初始化，用户头像hash保存

        用户在程序中注册账户时，会被赋予适当的角色。大多数用户在注册时赋予的角色都是“用户”，
        因为这是默认角色。唯一的例外是管理员，管理员在最开始就应该赋予“管理员”角色。管理员
        由保存在设置变量FLASKY_ADMIN中的电子邮件地址识别，只要这个电子邮件地址出现在注册
        请求中，就会被赋予正确的角色。

        User类的构造函数首先调用基类的构造函数，如果创建基类对象后还没有角色，则根据电子邮
        件地址决定将其设为管理员还是默认角色。

        用户注册时把自己设为自己的关注者，这样在用户查看所关注用户文章列表时，也能看到自己的文
        章。

        """
        # 原语句 super(User, self).__init__(**kwargs)
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(
                self.email.encode('utf-8')).hexdigest()
        self.followed.append(Follow(followed=self))

    @property
    def password(self):
        """ 用户密码

        （通过property装饰器）将password属性设置为只写。

        输入：
            self: 自身类；

        返回值：
            无。

        异常:
            password不可读，读取时抛出异常。
        """
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        """ 设置用户密码字段

        将密码字段设置为密码的hash值，不存储密码明文。

        输入：
            self: 自身类；
            password: 密码明文；

        输出：
            无直接返回值，但将 User.password_hash 设置为原始密码的hash值。

        异常：
            无。
        """
        # generate_password_hash(password, method=pbkdf2:sha1, salt_length=8)
        # 这个函数将原始密码作为输入，以字符串形式输出密码的散列值，输出的值
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        """ 密码校验函数

        校验User.password_hash值和用户输入的password hash值是否一致。

        输入：
            self: 自身类
            password: 用户输入密码

        返回值：
            True: 如用户输入密码的hash值与数据库中password_hash值一致；
            False: 如用户输入密码的hash值与数据库中password_hash值不一致；
        """
        # check_password_hash(hash, password)
        # 这个函数的参数是数据库中取回的密码散列和用户输入的密码。
        # 返回值
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        """ 生成认证令牌，有效期默认为1小时

            根据服务器配置的 SECRET_KEY 和 用户id 生成认证链接口令，后续通过邮件发送到用户邮箱进行确认。

        Serializer类生成具有过期时间的JSON Web签名。这个类的构造函数接收两个参数：
            SECRET_KEY: 密钥，在配置文件中设置
            expiration: 令牌过期时间，调用时默认设置为1小时
            类的dumps()方法为{'confirm': self.id}生成一个加密签名，然后再对数据和签名进行序列化，
            生成令牌字符串。

        """
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        """ 检验令牌

        如果检验令牌通过，则将confirmed属性设置为True。同时还检查令牌中的id是否和存储在current_user
        中已登录的用户匹配。防止恶意用户知道如何生成签名令牌以后，也不能确认他人的账户。

        Serializer类提供loads()方法解密令牌，其唯一的参数是令牌字符串。这个方法检验签名和过期时间，
        如果通过则返回原始数据。如果提供给loads()方法的令牌不正确或过期了，则抛出异常。

        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        """ 生成密码重置口令


        """
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'rest': self.id})

    def reset_password(self, token, new_password):
        """ 重置密码
            校验重置口令后
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        """ 生成邮箱变更口令
        """
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token):
        """ 更改邮箱
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_has = hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        return True

    def can(self, permissions):
        """ 用户权限判断

        检查用户是否有指定的权限。
        方法在请求和赋予角色这两种权限之间进行位与操作。如果角色中包含请求的所有权限位，则返回
        True，表示允许用户执行此项操作。

        """
        return (self.role is not None
                    and (self.role.permissions & permissions) == permissions)

    def is_administrator(self):
        """ 判断是否管理员

        检查管理员权限的功能经常用到，因此使用单独的方法实现。

        """
        return self.can(Permission.ADMINISTER)

    def ping(self):
        """ 更新用户最后登录时间
        """
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def gravatar(self, size=100, default='identicon', rating='g'):
        """ 生成Gravatar 头像URL获取用户头像

        选择标准的或加密的Gravatar URL基以匹配用户的安全需求。头像的URL由URL
        基、用户电子邮件地址的MD5散列值和参数组成，而且各参数都是默认值。

        生成头像时要生成MD5值。由于用户电子邮件地址的MD5散列值是不变的，模型初始化过程中
        会计算电子邮件的散列值，然后存入数据库，若用户更新了电子邮件地址，则会重新计算散列
        值。gravatar()方法会使用模型中保存的散列值，若模型中没有，就和之前一样计算电子邮
        件地址的散列值。

        """
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = (self.avatar_hash or
                hashlib.md5(self.email.encode('utf-8')).hexdigest())
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def follow(self, user):
        """ 用户关注

        方法把Follow实例插入关联表，从而把关注者和被关注者联接起来，并让程序有机会设定自定义
        字段的值，然后像往常一样，把这个实例对象添加到数据库会话中。

        """
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)

    def unfollow(self, user):
        """ 取消关注

        方法使用followed关系找到联接用户和关注用户的Follow实例。若要销毁这两个用户之间的联接，
        只需删除这个Follow对象即可。

        """
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    def is_following(self, user):
        """ 判断是否关注其他用户
        """
        return (self.followed.filter_by(follower_id=user.id).first()
                    is not None)

    def is_followed_by(self, user):
        """ 判断用户是否被其他用户关注
        """
        return (self.followers.filter_by(follower_id=user.id).first()
                    is not None)

    @property
    def followed_posts(self):
        """ 所关注用户发布的文章

        若想获得A所关注用户发布的文章，就要合并posts表和follows表。首先过滤follow表，只留下
        关注者为A的记录。然后过滤posts表，留下author_id和过滤后的follow表中followed_id
        相等的记录，把两次过滤结果合并，组成临时联结表。

        """
        return (Post.query.join(Follow,
                                Follow.followed_id == Post.author_id).filter(
                                    Follow.follower_id == self.id))

    def to_json(self):
        """ 把用户转换成JSON格式的序列化字典

        为了保护隐私，email，role等属性没有加入响应。说明，提供给客户端的资源表示没必要和数据
        库模型的内部表示完全一致。

        """
        json_user = {
            'url': url_for('api.get_user', id=self.id, _external=True),
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id=self.id, _external=True),
            'followed_posts': url_for('api.get_user_followed_posts',
                                      id=self.id, _external=True),
            'post_count': self.posts.count()
        }
        return json_user

    def generate_auth_token(self, expiration):
        """ 生成认证口令

        使用编码后的用户id字段值生成一个签名令牌，还制定了以秒为单位的过期时间。

        """
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    @staticmethod
    def verify_auth_token(token):
        """ 验证认证口令

        接受一个令牌，如果令牌可用就返回对应的用户。verify_auth_token()是静态方法，因为只有
        解码令牌后才能知道用户是谁。

        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def __repr__(self):
        """ 用户类描述
        """
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    """ 匿名用户类

    继承自Flask-Login中的AnonymousUserMixin类，并将其设为用户未登陆时
    current_user的值。

    """

    def can(self, permissions):
        """ 匿名用户权限
            匿名用户无任何权限
        """
        return False

    def is_administrator(self):
        """ 管理员判断
            匿名用户为非管理员
        """
        return False


# 将未登录用户的current_user值设置为AnonymousUser类
login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    """ 用户回调函数

    用户的回调函数接收以Unicode字符串形式表示的用户标识符。如果找到用户则返回用户对象，否则返回None。

    * Flask-Login 要求一个回调函数，使用指定的标识符加载用户。

    参数：
        user_id: 用户的唯一标识符

    返回值：
        user_id与参数值一致的User类对象。如无结果，则返回None.

    异常:
        无。

    """
    return User.query.get(int(user_id))


class Post(db.Model):
    """ 文章模型

    属性：
        body: 正文
        body_html: 博客文章HTML代码。
        timestamp: 时间戳
        author_id: 和User模型之间一对多关系


    """
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        """ 生成虚拟博客文章

        随机生成文章时要为每篇文章随机指定一个用户。使用offset()查询过滤器。这个过滤器
        会跳过参数中指定的记录数量。通过设定一个随机的偏移值，再调用first()方法，就能
        每次都获得一个不同的随机用户。

        """
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1, 5)),
                     timestamp=forgery_py.date.date(True),
                     author=u)
            db.session.add(p)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        """ 发表文章改变时

        把body字段中的文本渲染成HTML格式，并保存在body_html中。
        首先，markdown()函数初步把Markdown文本转换为HTML。然后把得到的结果和允许使用的HTML
        标签列表传给clean()函数。clean()函数删除所有不在白名单中的标签。最后调用Bleach提供
        的linkify()函数将纯文本中的URL转换成适当的<a>链接。
        Markdown规范没有为自动生成链接提供官方支持。PageDown以扩展的形式实现了这个功能。因此
        在服务器上调用linkify()函数。

        """
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote',
                        'code', 'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.body_html = bleach.linkify(
            bleach.clean(
                markdown(value, output_format='html'),
                tags=allowed_tags,
                strip=True
            )
        )

    def to_json(self):
        """ 把文章转换成JSON格式的序列化字典

        url、author和comments字段要分别返回各自资源的URL，因此使用url_for()生成，所调用
        的路由即将在API蓝本中定义。所有url_for()方法都指定了参数_external=True，这么做是
        为了生成完整的URL，而不是生成传统Web程序中经常使用的相对URL。

        表示资源时可以使用虚构的属性。comment_count字段是博客文章的评论数量，并不是模型的真
        实属性，它之所以包含在这个资源中是为了便于客户端使用。

        """
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_uer', id=self.author_id,
                              _external=True),
            'comments': url_for('api.get_post_comments', id=self.id,
                                _external=True),
            'comment_count': self.comments.count()
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        """ 从JSON格式数据创建一篇博客文章

        使用JSON字典中的body属性，而把body_html属性忽略，因为只要body属性的值发生变化，就
        会触发一个SQLAlchemy事件，自动在服务器端渲染Markdown。除非允许客户端填日期，负责无
        需制定timestamp属性。由于客户端无权选择博客文章的作者，所以没有使用author字段。
        author字段唯一能使用的值是通过认证的用户。comments和comment_count属性使用数据库自
        动生成，因此其中没有创建模型所需的有用信息。url字段也被忽略了，因为在这个实现中资源的
        URL由服务器派生，而不是客户端。

        如果没有body字段或者其值为空，from_json()方法会抛出ValidationError异常。在这种情
        况下，抛出异常才是处理错误的正确方式，因为from_json()方法并没有掌握处理问题的足够信
        息，唯有把错误调用者，由上层代码处理这个错误。

        """
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        return Post(body=body)


# 监听post.body部分的改变
db.event.listen(Post.body, 'set', Post.on_changed_body)


class Comment(db.Model):
    """ 评论模型

    Comment模型的属性几乎和Post模型一样，不过多了一个disabled字段。这是个bool字段，协管员通
    过这个字段查禁不当评论。和博客文章一样，评论也定义了一个事件，在修改body字段内容时触发，自
    动把Markdown文本转换成HTML。评论相对较短，对Markdown中允许使用的HTML标签要求更严格，要
    删除与段落相关的标签，只留下格式化字符的标签。

    """
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        """ 评论内容修改
        """
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em',
                        'i', 'strong']
        target.body_html = bleach.linkify(
            bleach.clean(
                markdown(value, output_format='html'),
                tags=allowed_tags,
                strip=True
            )
        )

    def to_json(self):
        """ 模型数据转换为JSON格式
        """
        json_comment = {
            'url': url_for('api.get_comment', id=self.id, _external=True),
            'post': url_for('api.get_post', id=self.post_id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id, _external=True),
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        """ 获取通过JSON格式发送的评论内容
        """
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)


# 监听评论内容改变
db.event.listen(Comment.body, 'set', Comment.on_changed_body)
