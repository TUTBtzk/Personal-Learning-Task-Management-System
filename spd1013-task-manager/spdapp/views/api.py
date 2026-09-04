# -*- coding: utf-8 -*-
"""REST API（扩展功能）。

鉴权说明：写操作只认请求头 X-API-KEY，读操作额外允许已登录的浏览器会话
（页面上的图表就是这样取数据的）。这不是生产级方案——key 明文写在配置里、
不会过期、没有速率限制，仅用于本机演示与接口验证。
"""
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from ..models import course_repo, task_repo
from ..services import classifier, stats_service, task_service

bp = Blueprint("api", __name__, url_prefix="/api")


def ok(data=None, msg="ok"):
    return jsonify(code=0, msg=msg, data=data)


def fail(msg, code=400):
    return jsonify(code=code, msg=msg, data=None), code


def require_api_key(view):
    """写操作：只接受请求头里的 key，浏览器无法跨站伪造自定义请求头。"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-KEY") != current_app.config["API_KEY"]:
            return fail("缺少或错误的 X-API-KEY 请求头", 401)
        return view(*args, **kwargs)
    return wrapper


def require_key_or_session(view):
    """读操作：已登录的页面可直接调用，外部调用需带 key。"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("uid"):
            return view(*args, **kwargs)
        key = request.headers.get("X-API-KEY") or request.args.get("api_key")
        if key != current_app.config["API_KEY"]:
            return fail("需要登录或提供 X-API-KEY", 401)
        return view(*args, **kwargs)
    return wrapper


def task_to_dict(row):
    state = task_service.derive_state(row)
    return {
        "id": row["id"],
        "title": row["title"],
        "course_id": row["course_id"],
        "course": row["course_name"] or "未分类",
        "due_date": row["due_date"],
        "days_left": task_service.days_left(row),
        "priority": row["priority"],
        "priority_label": task_service.PRIORITY_LABELS[row["priority"]],
        "status": row["status"],
        "status_label": task_service.STATUS_LABELS[row["status"]],
        "state": state,
        "state_label": task_service.STATE_BADGES[state][0],
        "note": row["note"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


@bp.get("/tasks")
@require_key_or_session
def list_tasks():
    """筛选、排序参数与页面完全一致，两边共用同一套数据层代码。"""
    filters = task_service.parse_filters(request.args)
    sort = request.args.get("sort") or task_repo.DEFAULT_SORT
    order = request.args.get("order") or task_repo.DEFAULT_ORDER
    limit = request.args.get("limit", type=int)
    rows = task_repo.list_tasks(filters, sort, order, limit=limit)
    return ok({
        "total": task_repo.count_tasks(filters),
        "count": len(rows),
        "items": [task_to_dict(r) for r in rows],
    })


@bp.get("/tasks/<int:task_id>")
@require_key_or_session
def get_task(task_id):
    row = task_repo.get_task(task_id)
    if row is None:
        return fail("任务不存在", 404)
    return ok(task_to_dict(row))


@bp.post("/tasks")
@require_api_key
def create_task():
    payload = request.get_json(silent=True) or request.form
    data, errors = task_service.validate(payload)
    if errors:
        return fail("；".join(errors.values()), 422)
    task_id = task_service.create(data)
    return ok(task_to_dict(task_repo.get_task(task_id)), "已创建"), 201


@bp.put("/tasks/<int:task_id>")
@require_api_key
def update_task(task_id):
    payload = request.get_json(silent=True) or request.form
    data, errors = task_service.validate(payload)
    if errors:
        return fail("；".join(errors.values()), 422)
    rows, detail = task_service.update(task_id, data)
    if not rows:
        return fail("任务不存在", 404)
    return ok(task_to_dict(task_repo.get_task(task_id)), detail or "已更新")


@bp.delete("/tasks/<int:task_id>")
@require_api_key
def delete_task(task_id):
    rows, task = task_service.delete(task_id)
    if not rows:
        return fail("任务不存在", 404)
    return ok({"id": task_id, "title": task["title"]}, "已删除")


@bp.post("/tasks/<int:task_id>/toggle")
@require_api_key
def toggle_task(task_id):
    new_status = task_service.toggle(task_id)
    if new_status is None:
        return fail("任务不存在", 404)
    return ok(task_to_dict(task_repo.get_task(task_id)),
              f"已标记为{task_service.STATUS_LABELS[new_status]}")


@bp.get("/courses")
@require_key_or_session
def list_courses():
    rows = course_repo.list_courses()
    return ok([{"id": r["id"], "name": r["name"], "teacher": r["teacher"],
                "color": r["color"]} for r in rows])


@bp.get("/stats")
@require_key_or_session
def get_stats():
    """仪表盘四张图表的数据源，与页面上的统计卡片同源。"""
    return ok(stats_service.get_dashboard_stats())


@bp.get("/classify")
@require_key_or_session
def classify():
    """智能分类建议：新增任务时输入标题失焦即调用。"""
    return ok(classifier.suggest(request.args.get("title")))


@bp.get("/meta")
@require_key_or_session
def meta():
    """项目信息，便于接口截图里也能看到姓名 / 学号 / 项目标识。"""
    cfg = current_app.config
    return ok({
        "app": cfg["APP_NAME"],
        "student_name": cfg["STUDENT_NAME"],
        "student_id": cfg["STUDENT_ID"],
        "project_code": cfg["PROJECT_CODE"],
        "remind_days": cfg["REMIND_DAYS"],
    })
