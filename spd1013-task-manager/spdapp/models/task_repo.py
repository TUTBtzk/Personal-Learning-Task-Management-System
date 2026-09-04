# -*- coding: utf-8 -*-
"""任务数据访问层（DAO）。

全项目只有 models/ 下的模块直接写 SQL；所有用户输入都以 ? 占位符传参，
不做字符串拼接，从根上避免 SQL 注入。
"""
from ..db import get_db

# 列表、日历、导出共用同一份字段定义。这里用 LEFT JOIN 而不是 INNER JOIN，
# 未分类任务（course_id 为 NULL）也必须能被查出来。
_SELECT = """
SELECT t.id, t.title, t.course_id, t.due_date, t.priority, t.status, t.note,
       t.created_at, t.updated_at, t.completed_at,
       c.name AS course_name, c.color AS course_color
FROM tasks t
LEFT JOIN courses c ON c.id = t.course_id
"""

# SQL 的 ORDER BY 不支持 ? 占位符，只能字符串拼接，
# 所以排序字段必须走白名单，杜绝 URL 参数直接进 SQL。
ALLOWED_SORT = {
    "due_date": "t.due_date",
    "priority": "t.priority",
    "created_at": "t.created_at",
    "title": "t.title",
    "status": "t.status",
}
SORT_LABELS = {
    "due_date": "截止日期",
    "priority": "优先级",
    "created_at": "创建时间",
    "title": "任务名称",
    "status": "完成状态",
}
DEFAULT_SORT = "due_date"
DEFAULT_ORDER = "asc"


def build_where(filters):
    """把筛选条件翻译成 WHERE 子句与参数列表，多个条件之间是 AND 关系。"""
    clauses, params = [], []

    keyword = (filters.get("q") or "").strip()
    if keyword:
        clauses.append("(t.title LIKE ? OR t.note LIKE ?)")
        like = f"%{keyword}%"
        params += [like, like]
    course_id = filters.get("course_id")
    if course_id == "none":                     # 「未分类」是一个有效筛选值
        clauses.append("t.course_id IS NULL")
    elif course_id not in (None, ""):
        clauses.append("t.course_id = ?")
        params.append(int(course_id))

    if filters.get("status") not in (None, ""):
        clauses.append("t.status = ?")
        params.append(int(filters["status"]))

    if filters.get("priority") not in (None, ""):
        clauses.append("t.priority = ?")
        params.append(int(filters["priority"]))

    # 截止日期存的是 YYYY-MM-DD 文本，字典序等于时间序，可以直接比较
    if filters.get("due_from"):
        clauses.append("t.due_date >= ?")
        params.append(filters["due_from"])
    if filters.get("due_to"):
        clauses.append("t.due_date <= ?")
        params.append(filters["due_to"])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def build_order(sort, order):
    """生成 ORDER BY 子句；非法字段一律回落到默认排序。"""
    column = ALLOWED_SORT.get(sort or DEFAULT_SORT, ALLOWED_SORT[DEFAULT_SORT])
    direction = "DESC" if str(order).lower() == "desc" else "ASC"
    # 追加次级排序键，保证同值行的顺序稳定，翻页时不会出现重复或漏项
    return f" ORDER BY {column} {direction}, t.priority ASC, t.id DESC"


def list_tasks(filters=None, sort=None, order=None, limit=None, offset=0):
    """按筛选条件 + 排序取任务列表，limit 为 None 时取全部（导出用）。"""
    where, params = build_where(filters or {})
    sql = _SELECT + where + build_order(sort, order)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [int(limit), int(offset)]
    return get_db().execute(sql, params).fetchall()


def count_tasks(filters=None):
    """同一套筛选条件下的命中总数，供分页与「已筛选 N 条」显示。"""
    where, params = build_where(filters or {})
    return get_db().execute(
        "SELECT COUNT(*) AS n FROM tasks t" + where, params
    ).fetchone()["n"]


def get_task(task_id):
    return get_db().execute(_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()


def create_task(data):
    """新增任务，返回新记录的 id。"""
    db = get_db()
    cur = db.execute(
        "INSERT INTO tasks (title, course_id, due_date, priority, status, note, "
        "created_at, updated_at, completed_at) VALUES "
        "(?, ?, ?, ?, ?, ?, datetime('now','localtime'), "
        "datetime('now','localtime'), ?)",
        (
            data["title"],
            data.get("course_id"),
            data["due_date"],
            data["priority"],
            data.get("status", 0),
            data.get("note", ""),
            data.get("completed_at"),
        ),
    )
    db.commit()
    return cur.lastrowid

def update_task(task_id, data):
    """修改任务，返回受影响行数（0 表示 id 不存在）。"""
    db = get_db()
    cur = db.execute(
        "UPDATE tasks SET title = ?, course_id = ?, due_date = ?, priority = ?, "
        "status = ?, note = ?, completed_at = ?, "
        "updated_at = datetime('now','localtime') WHERE id = ?",
        (
            data["title"],
            data.get("course_id"),
            data["due_date"],
            data["priority"],
            data.get("status", 0),
            data.get("note", ""),
            data.get("completed_at"),
            task_id,
        ),
    )
    db.commit()
    return cur.rowcount


def delete_task(task_id):
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return cur.rowcount


def set_status(task_id, status):
    """标记完成 / 取消完成。完成时写入 completed_at（趋势图数据源），取消时清空。"""
    db = get_db()
    if int(status) == 1:
        sql = ("UPDATE tasks SET status = 1, "
               "completed_at = datetime('now','localtime'), "
               "updated_at = datetime('now','localtime') WHERE id = ?")
    else:
        sql = ("UPDATE tasks SET status = 0, completed_at = NULL, "
               "updated_at = datetime('now','localtime') WHERE id = ?")
    cur = db.execute(sql, (task_id,))
    db.commit()
    return cur.rowcount


def tasks_between(start, end):
    """取某日期区间内的全部任务，供日历视图按天分组铺格子。"""
    return get_db().execute(
        _SELECT + " WHERE t.due_date BETWEEN ? AND ? "
        "ORDER BY t.status ASC, t.priority ASC, t.id ASC",
        (start, end),
    ).fetchall()


def upcoming_tasks(limit=8):
    """首页「近期待办」：未完成任务按截止日期升序，逾期的自然排在最前。"""
    return get_db().execute(
        _SELECT + " WHERE t.status = 0 ORDER BY t.due_date ASC, t.priority ASC "
        "LIMIT ?",
        (limit,),
    ).fetchall()
