# encoding=utf-8

from flask import jsonify, request, g, abort, url_for, current_app
from . import api
from .decorators import permission_required
from .errors import forbidden
from .. import db
from ..models import Post, Permission


@api.route('/posts/')
def get_posts():
    """ 获取文章集合

    使用列表推导生成所有文章的JSON版本。
    JSON格式响应中的posts字段依旧包含各篇文章，当现在这只是完整集合的一部分。如果资源有上一页
    和下一页，prev和next字段分别表示上一页和下一页资源的URL。count是集合中博客文章的总数。

    :return:
    """
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.paginate(
        page,
        per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False
    )
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_posts', page=page-1, _external=True)
    next = None
    if pagination.has_next:
        next = url_for('api.get_posts', page=page+1, _external=True)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/posts/<int:id>')
def get_post(id):
    """ 返回单篇博客文章

    如果在数据库中没找到指定id对应的文章，则返回404错误。

    :param id:
    :return:
    """
    post = Post.query.get_or_404(id)
    return jsonify(post.to_json())


@api.route('/posts/', methods=['POST'])
@permission_required(Permission.WRITE_ARTICLES)
def new_post():
    """ 把一篇新博客文章插入数据库

    接受POST请求添加文章。这个视图使用permission_required修饰器，确保通过认证的用户有写博客
    文章的权限。博客文章从JSON数据中创建，其作者就是通过认证的用户。文章写入数据库后，会返回
    201状态码，并把Location首部的值设为刚创建的这个资源的URL。

    为便于客户端操作，响应的主体中包含了新建的资源。客户端就无需在创建资源后再立即发起一个GET
    请求以获取资源。

    :return:
    """
    post = Post.from_json(request.json)
    post.author = g.current_user
    db.session.add(post)
    db.session.commit()
    return (jsonify(post.to_json()),
            201,
            {'Location': url_for('api.get_post', id=post.id, _external=True)}
    )


@api.route('/posts/<int:id>', methods=['PUT'])
@permission_required(Permission.WRITE_ARTICLES)
def edit_post(id):
    """ 更新已有博客文章

    通过PUT请求更新已有博客文章。
    修饰器用来检查用户是否有写博客文章的权限，但为了确保用户能编辑博客文章，这个函数还要保证用
    户是文章的作者或者是管理员。这个检查直接添加到视图函数中。

    :param id:
    :return:
    """
    post = Post.query.get_or_404(id)
    if (g.current_user != post.author
            and not g.current_user.can(Permission.ADMINISTER)):
        return forbidden('Insufficient permissions')
    post.body = request.json.get('body', post.body)
    db.session.add(post)
    return jsonify(post.to_json())