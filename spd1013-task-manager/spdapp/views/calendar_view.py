# -*- coding: utf-8 -*-
"""日历视图：把任务按截止日期铺进月历格子。"""
import calendar
from datetime import date

from flask import Blueprint, render_template, request

from ..models import task_repo

bp = Blueprint("calendar_view", __name__)


@bp.route("/calendar")
def month_view():
    today = date.today()
    year = request.args.get("y", type=int) or today.year
    month = request.args.get("m", type=int) or today.month
    if not 1 <= month <= 12:
        month = today.month
    year = min(max(year, 1970), 2999)

    # 用标准库生成 6×7 的日期网格（每行是一周，含上下月补齐的日期）
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    start, end = weeks[0][0].isoformat(), weeks[-1][-1].isoformat()

    # 整个网格范围内的任务一次查完，再按日期分组塞格子，避免 42 次查询
    grouped = {}
    for row in task_repo.tasks_between(start, end):
        grouped.setdefault(row["due_date"], []).append(row)

    prefix = f"{year:04d}-{month:02d}"
    prev_ym = (year - 1, 12) if month == 1 else (year, month - 1)
    next_ym = (year + 1, 1) if month == 12 else (year, month + 1)

    return render_template(
        "calendar.html",
        year=year, month=month, weeks=weeks, grouped=grouped,
        prev_ym=prev_ym, next_ym=next_ym,
        month_total=sum(len(v) for k, v in grouped.items() if k.startswith(prefix)),
        month_done=sum(1 for k, v in grouped.items() if k.startswith(prefix)
                       for t in v if t["status"] == 1),
    )
