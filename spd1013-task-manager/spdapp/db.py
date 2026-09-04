# -*- coding: utf-8 -*-
"""数据层基础设施：SQLite 连接管理与建库。

约定：全项目只有 models/ 下的模块写 SQL，它们统一通过这里的 get_db() 拿连接。
"""
import os
import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """取当前请求上下文内的数据库连接（同一请求复用同一连接）。"""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        # 让查询结果支持 row["title"] 这样的按列名取值，模板里更好写
        g.db.row_factory = sqlite3.Row
        # SQLite 每个连接默认「关闭」外键约束，必须显式打开，
        # 否则 tasks.course_id 上的 ON DELETE SET NULL 根本不会生效。
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    """请求结束时归还连接，避免连接泄漏与文件锁。"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """执行 schema.sql 重建表结构。"""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


def db_is_empty():
    """数据库文件不存在或没有 tasks 表时视为空库。"""
    path = current_app.config["DATABASE"]
    if path != ":memory:" and not os.path.exists(path):
        return True
    row = get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()
    return row is None


def ensure_database(app):
    """启动时调用：准备目录，空库则建表并写入初始数据。返回是否执行了初始化。"""
    db_dir = os.path.dirname(app.config["DATABASE"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)

    with app.app_context():
        if not db_is_empty():
            return False
        init_db()
        from .seed import seed_all
        seed_all(seed_demo=app.config.get("SEED_ON_INIT", True))
        return True


@click.command("init-db")
@with_appcontext
def init_db_command():
    """命令行重建数据库：flask --app app init-db"""
    init_db()
    from .seed import seed_all
    seed_all(seed_demo=current_app.config.get("SEED_ON_INIT", True))
    click.echo("数据库已重建，初始数据写入完成。")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
