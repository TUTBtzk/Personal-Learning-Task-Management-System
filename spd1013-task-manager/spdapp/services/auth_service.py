# -*- coding: utf-8 -*-
"""登录业务层。

密码只以哈希形式存库（werkzeug 的 pbkdf2 加盐），任何环节都不保存明文。
"""
from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import log_repo, user_repo


def verify(username, password):
    """校验账号密码，成功返回用户行，失败返回 None（不区分「用户不存在」和「密码错」）。"""
    user = user_repo.get_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    return user


def login(user):
    session.clear()
    session["uid"] = user["id"]
    log_repo.add_log("login", user["display_name"],
                     f"学号 {user['student_id']} 登录系统")


def logout():
    session.clear()


def current_user():
    uid = session.get("uid")
    return user_repo.get_by_id(uid) if uid else None


def change_password(user_id, old_password, new_password, confirm_password):
    """修改密码，返回错误信息字符串；返回 None 表示修改成功。"""
    user = user_repo.get_by_id(user_id)
    if user is None:
        return "用户不存在"
    if not check_password_hash(user["password_hash"], old_password or ""):
        return "原密码不正确"
    if len(new_password or "") < 6:
        return "新密码至少 6 位"
    if new_password != confirm_password:
        return "两次输入的新密码不一致"
    user_repo.update_password(user_id, generate_password_hash(new_password))
    return None
