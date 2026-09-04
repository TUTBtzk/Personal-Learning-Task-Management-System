# -*- coding: utf-8 -*-
"""统计聚合查询。

所有汇总都交给 SQL 的聚合函数完成，不在 Python 里遍历任务列表——
既是正确的做法，也让课程报告里的「数据统计」有实打实的 SQL 可讲。
"""
from ..db import get_db


def _count(where, params=()):
    return get_db().execute(
        f"SELECT COUNT(*) AS n FROM tasks WHERE {where}", params
    ).fetchone()["n"]


def summary():
    """总任务数 / 已完成 / 未完成，一条 SQL 全部拿到。"""
    return get_db().execute(
        """
        SELECT COUNT(*)                                            AS total,
               COALESCE(SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END), 0) AS done,
               COALESCE(SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END), 0) AS undone
        FROM tasks
        """
    ).fetchone()


def by_course():
    """按课程统计任务数与完成数。

    用 LEFT JOIN 而非 INNER JOIN：一门任务数为 0 的课程也要出现在柱状图里，
    否则图表会莫名少一根柱子，和课程列表对不上。
    """
    return get_db().execute(
        """
        SELECT c.id, c.name, c.color,
               COUNT(t.id)                AS total,
               COALESCE(SUM(t.status), 0) AS done
        FROM courses c
        LEFT JOIN tasks t ON t.course_id = c.id
        GROUP BY c.id, c.name, c.color
        ORDER BY total DESC, c.id ASC
        """
    ).fetchall()


def uncategorized():
    """未分类任务（course_id 为 NULL）单独统计，补上 by_course 覆盖不到的部分。"""
    return get_db().execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(status), 0) AS done "
        "FROM tasks WHERE course_id IS NULL"
    ).fetchone()


def by_priority():
    """按优先级分布。优先级存的是 1/2/3，GROUP BY 后顺序天然是 高→中→低。"""
    return get_db().execute(
        "SELECT priority, COUNT(*) AS cnt, "
        "COALESCE(SUM(status), 0) AS done "
        "FROM tasks GROUP BY priority ORDER BY priority"
    ).fetchall()


def completed_per_day(start_date):
    """从 start_date 起每天的完成数。

    注意：GROUP BY 不会为「当天一条都没完成」生成结果行，
    折线图缺点会导致日期错位，补零的活儿交给 stats_service。
    """
    return get_db().execute(
        "SELECT date(completed_at) AS d, COUNT(*) AS cnt FROM tasks "
        "WHERE status = 1 AND completed_at IS NOT NULL "
        "AND date(completed_at) >= ? GROUP BY d ORDER BY d",
        (start_date,),
    ).fetchall()


def overdue_count(today):
    """已逾期：未完成且截止日期早于今天。"""
    return _count("status = 0 AND due_date < ?", (today,))


def due_today_count(today):
    return _count("status = 0 AND due_date = ?", (today,))


def due_soon_count(today, deadline):
    """即将到期：今天之后、deadline 之前（含）到期且未完成。"""
    return _count("status = 0 AND due_date > ? AND due_date <= ?", (today, deadline))
