# -*- coding: utf-8 -*-
"""课程数据访问层。"""
from ..db import get_db

# 新建课程时按顺序取色，保证图表与日历里各门课颜色不撞
PALETTE = [
    "#0d6efd", "#6f42c1", "#198754", "#fd7e14", "#d63384",
    "#0dcaf0", "#20c997", "#dc3545", "#6610f2", "#ffc107",
]


def list_courses():
    return get_db().execute(
        "SELECT id, name, teacher, color FROM courses ORDER BY id"
    ).fetchall()


def get_course(course_id):
    return get_db().execute(
        "SELECT id, name, teacher, color FROM courses WHERE id = ?", (course_id,)
    ).fetchone()


def get_by_name(name):
    return get_db().execute(
        "SELECT id, name, teacher, color FROM courses WHERE name = ?",
        ((name or "").strip(),),
    ).fetchone()


def create_course(name, teacher="", color=None):
    db = get_db()
    if color is None:
        n = db.execute("SELECT COUNT(*) AS n FROM courses").fetchone()["n"]
        color = PALETTE[n % len(PALETTE)]
    cur = db.execute(
        "INSERT INTO courses (name, teacher, color) VALUES (?, ?, ?)",
        ((name or "").strip(), teacher or "", color),
    )
    db.commit()
    return cur.lastrowid


def get_or_create(name):
    """导入 CSV/Excel 时使用：课程不存在就自动建一门，不让整行导入失败。"""
    name = (name or "").strip()
    if not name:
        return None
    row = get_by_name(name)
    return row["id"] if row else create_course(name)


def delete_course(course_id):
    """删除课程。外键 ON DELETE SET NULL 会把它下面的任务转为「未分类」而不是一起删掉。"""
    db = get_db()
    cur = db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    db.commit()
    return cur.rowcount
