# -*- coding: utf-8 -*-
"""任务的增删改查、关键词搜索、多条件筛选与排序。"""
from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from ..models import course_repo, task_repo
from ..services import stats_service, task_service

bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _form_data(form):
    """把提交上来的表单整理成模板可直接回填的字典（校验失败时不丢用户输入）。"""
    return {
        "title": (form.get("title") or "").strip(),
        "course_id": (form.get("course_id") or "").strip(),
        "due_date": (form.get("due_date") or "").strip(),
        "priority": (form.get("priority") or "2").strip(),
        "status": 1 if str(form.get("status")) in ("1", "on", "true") else 0,
        "note": (form.get("note") or "").strip(),
    }


def _row_to_form(row):
    return {
        "title": row["title"],
        "course_id": row["course_id"] or "",
        "due_date": row["due_date"],
        "priority": row["priority"],
        "status": row["status"],
        "note": row["note"] or "",
    }


def _safe_back(value, default_endpoint="tasks.index"):
    """只接受站内相对地址，避免被构造成跳转到外部网站。"""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return url_for(default_endpoint)


@bp.route("/")
def index():
    """任务列表：关键词 + 课程 + 状态 + 优先级 + 日期区间可同时生效，并支持排序分页。"""
    filters = task_service.parse_filters(request.args)

    sort = request.args.get("sort") or task_repo.DEFAULT_SORT
    if sort not in task_repo.ALLOWED_SORT:          # 非法排序字段回落默认值
        sort = task_repo.DEFAULT_SORT
    order = "desc" if (request.args.get("order") or "").lower() == "desc" else "asc"

    page_size = current_app.config["PAGE_SIZE"]
    total = task_repo.count_tasks(filters)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, request.args.get("page", type=int) or 1), pages)

    rows = task_repo.list_tasks(filters, sort, order,
                               limit=page_size, offset=(page - 1) * page_size)

    return render_template(
        "tasks/list.html",
        tasks=rows,
        filters=filters,
        sort=sort,
        order=order,
        page=page,
        pages=pages,
        total=total,
        courses=course_repo.list_courses(),
        active_filters=task_service.active_filter_count(filters),
        summary=stats_service.get_summary(),
        highlight=request.args.get("highlight", type=int),
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    courses = course_repo.list_courses()
    if request.method == "POST":
        data, errors = task_service.validate(request.form)
        if errors:
            # 校验失败：原表单回显 + 字段级错误提示，已填内容不丢
            return render_template("tasks/form.html", mode="create",
                                   task=_form_data(request.form), errors=errors,
                                   courses=courses), 400
        task_id = task_service.create(data)
        flash(f"任务已创建：{data['title']}", "success")
        # POST-Redirect-GET：刷新页面不会重复提交
        return redirect(url_for("tasks.index", highlight=task_id))

    # 日历视图点某天的「+」会带上 ?due=YYYY-MM-DD，默认填这一天
    preset_due = (request.args.get("due") or "").strip()
    if not task_service.is_date(preset_due):
        preset_due = task_service.today_str()
    blank = {"title": "", "course_id": "", "due_date": preset_due,
             "priority": "2", "status": 0, "note": ""}
    return render_template("tasks/form.html", mode="create", task=blank,
                           errors={}, courses=courses)


@bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
def edit(task_id):
    row = task_repo.get_task(task_id)
    if row is None:
        abort(404)
    courses = course_repo.list_courses()

    if request.method == "POST":
        data, errors = task_service.validate(request.form)
        if errors:
            return render_template("tasks/form.html", mode="edit", task_id=task_id,
                                   task=_form_data(request.form), errors=errors,
                                   courses=courses), 400
        rows, detail = task_service.update(task_id, data)
        if not rows:
            abort(404)
        flash(f"任务已更新：{data['title']}" + (f"（{detail}）" if detail else ""),
              "success")
        return redirect(url_for("tasks.index", highlight=task_id))

    return render_template("tasks/form.html", mode="edit", task_id=task_id,
                           task=_row_to_form(row), errors={}, courses=courses)

@bp.route("/<int:task_id>/delete", methods=["POST"])
def delete(task_id):
    rows, task = task_service.delete(task_id)
    if not rows:
        abort(404)
    flash(f"已删除任务：{task['title']}", "warning")
    return redirect(_safe_back(request.form.get("back")))


@bp.route("/<int:task_id>/toggle", methods=["POST"])
def toggle(task_id):
    """标记完成 / 取消完成。返回 JSON，页面上的统计卡片和图表据此就地刷新。"""
    new_status = task_service.toggle(task_id)
    if new_status is None:
        abort(404)
    row = task_repo.get_task(task_id)
    state = task_service.derive_state(row)
    return jsonify(code=0, msg="ok", data={
        "id": task_id,
        "status": new_status,
        "status_label": task_service.STATUS_LABELS[new_status],
        "state": state,
        "state_label": task_service.STATE_BADGES[state][0],
        "state_color": task_service.STATE_BADGES[state][1],
        "summary": stats_service.get_summary(),
    })
