# -*- coding: utf-8 -*-
"""统计口径、完成率零除保护、趋势补零、派生状态。"""
from conftest import day

from spdapp.services import stats_service, task_service


def test_completion_rate_zero_guard():
    """空库时 total=0，不加短路判断这里就是 ZeroDivisionError → 首页 500。"""
    assert stats_service.completion_rate(0, 0) == 0.0
    assert stats_service.completion_rate(1, 3) == 33.3
    assert stats_service.completion_rate(3, 3) == 100.0


def test_dashboard_works_on_empty_database(logged_in):
    """一条任务都没有时，首页也要正常渲染出 0%。"""
    body = logged_in.get("/").get_data(as_text=True)
    assert "0.0" in body
    assert "总任务数" in body


def test_summary_counts(add_task, logged_in):
    add_task(title="统计任务 A", due_date=day(1))
    add_task(title="统计任务 B", due_date=day(2))
    add_task(title="统计任务 C", due_date=day(3), status=True)

    summary = logged_in.get("/api/stats").get_json()["data"]["summary"]
    assert summary["total"] == 3
    assert summary["done"] == 1
    assert summary["undone"] == 2
    assert summary["completion_rate"] == 33.3


def test_reminder_counts(add_task, logged_in):
    add_task(title="逾期任务", due_date=day(-1))
    add_task(title="今天到期", due_date=day(0))
    add_task(title="三天后到期", due_date=day(3))
    add_task(title="很久以后", due_date=day(30))

    summary = logged_in.get("/api/stats").get_json()["data"]["summary"]
    assert summary["overdue"] == 1
    assert summary["due_today"] == 1
    assert summary["due_soon"] == 1          # REMIND_DAYS=3，只算今天之后到 3 天内
    assert summary["remind_days"] == 3


def test_trend_is_zero_filled(app, add_task):
    """SQL 的 GROUP BY 不会为「零完成」的日期产出行，必须补零，否则折线图日期错位。"""
    add_task(title="今天完成的任务", status=True)
    with app.app_context():
        trend = stats_service.get_trend()

    assert len(trend) == app.config["TREND_DAYS"]
    assert [p["date"] for p in trend] == sorted(p["date"] for p in trend)
    assert trend[-1]["date"] == day(0)
    assert trend[-1]["count"] == 1
    assert trend[0]["count"] == 0


def test_by_priority_always_three_bars(app, add_task):
    """库里只有高优先级任务时，中/低也要补 0，柱状图始终三根柱子。"""
    add_task(title="唯一的高优先级任务", priority="1")
    with app.app_context():
        rows = stats_service.get_by_priority()

    assert [r["label"] for r in rows] == ["高", "中", "低"]
    assert [r["count"] for r in rows] == [1, 0, 0]


def test_by_course_keeps_zero_task_courses(app, add_task, courses):
    """LEFT JOIN 保证零任务课程也出现在统计里。"""
    add_task(title="只给第一门课加任务", course_id=courses[0]["id"])
    with app.app_context():
        rows = stats_service.get_by_course()

    assert len(rows) == len(courses)
    hit = next(r for r in rows if r["name"] == courses[0]["name"])
    assert hit["total"] == 1 and hit["rate"] == 0.0


def test_uncategorized_group_only_when_needed(app, add_task):
    with app.app_context():
        assert all(r["name"] != "未分类" for r in stats_service.get_by_course())

    add_task(title="不属于任何课程的任务")
    with app.app_context():
        rows = stats_service.get_by_course()
    assert rows[-1]["name"] == "未分类"
    assert rows[-1]["total"] == 1
def test_derive_state_matrix(app):
    """派生状态不入库，按「今天」现算，所以这里能用相对日期穷举五种取值。"""
    with app.app_context():
        assert task_service.derive_state({"status": 1, "due_date": day(-9)}) == "done"
        assert task_service.derive_state({"status": 0, "due_date": day(-1)}) == "overdue"
        assert task_service.derive_state({"status": 0, "due_date": day(0)}) == "today"
        assert task_service.derive_state({"status": 0, "due_date": day(3)}) == "soon"
        assert task_service.derive_state({"status": 0, "due_date": day(4)}) == "normal"


def test_days_left_sign(app):
    with app.app_context():
        assert task_service.days_left({"due_date": day(-2)}) == -2
        assert task_service.days_left({"due_date": day(0)}) == 0
        assert task_service.days_left({"due_date": day(5)}) == 5


def test_dashboard_numbers_match_api(add_task, logged_in):
    """首页 HTML 与 /api/stats 必须同源，否则截图里的数字和接口对不上。"""
    add_task(title="一致性检查 A", status=True)
    add_task(title="一致性检查 B")

    summary = logged_in.get("/api/stats").get_json()["data"]["summary"]
    body = logged_in.get("/").get_data(as_text=True)

    assert summary["total"] == 2 and summary["done"] == 1
    for key in ("total", "done", "undone", "completion_rate"):
        assert 'data-stat="%s">%s' % (key, summary[key]) in body
