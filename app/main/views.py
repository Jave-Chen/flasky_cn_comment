# coding=utf-8

""" 视图文件

"""

from flask import render_template, redirect, url_for, abort
from flask import flash, request, current_app, make_response
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries

from . import main
from .forms import EditProfileForm, EditProfileAdminForm
from .forms import PostForm, CommentForm
from .. import db
from ..models import Permission, Role, User, Post, Comment
from ..decorators import admin_required, permission_required


@main.after_app_request
def after_request(response):
    """ 报告缓慢的数据库查询

    获取Flask-SQLAlchemy记录的查询时间并把执行缓慢的查询写入日志。

    使用after_app_request修饰器，在视图函数处理完请求之后执行。Flask把响应对象传给
    after_app_request处理程序，以防需要修改响应。

    after_app_request处理程序遍历get_debug_queries()函数获取的列表，把持续时间比设定阀值
    长的查询写入日志。写入的日志被设为“警告”等级。如果换成“错误”等级，发现缓慢的查询时还会发送
    电子邮件。

    默认情况下，get_debug_queries()函数只在调试模式中可用。但是数据库性能问题很少发生在开发
    阶段，因为开发过程中使用的数据库较小。因此，在生产环境中使用该选项才能发挥作用。

    :param response:
    :return:
    """
    for query in get_debug_queries():
        if (query.duration >=
                current_app.config['FLASKY_SLOW_DB_QUERY_TIME']):
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %f\nContext: %s\n'
                % (query.statement, query.parameters, query.duratioin,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    """ 关闭服务器路由

    只有当程序运行在测试环境中时，这个关系服务器的路由才可用，在其他配置中调用时将不起作用。在
    实际过程中，关闭服务器时要调用Werkzegu在环境中提供的关系函数。调用这个函数且请求处理完成
    后，开发服务器自动退出。

    :return:
    """
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'

@main.route('/', methods=['GET', 'POST'])
def index():
    """

        路由装饰器由蓝本提供。
        在蓝本中Flask会为蓝本中的全部端点加上一个命名空间，这样就可以在不通的蓝本中使用
        相同的端点名定义视图函数，而不会产生冲突。
        命名空间就是蓝本的名字（Blueprint构造函数的第一个参数），所以视图函数index()
        注册的端点名是main.index，其URL使用url_for('main.index')获取。
        url_for()函数可以省略当前蓝本名，简写成url_for('.index')，这种写法，命名空间
        是当前请求所在的蓝本。跨蓝本的重定向必须使用带有命名空间的端点名。

        这个视图把表单和完整的博客文章列表传给模版。文章列表按照时间戳进行降序排列。博客文章采
        取惯常处理方式，如果提交的数据能通过验证就创建一个新Post实例。
        在发布新文章之前，要检查当前用户是否有写文章的权限。
        新文章对象的author属性值为表达式current_user._get_current_object()。变量current_user
        由Flask-Login提供，和所有上下文变量一样，也是通过线程内的代理对象实现。这个对象的表现
        类似用户对象，但实际上却是一个轻度包装，包含真正的用户对象。数据库需要真正的用户对象，
        因此要调用_get_current_object()方法。

        渲染的页数从请求的查询字符串(request.args)中获取，如果没有明确指定，则默
        认渲染第一页。参数type=int保证参数无法转换成整数时，返回默认值。

        为了显示某页中的记录，需要使用Flask-SQLAlchemy提供的paginate()
        方法。页数是paginate()方法的第一个参数，也是唯一必需的参数。可选参数per_page
        用来指定每页显示的记录数量；若没有指定，着默认显示20个记录。另一个可选参数为error_out，
        当其设为True时（默认值），如果请求的页数超出了范围，则会返回404错误；如果设为False，
        页数超过范围时会返回一个空列表。为了能够很便利地配置每页显示的记录数量，参数per_page
        的值从程序的环境变量FLASK_POSTS_PER_PAGE中读取。

    安全起见，只提交Markdown源文本，在服务器上使用Markdown将其转换成HTML格式。得到HTML格式
    后，再使用Bleach进行清理，确保其中只包含几个允许使用的HTML标签。
    把Markdown格式的博客文章转换成HTML的过程可以在_posts.html模板中完成，但这样做的效率不高，
    因为每次渲染页面都要转换一次。为了避免重复工作，我们可在创建博客文章时做一次转换。转换后的文
    章HTML代码缓存在Post模型的body_html字段中，在模版中直接调用。文章的Markdown源文本保存在
    数据库中，以便再次编辑。

    显示所有博客文章或只显示所关注用户的文章。
    决定显示所有博客文章还是只显示所关注用户文章的选项储存在cookie的show_followed字段中，如
    果其值为非空字符串，则表示只显示所关注用户的文章。cookie以request.cookies字典的形式存储
    在请求对象中。这个cookie的值会转换成bool值，根据得到的值设定本地变量query值。query的值
    决定最终获取所有博客文章的查询，或是获取过滤后的博客文章查询。显示所有用户的文章时，要使用
    顶级查询Post.query；如果限制只显示所关注用户的文章，要使用最近添加的
    User.followed_posts属性。然后将本地变量query中保存的查询进行分页，像往常一样将其传入模
    板。

    """
    form = PostForm()
    if (current_user.can(Permission.WRITE_ARTICLES)
            and form.validate_on_submit()):
        post = Post(body=form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page,
        per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False
    )
    posts = pagination.items
    return render_template(
        'index.html',
        form=form,
        posts=posts,
        show_followed=show_followed,
        pagination=pagination
    )


@main.route('/user/<username>')
def user(username):
    """ 用户资料页面路由

    视图在数据库中搜索URL中制定的用户名，如果找到，则渲染user.html模板，并把用户名作为
    参数传入模板。如果用户名不存在，则返回404错误。

    :param username:
    :return:
    """
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page,
        per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False
    )
    posts = pagination.items
    return render_template(
        'user.html',
        user=user,
        posts=posts,
        pagination=pagination
    )


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """ 普通用户资料编辑路由

    在显示表单之前，视图为所有字段设定了初始值。对于所有给定字段，这一工作都是通过把初始值赋值給
    form.<field.name>.data完成的。当form.validate_on_submit()返回False时，表单中的3个
    字段都使用current_user中保存的初始值。提交表单后，表单字段的data属性中保存有更新后的值。
    提交表单后，表单字段的data属性中保存有更新后的值，因此可以将其赋值给用户对象中的各字段，然后
    再把用户对象添加到数据库会话中。
  :return:
    """
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    """ 管理员资料编辑路由

    用户由id指定，因此可使用Flask-SQLAlchemy提供的get_or_404()函数，
    如果提供的id不正确。则会返回404错误。

    设定用户角色字段的SelectField初始值时，role_id被赋值给了field.role.data，
    这么做的原因在于choices属性中设置的元组列表使用数字标识符表示各选项。表单提交后，id从
    字段的data属性中提取，并且查询时会使用提取出来的id值加载角色对象。表单中声明SelectField
    时使用coerce=int参数，其作用是保证这个字段的data属性值是整数。


    :param id:
    :return:
    """
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    """ 文章的固定链接

    为每篇文章提供唯一的URL地址，以便分享和引用文章。

    这个视图函数实例化一个评论表单，并将其转入post.html模板，以便渲染。提交表单后，插入新评论
    的逻辑和处理博客文章的过程差不多。和Post模型一样，评论的author字段也不能直接设为
    current_user，因为这个变量是上下文代理对象。真正的User对象要使用表达式
    current_user._get_current_object()获取。

    评论按照时间戳顺序排序，新评论显示在列表的底部。提交评论后，请求结果是一个重定向，转回之前
    的URL，但是在url_for()函数的参数中把page设为-1，这是个特殊的页数，用来请求评论的最后一
    页，所以刚提交的评论才会出现在页面中。程序从查询字符串中获取页数，发现值为-1时，会计算评论
    的总量和总页数，得出真正要显示的页数。

    文章的评论列表通过post.comments一对多关系获取，按照时间戳顺序进行排序，再使用与博客文章
    系统的技术分页显示。评论列表对象和分页对象都传入了模板，以便渲染。
    FLASKY_COMMENTS_PER_PAGE配置变量也被加入config.py中，用来控制每页显示的评论数量。

    评论的渲染过程在新模板_comments.html中进行，类似于_posts.html，但使用的CSS类不同。
    _comments.html模板要引入post.html中，放在文章正文下方，后面再显示分页导航。

    :param id:
    :return:
    """
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            body=form.body.data,
            post=post,
            author=current_user._get_current_object()
        )
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = ((post.comments.count() - 1) //
                current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1)
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page,
        per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False
    )
    comments = pagination.items
    return render_template(
        'post.html',
        posts=[post],
        form=form,
        comments=comments,
        pagination=pagination
    )


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """ 编辑博客文章路由

    只允许博客文章的作者编辑文章，但管理员例外，管理员能编辑所有用户的文章。如果用户试图编辑其他
    用户的文章，视图函数会返回403错误。

    :param id:
    :return:
    """
    post = Post.query.get_or_404(id)
    if (current_user != post.author
            and not current_user.can(Permission.ADMINISTER)):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    """ 关注路由和视图

    这个视图先加载请求的用户，确保用户存在且当前登录用户还没有关注这个用户，然后调用User模型中
    定义的辅助方法follow(),用以联结两个用户。

    :param username:
    :return:
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    """ 取消关注路由

    :param username:
    :return:
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('Your are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    """ 关注者路由和视图

    函数加载并验证请求的用户，然后分页显示该用户follow关系。由于查询关注者返回的是Follow实例
    列表，为了渲染方便，我们将其转换为一个新列表，列表中的各元素包含user和timestamp字段。

    :param username:
    :return:
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page,
        per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False
    )
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
                for item in pagination.items]
    return render_template(
        'followers.html',
        user=user,
        title="Followers of",
        endpoint='.followers',
        pagination=pagination,
        follows=follows
    )


