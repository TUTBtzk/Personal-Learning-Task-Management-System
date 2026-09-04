# -*- coding: utf-8 -*-
"""用户数据访问层（单用户，仅用于登录与首页信息条）。"""
from ..db import get_db


def get_by_username(username):
    return get_db().execute(
        "SELECT id, username, password_hash, display_name, student_id "
        "FROM users WHERE username = ?",
        ((username or "").strip(),),
    ).fetchone()


def get_by_id(user_id):
    return get_db().execute(
        "SELECT id, username, password_hash, display_name, student_id "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def update_password(user_id, password_hash):
    db = get_db()
    cur = db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
    )
    db.commit()
    return cur.rowcount
