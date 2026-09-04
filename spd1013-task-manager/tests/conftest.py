# -*- coding: utf-8 -*-
"""pytest 公共夹具：临时数据库 + 已登录的测试客户端。

个人学习任务管理与数据分析系统 · 佟政慷 239001013 · SPD-1013
"""
import os
import sys
import tempfile
from datetime import date, timedelta

import pytest

# 让 tests/ 下的用例能 import 到项目根目录的 config 与 spdapp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TestConfig      # noqa: E402
from spdapp import create_app      # noqa: E402


@pytest.fixture
def app():
    """每个用例一个全新的临时数据库文件。

    刻意不用 :memory:——SQLite 的内存库是「一个连接一个库」，
    而应用每个请求都会新建连接，用内存库时上一步写进去的数据下一个请求就查不到。
    """
    fd, db_path = tempfile.mkstemp(prefix="spd_test_", suffix=".db")
    os.close(fd)
    backup_dir = tempfile.mkdtemp(prefix="spd_backup_")

    class _Cfg(TestConfig):
        DATABASE = db_path
        BACKUP_DIR = backup_dir

    # 空库 → create_app 内部自动建表并写入账号与课程（TestConfig 关闭了演示任务）
    application = create_app(_Cfg)
    yield application

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()
@pytest.fixture
def logged_in(app, client):
    """走真实登录流程，后续用例可直接访问受保护页面。"""
    resp = client.post("/login", data={
        "username": app.config["DEFAULT_USERNAME"],
        "password": app.config["DEFAULT_PASSWORD"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


@pytest.fixture
def courses(app):
    """初始课程列表（id 与名称），供筛选用例使用。"""
    from spdapp.models import course_repo
    with app.app_context():
        return [{"id": r["id"], "name": r["name"]} for r in course_repo.list_courses()]


@pytest.fixture
def api_headers(app):
    return {"X-API-KEY": app.config["API_KEY"]}


def day(offset=0):
    """相对今天偏移若干天的 YYYY-MM-DD 文本。"""
    return (date.today() + timedelta(days=offset)).isoformat()


@pytest.fixture
def add_task(logged_in):
    """通过页面表单新增任务，返回响应对象（CSRF 在测试配置里已关闭）。"""
    def _add(title="测试任务", course_id="", due_date=None, priority="2",
             status=False, note=""):
        data = {
            "title": title,
            "course_id": str(course_id) if course_id else "",
            "due_date": due_date or day(0),
            "priority": str(priority),
            "note": note,
        }
        if status:
            data["status"] = "1"
        return logged_in.post("/tasks/new", data=data, follow_redirects=True)
    return _add


@pytest.fixture
def db_tasks(app):
    """直接查库取任务（不经过页面），用于断言写操作真的落库了。"""
    from spdapp.models import task_repo

    def _query(filters=None, sort="created_at", order="desc", limit=None):
        with app.app_context():
            rows = task_repo.list_tasks(filters or {}, sort, order, limit=limit)
            return [dict(r) for r in rows]
    return _query
