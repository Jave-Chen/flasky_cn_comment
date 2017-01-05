# coding=utf-8
# API蓝本构造文件

from flask import Blueprint

api = Blueprint('api', __name__)

from .import authentication, posts, users, comments, errors