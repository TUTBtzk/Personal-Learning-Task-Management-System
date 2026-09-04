# -*- coding: utf-8 -*-
"""任务业务层：字段校验、状态流转、筛选条件规整、到期状态派生、操作日志。"""
from datetime import date, datetime, timedelta

from flask import current_app

from ..models import course_repo, log_repo, task_repo

# 优先级在库里存 1/2/3，中文标签只在显示层出现：
# 这样 ORDER BY priority 就是「高→中→低」，不会被中文字符编码顺序打乱
PRIORITY_LABELS = {1: "高", 2: "中", 3: "低"}
STATUS_LABELS = {0: "未完成", 1: "已完成"}
PRIORITY_BY_LABEL = {"高": 1, "中": 2, "低": 3}
STATUS_BY_LABEL = {"未完成": 0, "已完成": 1}

PRIORITY_COLORS = {1: "#dc3545", 2: "#fd7e14", 3: "#20c997"}

TITLE_MAX = 50
NOTE_MAX = 200
PRESETS = ("overdue", "today", "due_soon", "undone")

# 派生状态 → (中文标签, Bootstrap 配色)
STATE_BADGES = {
    "done": ("已完成", "secondary"),
    "overdue": ("已逾期", "danger"),
    "today": ("今天到期", "warning"),
    "soon": ("即将到期", "info"),
    "normal": ("进行中", "primary"),
}


def today_str():
    return date.today().isoformat()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def shift(day, days):
    """日期偏移，返回 YYYY-MM-DD 文本。"""
    base = datetime.strptime(day, "%Y-%m-%d").date()
    return (base + timedelta(days=days)).isoformat()


def parse_filters(args):
    """把 URL 查询参数规整成筛选条件字典。

    非法参数一律丢弃而不是抛异常——用户手改 URL 不应该看到 500。
    """
    f = {
        "q": (args.get("q") or "").strip(),
        "course_id": (args.get("course_id") or "").strip(),
        "status": (args.get("status") or "").strip(),
        "priority": (args.get("priority") or "").strip(),
        "due_from": (args.get("due_from") or "").strip(),
        "due_to": (args.get("due_to") or "").strip(),
    }
    if f["course_id"] != "none" and not f["course_id"].isdigit():
        f["course_id"] = ""
    if f["status"] not in ("0", "1"):
        f["status"] = ""
    if f["priority"] not in ("1", "2", "3"):
        f["priority"] = ""
    for key in ("due_from", "due_to"):
        if f[key] and not is_date(f[key]):
            f[key] = ""

    # 快捷提醒视图：把 preset 翻译成具体的状态 + 日期区间
    preset = (args.get("preset") or "").strip()
    today = today_str()
    if preset == "overdue":
        f.update(status="0", due_from="", due_to=shift(today, -1))
    elif preset == "today":
        f.update(status="0", due_from=today, due_to=today)
    elif preset == "due_soon":
        f.update(status="0", due_from=today,
                 due_to=shift(today, current_app.config["REMIND_DAYS"]))
    elif preset == "undone":
        f.update(status="0")
    f["preset"] = preset if preset in PRESETS else ""
    return f


def active_filter_count(filters):
    """生效的筛选条件个数，用于列表页显示「已筛选 N 个条件」。"""
    keys = ("q", "course_id", "status", "priority", "due_from", "due_to")
    return sum(1 for k in keys if filters.get(k))


def _text(form, key, default=""):
    """取表单/JSON 字段并统一成去空白的字符串。

    REST 接口收到的是 JSON，priority 很可能是数字 1 而不是字符串 "1"，
    直接 .strip() 会 AttributeError → 接口 500；这里统一 str() 兜底。
    """
    value = form.get(key)
    text = "" if value is None else str(value).strip()
    return text or default


def validate(form):
    """校验新增/修改表单，返回 (整理后的数据, 错误字典)。错误为空即通过。"""
    errors = {}

    title = _text(form, "title")
    if not title:
        errors["title"] = "任务名称不能为空"
    elif len(title) > TITLE_MAX:
        errors["title"] = f"任务名称不能超过 {TITLE_MAX} 个字（当前 {len(title)} 个）"

    due_date = _text(form, "due_date")
    if not due_date:
        errors["due_date"] = "请选择截止日期"
    elif not is_date(due_date):
        errors["due_date"] = "截止日期格式应为 YYYY-MM-DD"

    priority = _text(form, "priority", "2")
    if priority not in ("1", "2", "3"):
        errors["priority"] = "优先级只能是 高 / 中 / 低"

    course_id = _text(form, "course_id")
    if course_id:
        if not course_id.isdigit():
            errors["course_id"] = "所属课程无效"
        elif course_repo.get_course(int(course_id)) is None:
            errors["course_id"] = "所属课程不存在，请重新选择"

    note = _text(form, "note")
    if len(note) > NOTE_MAX:
        errors["note"] = f"备注不能超过 {NOTE_MAX} 个字（当前 {len(note)} 个）"

    data = {
        "title": title,
        "course_id": int(course_id) if course_id.isdigit() else None,
        "due_date": due_date,
        "priority": int(priority) if priority in ("1", "2", "3") else 2,
        # 复选框传 "on"、JSON 传 true、导入传 "1"，统一成 0/1
        "status": 1 if _text(form, "status").lower() in ("1", "on", "true", "yes") else 0,
        "note": note,
    }
    return data, errors


