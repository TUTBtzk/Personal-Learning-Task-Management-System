# -*- coding: utf-8 -*-
"""操作日志数据访问层。

每一次增 / 删 / 改 / 导入 / 导出都留一行记录，页面上可直接截图，
作为课程报告里「完整操作过程」的证据。
"""
from ..db import get_db

ACTION_LABELS = {
    "create": "新增任务",
    "update": "修改任务",
    "delete": "删除任务",
    "toggle": "切换完成状态",
    "import": "导入数据",
    "export": "导出数据",
    "backup": "备份数据库",
    "login": "登录系统",
    "seed": "初始化数据",
}


def add_log(action, target="", detail=""):
    db = get_db()
    db.execute(
        "INSERT INTO operation_logs (action, target, detail) VALUES (?, ?, ?)",
        (action, target or "", detail or ""),
    )
    db.commit()


def recent_logs(limit=10):
    return get_db().execute(
        "SELECT id, action, target, detail, created_at FROM operation_logs "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def count_logs():
    return get_db().execute(
        "SELECT COUNT(*) AS n FROM operation_logs"
    ).fetchone()["n"]
