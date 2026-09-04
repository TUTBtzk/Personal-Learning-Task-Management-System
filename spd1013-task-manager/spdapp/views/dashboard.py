# -*- coding: utf-8 -*-
"""首页仪表盘：统计卡片 + 四张图表 + 近期待办 + 最近操作记录。"""
from flask import Blueprint, render_template

from ..models import log_repo, task_repo
from ..services import stats_service

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    # 页面上的数字和 /api/stats 返回的是同一份数据，保证两处永远一致
    stats = stats_service.get_dashboard_stats()
    return render_template(
        "dashboard.html",
        stats=stats,
        summary=stats["summary"],
        by_course=stats["by_course"],
        upcoming=task_repo.upcoming_tasks(limit=8),
        logs=log_repo.recent_logs(limit=8),
    )
