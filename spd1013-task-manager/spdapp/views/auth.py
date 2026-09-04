# -*- coding: utf-8 -*-
"""登录与退出。"""
from flask import (Blueprint, flash, redirect, render_template, request, session,
                   url_for)

from ..services import auth_service

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid"):
        return redirect(url_for("dashboard.index"))

    error = None
    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        user = auth_service.verify(username, request.form.get("password"))
        if user is None:
            # 不区分「用户不存在」和「密码错误」，避免暴露账号是否存在
            error = "账号或密码不正确"
        else:
            auth_service.login(user)
            flash(f"欢迎回来，{user['display_name']}", "success")
            target = request.args.get("next") or request.form.get("next") or ""
            # 只允许跳回站内地址，防止被构造成跳转到外部站点
            if target.startswith("/") and not target.startswith("//"):
                return redirect(target)
            return redirect(url_for("dashboard.index"))

    return render_template("login.html", error=error, username=username)


@bp.route("/logout", methods=["POST"])
def logout():
    auth_service.logout()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))