@main.route('/followed-by/<username>')
def followed_by(username):
    """ 被关注路由和视图

    :param username:
    :return:
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page,
        per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False
    )
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
                for item in pagination.items]
    return render_template(
        'followers.html',
        user=user,
        title="Follower by",
        endpoint='.followed_by',
        pagination=pagination,
        follows=follows
    )


@main.route('/all')
@login_required
def show_all():
    """ 查询所有用户的文章

    cookie只能在相应对象中设置，因此show_all和show_followed这两个路由不能依赖Flask，要使
    用make_response()方法创建响应对象。

    set_cookie()函数的前两个参数分别是cookie名和值。可选的max_age参数设置cookie的过期时
    间，单位为妙。如果不制定参数max_age，浏览器关闭后cookie就会过期。默认过期时间设为30天。

    :return:
    """
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30*24**60*60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    """ 查询所关注用户的文章

    :return:
    """
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp


@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate():
    """ 管理评论的路由

    路由从数据库中读取一页评论，将其传入模板进行渲染。除了评论列表之外，还把分页对象和当前页数
    传入模板。

    :return:
    """
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page,
        per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False
    )
    comments = pagination.items
    return render_template(
        'moderate.html',
        comments=comments,
        pagination=pagination,
        page=page
    )


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_enable(id):
    """ 启用评论路由

    将评论的disable字段设为false，在更新到数据库。最后重定向到评论管理页面，如果查询字符串中
    指定了page参数，会将其传入重定向操作。_comments.html模板中的按钮指定了page参数，重定向
    后会返回之前的页面。

    :param id:
    :return:
    """
    comment = Comment.query.get_or_404(id)
    comment.disable = False
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_disable(id):
    """ 禁用评论路由

    :param id:
    :return:
    """
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))
