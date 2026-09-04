# -*- coding: utf-8 -*-
"""应用工厂。

个人学习任务管理与数据分析系统
姓名：佟政慷    学号：239001013    项目标识：SPD-1013
"""
import secrets
from datetime import datetime

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)

from config import Config

from . import db
from .services import stats_service, task_service

# 不需要登录即可访问的端点
LOGIN_EXEMPT = {"auth.login", "static"}
WEEKDAY_CN = "一二三四五六日"


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    _register_blueprints(app)
    _register_hooks(app)
    _register_template_helpers(app)
    _register_error_handlers(app)

    # 空库则建表并写入初始数据；已有数据库直接沿用（重启后数据保留）
    db.ensure_database(app)
    return app


def _register_blueprints(app):
    from .views import api, auth, calendar_view, dashboard, data_io, tasks

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(calendar_view.bp)
    app.register_blueprint(data_io.bp)
    app.register_blueprint(api.bp)


def _register_hooks(app):
    """全局钩子：登录拦截与 CSRF 校验都集中在这里，不靠每个视图各写一遍装饰器。"""

    @app.before_request
    def ensure_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)

    @app.before_request
    def require_login():
        # REST 接口用请求头 X-API-KEY 自行校验；登录页与静态资源放行
        if request.blueprint == "api" or request.endpoint in LOGIN_EXEMPT:
            return None
        if request.endpoint is None:          # 404 交给错误处理器
            return None
        if not session.get("uid"):
            return redirect(url_for("auth.login", next=request.full_path))
        return None

    @app.before_request
    def check_csrf():
        """所有写操作都要带 session 绑定的令牌：表单放隐藏域，AJAX 放请求头。"""
        if not app.config.get("CSRF_ENABLED", True):
            return None
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        if request.blueprint == "api":
            return None
        expected = session.get("csrf_token")
        received = (request.form.get("csrf_token")
                    or request.headers.get("X-CSRF-Token"))
        if not expected or received != expected:
            abort(400, description="页面令牌已失效，请刷新页面后重试")
        return None


def _register_template_helpers(app):
    """注入全局变量与模板过滤器。

    姓名 / 学号 / 项目标识放在这里，base.html 一处渲染，
    于是每个页面的截图都自带个性化信息，不必事后补拍。
    """
    from .models import log_repo, task_repo
    from .services import auth_service

    @app.context_processor
    def inject_globals():
        cfg = app.config
        ctx = {
            "APP_NAME": cfg["APP_NAME"],
            "STUDENT_NAME": cfg["STUDENT_NAME"],
            "STUDENT_ID": cfg["STUDENT_ID"],
            "PROJECT_CODE": cfg["PROJECT_CODE"],
            "REMIND_DAYS": cfg["REMIND_DAYS"],
            "today": task_service.today_str(),
            "csrf_token": session.get("csrf_token", ""),
            "current_user": None,
            "reminder_count": 0,
        }
        if session.get("uid"):
            ctx["current_user"] = auth_service.current_user()
            ctx["reminder_count"] = stats_service.reminder_count()
        return ctx

    @app.template_filter("priority_label")
    def priority_label(value):
        return task_service.PRIORITY_LABELS.get(int(value), "中")

    @app.template_filter("status_label")
    def status_label(value):
        return task_service.STATUS_LABELS.get(int(value), "未完成")

    @app.template_filter("action_label")
    def action_label(value):
        return log_repo.ACTION_LABELS.get(value, value)

    @app.template_filter("date_cn")
    def date_cn(value):
        """2026-09-09 → 09-09 周三"""
        try:
            day = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return value
        return f"{day.month:02d}-{day.day:02d} 周{WEEKDAY_CN[day.weekday()]}"

    app.jinja_env.globals["task_state"] = task_service.derive_state
    app.jinja_env.globals["STATE_BADGES"] = task_service.STATE_BADGES
    app.jinja_env.globals["days_left"] = task_service.days_left
    app.jinja_env.globals["SORT_LABELS"] = task_repo.SORT_LABELS

def _register_error_handlers(app):
    """自定义错误页：接口返回 JSON，页面返回友好提示，不给用户看 traceback。"""

    def _wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(400)
    def bad_request(err):
        message = getattr(err, "description", "请求参数有误")
        if _wants_json():
            return jsonify(code=400, msg=message, data=None), 400
        return render_template("error.html", code=400, message=message), 400

    @app.errorhandler(404)
    def not_found(err):
        message = "页面或任务不存在，可能已被删除"
        if _wants_json():
            return jsonify(code=404, msg=message, data=None), 404
        return render_template("error.html", code=404, message=message), 404

    @app.errorhandler(413)
    def too_large(err):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        message = f"上传文件超过 {limit_mb} MB，请拆分后再导入"
        if _wants_json():
            return jsonify(code=413, msg=message, data=None), 413
        return render_template("error.html", code=413, message=message), 413

    @app.errorhandler(500)
    def server_error(err):
        message = "服务器内部错误，请查看控制台日志"
        if _wants_json():
            return jsonify(code=500, msg=message, data=None), 500
        return render_template("error.html", code=500, message=message), 500
