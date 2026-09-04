# -*- coding: utf-8 -*-
"""REST API（扩展功能）：鉴权、CRUD、元信息、智能分类。"""
from conftest import day


def test_read_requires_login_or_key(client, api_headers, app):
    """未登录且不带 key 的读请求返回 401 JSON，而不是跳转到登录页。"""
    anon = client.get("/api/tasks")
    assert anon.status_code == 401
    assert anon.get_json()["msg"] == "需要登录或提供 X-API-KEY"

    assert client.get("/api/tasks", headers=api_headers).status_code == 200
    # 也支持 ?api_key=，方便浏览器地址栏直接查看接口返回
    assert client.get("/api/tasks",
                      query_string={"api_key": app.config["API_KEY"]}).status_code == 200


def test_write_requires_api_key_even_when_logged_in(logged_in, db_tasks):
    """写操作只认请求头 key：浏览器无法跨站伪造自定义头，会话本身不足以授权。"""
    resp = logged_in.post("/api/tasks", json={"title": "无 key 的写请求", "due_date": day(1)})
    assert resp.status_code == 401
    assert resp.get_json()["msg"] == "缺少或错误的 X-API-KEY 请求头"
    assert db_tasks() == []

    bad = logged_in.post("/api/tasks", headers={"X-API-KEY": "wrong-key"},
                         json={"title": "错 key 的写请求", "due_date": day(1)})
    assert bad.status_code == 401
    assert db_tasks() == []


def test_api_full_crud(client, api_headers, courses):
    """接口全链路：创建 → 查询 → 修改 → 切换状态 → 删除。"""
    created = client.post("/api/tasks", headers=api_headers, json={
        "title": "接口创建的任务 SPD-1013",
        "course_id": courses[1]["id"],          # JSON 里是数字，服务层要能兼容
        "due_date": day(2), "priority": 1, "note": "由 curl 创建",
    })
    assert created.status_code == 201
    body = created.get_json()
    assert body["code"] == 0 and body["msg"] == "已创建"

    task = body["data"]
    task_id = task["id"]
    assert task["priority_label"] == "高"
    assert task["course"] == courses[1]["name"]
    assert task["state"] == "soon" and task["days_left"] == 2

    got = client.get(f"/api/tasks/{task_id}", headers=api_headers).get_json()["data"]
    assert got["title"] == "接口创建的任务 SPD-1013"

    updated = client.put(f"/api/tasks/{task_id}", headers=api_headers, json={
        "title": "接口修改后的任务", "due_date": day(5), "priority": 3,
    }).get_json()["data"]
    assert updated["title"] == "接口修改后的任务"
    assert updated["priority_label"] == "低" and updated["course"] == "未分类"

    toggled = client.post(f"/api/tasks/{task_id}/toggle", headers=api_headers).get_json()
    assert toggled["msg"] == "已标记为已完成"
    assert toggled["data"]["status"] == 1 and toggled["data"]["state_label"] == "已完成"
    assert toggled["data"]["completed_at"] is not None

    deleted = client.delete(f"/api/tasks/{task_id}", headers=api_headers).get_json()
    assert deleted["msg"] == "已删除"
    assert client.get(f"/api/tasks/{task_id}", headers=api_headers).status_code == 404
def test_api_validation_errors_are_422(client, api_headers, db_tasks):
    resp = client.post("/api/tasks", headers=api_headers,
                       json={"title": "  ", "due_date": "2026/09/09"})
    assert resp.status_code == 422
    msg = resp.get_json()["msg"]
    assert "任务名称不能为空" in msg and "YYYY-MM-DD" in msg
    assert db_tasks() == []


def test_api_missing_task_returns_404_json(client, api_headers):
    for method, path in (("get", "/api/tasks/9999"),
                         ("put", "/api/tasks/9999"),
                         ("delete", "/api/tasks/9999"),
                         ("post", "/api/tasks/9999/toggle")):
        resp = getattr(client, method)(
            path, headers=api_headers,
            json={"title": "任意标题", "due_date": day(1)})
        assert resp.status_code == 404
        assert resp.get_json()["msg"] == "任务不存在"


def test_api_list_shares_filters_with_page(add_task, logged_in):
    """接口和页面共用同一套筛选/排序参数，两边结果一致。"""
    add_task(title="接口筛选 实验报告", priority="1")
    add_task(title="接口筛选 课外阅读", priority="3", status=True)

    data = logged_in.get("/api/tasks", query_string={"q": "实验", "status": 0}).get_json()["data"]
    assert data["total"] == 1 and data["count"] == 1
    assert data["items"][0]["title"] == "接口筛选 实验报告"

    limited = logged_in.get("/api/tasks", query_string={"limit": 1}).get_json()["data"]
    assert limited["total"] == 2 and limited["count"] == 1


def test_api_courses(client, api_headers, courses):
    rows = client.get("/api/courses", headers=api_headers).get_json()["data"]
    assert len(rows) == len(courses)
    assert rows[0]["color"].startswith("#")
    assert all(r["teacher"] for r in rows)


def test_api_stats_shape(add_task, logged_in, app):
    add_task(title="统计接口任务", status=True)
    data = logged_in.get("/api/stats").get_json()["data"]

    assert set(data) >= {"summary", "by_course", "by_priority", "trend", "today"}
    assert data["summary"]["completion_rate"] == 100.0
    assert len(data["trend"]) == app.config["TREND_DAYS"]
    assert len(data["by_priority"]) == 3
    assert data["today"] == day(0)


def test_api_meta_carries_identity(client, api_headers, app):
    """接口截图里也要出现姓名 / 学号 / 项目标识。"""
    data = client.get("/api/meta", headers=api_headers).get_json()["data"]
    assert data["student_name"] == "佟政慷"
    assert data["student_id"] == "239001013"
    assert data["project_code"] == "SPD-1013"
    assert data["remind_days"] == app.config["REMIND_DAYS"]


def test_api_classify_suggests_course_and_priority(client, api_headers):
    """规则分类：课程名 / 别名关键词命中课程，交付物类词判高、学习类词判低。"""
    hit = client.get("/api/classify", headers=api_headers,
                     query_string={"title": "数据库原理 实验五：索引优化"}).get_json()["data"]
    assert hit["matched"] is True
    assert hit["course_name"] == "数据库原理"
    assert hit["priority"] == 1 and hit["priority_label"] == "高"
    assert "实验" in hit["reason"]

    alias = client.get("/api/classify", headers=api_headers,
                       query_string={"title": "整理线代笔记"}).get_json()["data"]
    assert alias["course_name"] == "高等数学"       # 「线代」是高等数学的别名关键词
    assert alias["priority"] == 3

    miss = client.get("/api/classify", headers=api_headers,
                      query_string={"title": "去操场跑步"}).get_json()["data"]
    assert miss["matched"] is False
    assert miss["course_id"] is None
    assert miss["priority"] == 2                    # 兜底给中优先级，但不算命中
