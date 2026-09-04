# -*- coding: utf-8 -*-
"""关键词搜索、多条件组合筛选、排序、分页。"""
import pytest

from conftest import day


@pytest.fixture
def dataset(add_task, courses):
    """7 条覆盖各种状态与日期的样本数据。"""
    add_task(title="高等数学 第5章习题", course_id=courses[0]["id"], due_date=day(-2), priority="2")
    add_task(title="数据库原理 实验四", course_id=courses[1]["id"], due_date=day(0), priority="1")
    add_task(title="软件工程 UML 作业", course_id=courses[2]["id"], due_date=day(2), priority="3")
    add_task(title="计算机网络 抓包实验", course_id=courses[3]["id"], due_date=day(10),
             priority="2", status=True)
    add_task(title="大学英语 单词背诵", course_id=courses[4]["id"], due_date=day(5),
             priority="3", status=True)
    add_task(title="SPD-1013 课程报告", course_id=courses[5]["id"], due_date=day(6),
             priority="1", note="备注里也有关键词：答辩")
    add_task(title="整理笔记", due_date=day(1), priority="2")
    return courses


def api_list(client, **params):
    """读接口允许已登录会话直接调用，用它断言筛选结果最省事。"""
    resp = client.get("/api/tasks", query_string=params)
    assert resp.status_code == 200
    return resp.get_json()["data"]


def test_keyword_matches_title(dataset, logged_in):
    data = api_list(logged_in, q="实验")
    titles = [x["title"] for x in data["items"]]
    assert data["total"] == 2
    assert "数据库原理 实验四" in titles and "计算机网络 抓包实验" in titles


def test_keyword_matches_note(dataset, logged_in):
    """关键词同时搜标题和备注（SQL 里是 title LIKE ? OR note LIKE ?）。"""
    data = api_list(logged_in, q="答辩")
    assert data["total"] == 1
    assert data["items"][0]["title"] == "SPD-1013 课程报告"


def test_filter_by_status_and_priority(dataset, logged_in):
    assert api_list(logged_in, status=1)["total"] == 2
    assert api_list(logged_in, status=0)["total"] == 5
    assert api_list(logged_in, priority=1)["total"] == 2
    assert api_list(logged_in, priority=3)["total"] == 2


def test_filter_by_course_and_uncategorized(dataset, logged_in, courses):
    assert api_list(logged_in, course_id=courses[1]["id"])["total"] == 1
    # 「未分类」是一个有效筛选值，course_id=none 走 IS NULL
    data = api_list(logged_in, course_id="none")
    assert data["total"] == 1
    assert data["items"][0]["title"] == "整理笔记"


def test_combined_filters(dataset, logged_in):
    """多个条件是 AND 关系：未完成 + 高优先级。"""
    data = api_list(logged_in, status=0, priority=1)
    titles = sorted(x["title"] for x in data["items"])
    assert data["total"] == 2
    assert titles == ["SPD-1013 课程报告", "数据库原理 实验四"]


def test_filter_by_date_range(dataset, logged_in):
    data = api_list(logged_in, due_from=day(0), due_to=day(2))
    assert data["total"] == 3


def test_keyword_plus_course_plus_date(dataset, logged_in, courses):
    data = api_list(logged_in, q="实验", course_id=courses[1]["id"],
                    due_from=day(-1), due_to=day(1))
    assert data["total"] == 1
    assert data["items"][0]["title"] == "数据库原理 实验四"


def test_preset_views(dataset, logged_in):
    """提醒预设视图会被翻译成状态 + 日期区间。"""
    assert api_list(logged_in, preset="overdue")["total"] == 1
    assert api_list(logged_in, preset="today")["total"] == 1
    assert api_list(logged_in, preset="due_soon")["total"] == 3   # 今天 / 1 天后 / 2 天后
    assert api_list(logged_in, preset="undone")["total"] == 5


def test_sort_by_priority_both_directions(dataset, logged_in):
    asc = api_list(logged_in, sort="priority", order="asc")["items"]
    desc = api_list(logged_in, sort="priority", order="desc")["items"]
    # 优先级存 1/2/3，所以升序就是「高→中→低」，不受中文编码顺序影响
    assert [x["priority"] for x in asc] == sorted(x["priority"] for x in asc)
    assert asc[0]["priority_label"] == "高"
    assert desc[0]["priority_label"] == "低"


def test_sort_by_due_date(dataset, logged_in):
    items = api_list(logged_in, sort="due_date", order="asc")["items"]
    dates = [x["due_date"] for x in items]
    assert dates == sorted(dates)          # 文本日期的字典序就是时间序
    assert items[0]["due_date"] == day(-2)


def test_illegal_sort_field_falls_back(dataset, logged_in):
    """排序字段走白名单：注入内容会被丢弃并回落默认排序，而不是拼进 SQL。"""
    resp = logged_in.get("/tasks/", query_string={"sort": "id; DROP TABLE tasks--"})
    assert resp.status_code == 200
    assert "截止日期" in resp.get_data(as_text=True)
    # 表还在、数据还在
    assert api_list(logged_in)["total"] == 7


def test_illegal_filter_values_are_ignored(dataset, logged_in):
    """用户手改 URL 塞非法值时应当被丢弃，而不是抛 500。"""
    data = api_list(logged_in, status="abc", priority="9",
                    course_id="xx", due_from="2026-13-45")
    assert data["total"] == 7


def test_pagination(dataset, logged_in, app):
    app.config["PAGE_SIZE"] = 3            # 7 条数据 → 3 页
    first = logged_in.get("/tasks/").get_data(as_text=True)
    assert "第 1 / 3 页" in first

    second = logged_in.get("/tasks/", query_string={"page": 2}).get_data(as_text=True)
    assert "第 2 / 3 页" in second

    # 超出范围的页码要被夹到最后一页，不能是空白页
    last = logged_in.get("/tasks/", query_string={"page": 99}).get_data(as_text=True)
    assert "第 3 / 3 页" in last


def test_list_page_shows_filter_count(dataset, logged_in):
    body = logged_in.get("/tasks/", query_string={"q": "实验", "status": 0}).get_data(as_text=True)
    assert "已筛选 2 个条件" in body
    assert "数据库原理 实验四" in body
    assert "大学英语 单词背诵" not in body