def course_name(course_id):
    if not course_id:
        return "未分类"
    row = course_repo.get_course(course_id)
    return row["name"] if row else "未分类"


def create(data):
    """新增任务：创建时就勾了「已完成」的，补上 completed_at。"""
    if data.get("status") == 1:
        data["completed_at"] = _now()
    task_id = task_repo.create_task(data)
    log_repo.add_log(
        "create", data["title"],
        f"课程 {course_name(data['course_id'])}，截止 {data['due_date']}，"
        f"优先级 {PRIORITY_LABELS[data['priority']]}",
    )
    return task_id


def diff_detail(old, new):
    """对比修改前后，生成「优先级 中→高」这样的变更摘要写进操作日志。"""
    parts = []
    if old["title"] != new["title"]:
        parts.append(f"名称「{old['title']}」→「{new['title']}」")
    if (old["course_id"] or None) != new["course_id"]:
        parts.append(f"课程 {course_name(old['course_id'])}→{course_name(new['course_id'])}")
    if old["due_date"] != new["due_date"]:
        parts.append(f"截止 {old['due_date']}→{new['due_date']}")
    if old["priority"] != new["priority"]:
        parts.append(f"优先级 {PRIORITY_LABELS[old['priority']]}→"
                     f"{PRIORITY_LABELS[new['priority']]}")
    if old["status"] != new["status"]:
        parts.append(f"状态 {STATUS_LABELS[old['status']]}→{STATUS_LABELS[new['status']]}")
    if (old["note"] or "") != new["note"]:
        parts.append("备注已更新")
    return "；".join(parts)


def update(task_id, data):
    """修改任务，返回 (受影响行数, 变更摘要)。id 不存在时返回 (0, None)。"""
    old = task_repo.get_task(task_id)
    if old is None:
        return 0, None
    # 状态改为已完成时补完成时刻（已有则保留），改回未完成时清空
    data["completed_at"] = (old["completed_at"] or _now()) if data["status"] == 1 else None
    rows = task_repo.update_task(task_id, data)
    detail = diff_detail(old, data)
    log_repo.add_log("update", data["title"], detail or "提交了修改，但字段无变化")
    return rows, detail

def delete(task_id):
    """删除任务。删除前把标题写进日志，任务没了也能追溯这次操作。"""
    task = task_repo.get_task(task_id)
    if task is None:
        return 0, None
    task_repo.delete_task(task_id)
    log_repo.add_log("delete", task["title"],
                     f"原截止 {task['due_date']}，原状态 {STATUS_LABELS[task['status']]}")
    return 1, task


def toggle(task_id):
    """切换完成状态，返回新状态；id 不存在返回 None。"""
    task = task_repo.get_task(task_id)
    if task is None:
        return None
    new_status = 0 if task["status"] == 1 else 1
    task_repo.set_status(task_id, new_status)
    log_repo.add_log("toggle", task["title"],
                     f"{STATUS_LABELS[task['status']]}→{STATUS_LABELS[new_status]}")
    return new_status


def derive_state(task, today=None, remind_days=None):
    """派生到期状态。

    刻意不入库：存进数据库就需要定时任务刷新，且一定会和真实日期不一致；
    改为查询时按「今天」现算，永远准确。
    """
    if task["status"] == 1:
        return "done"
    today = today or today_str()
    if remind_days is None:
        remind_days = current_app.config["REMIND_DAYS"]
    due = task["due_date"]
    if due < today:
        return "overdue"
    if due == today:
        return "today"
    if due <= shift(today, remind_days):
        return "soon"
    return "normal"


def days_left(task, today=None):
    """距截止还有几天：负数表示已逾期，0 表示今天。"""
    today = today or today_str()
    due = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
    return (due - datetime.strptime(today, "%Y-%m-%d").date()).days
