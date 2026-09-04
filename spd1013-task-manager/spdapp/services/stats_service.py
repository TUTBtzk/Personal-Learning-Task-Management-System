# -*- coding: utf-8 -*-
"""统计业务层：完成率口径、趋势补零、图表数据打包。

页面（仪表盘）与接口（/api/stats）共用本模块的同一份输出，
保证界面上的数字和接口返回值永远一致，报告里交叉截图不会自相矛盾。
"""
from flask import current_app

from ..models import stats_repo
from .task_service import PRIORITY_COLORS, PRIORITY_LABELS, shift, today_str


def completion_rate(done, total):
    """任务完成率（百分比，保留 1 位）。

    total 为 0 时必须短路返回 0：空库第一次访问首页就会走到这里，
    不加这个判断直接就是 ZeroDivisionError → 500 白屏。
    """
    if not total:
        return 0.0
    return round(done / total * 100, 1)


def get_summary(today=None):
    """四项必需统计 + 三项提醒计数。"""
    today = today or today_str()
    row = stats_repo.summary()
    total, done, undone = row["total"], row["done"], row["undone"]
    remind_days = current_app.config["REMIND_DAYS"]
    return {
        "total": total,
        "done": done,
        "undone": undone,
        "completion_rate": completion_rate(done, total),
        "overdue": stats_repo.overdue_count(today),
        "due_today": stats_repo.due_today_count(today),
        "due_soon": stats_repo.due_soon_count(today, shift(today, remind_days)),
        "remind_days": remind_days,
    }


def reminder_count(today=None):
    """导航栏铃铛角标：已逾期 + 今天到期 + 即将到期。"""
    today = today or today_str()
    remind_days = current_app.config["REMIND_DAYS"]
    return (stats_repo.overdue_count(today)
            + stats_repo.due_today_count(today)
            + stats_repo.due_soon_count(today, shift(today, remind_days)))


def get_by_course():
    """课程维度统计，末尾追加「未分类」一组（有任务时才加）。"""
    rows = []
    for r in stats_repo.by_course():
        rows.append({
            "name": r["name"], "color": r["color"], "total": r["total"],
            "done": r["done"], "undone": r["total"] - r["done"],
            "rate": completion_rate(r["done"], r["total"]),
        })
    extra = stats_repo.uncategorized()
    if extra["total"]:
        rows.append({
            "name": "未分类", "color": "#adb5bd", "total": extra["total"],
            "done": extra["done"], "undone": extra["total"] - extra["done"],
            "rate": completion_rate(extra["done"], extra["total"]),
        })
    return rows


def get_by_priority():
    """优先级分布。库里没有某一级时补 0，柱状图始终是「高中低」三根柱子。"""
    counts = {r["priority"]: r["cnt"] for r in stats_repo.by_priority()}
    return [
        {"priority": p, "label": PRIORITY_LABELS[p],
         "color": PRIORITY_COLORS[p], "count": counts.get(p, 0)}
        for p in (1, 2, 3)
    ]


def get_trend(days=None, today=None):
    """近 N 天完成趋势。

    SQL 的 GROUP BY 不会为「当天零完成」生成结果行，直接拿去画折线会缺点、
    日期还会错位，所以这里按完整日期序列补零。
    """
    days = days or current_app.config["TREND_DAYS"]
    today = today or today_str()
    start = shift(today, -(days - 1))
    hit = {r["d"]: r["cnt"] for r in stats_repo.completed_per_day(start)}
    return [
        {"date": shift(start, i), "label": shift(start, i)[5:],
         "count": hit.get(shift(start, i), 0)}
        for i in range(days)
    ]


def get_dashboard_stats(today=None):
    """仪表盘 / REST 接口共用的完整统计数据包。"""
    today = today or today_str()
    return {
        "summary": get_summary(today),
        "by_course": get_by_course(),
        "by_priority": get_by_priority(),
        "trend": get_trend(today=today),
        "today": today,
    }
