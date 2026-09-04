# -*- coding: utf-8 -*-
"""任务增删改查与登录保护。"""
from conftest import day


def test_login_required(client):
    """未登录访问首页应重定向到登录页。"""
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_with_wrong_password(client, app):
    resp = client.post("/login", data={
        "username": app.config["DEFAULT_USERNAME"], "password": "wrong-password",
    })
    assert resp.status_code == 200          # 停在登录页并提示，不跳转
    assert "账号或密码不正确" in resp.get_data(as_text=True)


def test_dashboard_shows_identity(logged_in):
    """首页必须显示姓名、学号、项目标识（评分硬性要求）。"""
    body = logged_in.get("/").get_data(as_text=True)
    assert "佟政慷" in body
    assert "239001013" in body
    assert "SPD-1013" in body


def test_create_task(add_task, logged_in, db_tasks):
    resp = add_task(title="软件项目开发综合实践-SPD1013 报告", due_date=day(3), priority="1")
    assert resp.status_code == 200
    assert "任务已创建" in resp.get_data(as_text=True)

    rows = db_tasks(limit=1)
    assert rows[0]["title"] == "软件项目开发综合实践-SPD1013 报告"
    assert rows[0]["priority"] == 1
    assert rows[0]["status"] == 0
    assert rows[0]["completed_at"] is None


def test_create_task_with_course(add_task, courses, db_tasks):
    add_task(title="数据库原理 实验一", course_id=courses[1]["id"])
    row = db_tasks(limit=1)[0]
    assert row["course_id"] == courses[1]["id"]
    assert row["course_name"] == courses[1]["name"]


def test_create_rejects_empty_title(logged_in, db_tasks):
    """校验失败要回显表单并给出字段级提示，而不是入库或 500。"""
    resp = logged_in.post("/tasks/new", data={
        "title": "  ", "due_date": day(1), "priority": "2", "course_id": "", "note": "",
    })
    assert resp.status_code == 400
    assert "任务名称不能为空" in resp.get_data(as_text=True)
    assert db_tasks() == []


def test_create_rejects_bad_date(logged_in):
    resp = logged_in.post("/tasks/new", data={
        "title": "日期格式测试", "due_date": "2026/09/09", "priority": "2",
    })
    assert resp.status_code == 400
    assert "YYYY-MM-DD" in resp.get_data(as_text=True)


def test_edit_task(add_task, logged_in, db_tasks):
    add_task(title="原始标题", due_date=day(5), priority="3")
    task_id = db_tasks(limit=1)[0]["id"]

    resp = logged_in.post(f"/tasks/{task_id}/edit", data={
        "title": "修改后的标题", "due_date": day(6), "priority": "1",
        "course_id": "", "note": "补充备注",
    }, follow_redirects=True)
    assert resp.status_code == 200

    row = db_tasks(limit=1)[0]
    assert row["title"] == "修改后的标题"
    assert row["priority"] == 1
    assert row["due_date"] == day(6)
    assert row["note"] == "补充备注"


def test_toggle_task_returns_json_and_sets_completed_at(add_task, logged_in, db_tasks):
    add_task(title="待完成任务", due_date=day(2))
    task_id = db_tasks(limit=1)[0]["id"]

    resp = logged_in.post(f"/tasks/{task_id}/toggle")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["status"] == 1
    assert body["data"]["state_label"] == "已完成"
    assert body["data"]["summary"]["done"] == 1
    assert db_tasks(limit=1)[0]["completed_at"] is not None

    # 再点一次应恢复未完成，并清空完成时刻
    again = logged_in.post(f"/tasks/{task_id}/toggle").get_json()
    assert again["data"]["status"] == 0
    assert db_tasks(limit=1)[0]["completed_at"] is None


def test_delete_task(add_task, logged_in, db_tasks):
    add_task(title="待删除任务")
    task_id = db_tasks(limit=1)[0]["id"]

    resp = logged_in.post(f"/tasks/{task_id}/delete",
                          data={"back": "/tasks/"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "已删除任务" in resp.get_data(as_text=True)
    assert db_tasks() == []


def test_missing_task_returns_404(logged_in):
    assert logged_in.get("/tasks/9999/edit").status_code == 404
    assert logged_in.post("/tasks/9999/toggle").status_code == 404
    assert logged_in.post("/tasks/9999/delete").status_code == 404


def test_delete_rejects_external_redirect(add_task, logged_in, db_tasks):
    """back 参数只接受站内地址，构造外部地址时应回落到任务列表。"""
    add_task(title="跳转安全测试")
    task_id = db_tasks(limit=1)[0]["id"]

    resp = logged_in.post(f"/tasks/{task_id}/delete",
                          data={"back": "//evil.example.com/"})
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]
    assert resp.headers["Location"].endswith("/tasks/")


def test_operation_log_written(add_task, logged_in):
    """增删改都要留痕，数据管理页能看到操作日志。"""
    add_task(title="日志检查任务")
    body = logged_in.get("/data").get_data(as_text=True)
    assert "新增" in body
    assert "日志检查任务" in body


def test_create_task_marked_done_has_completed_at(add_task, db_tasks):
    """新增时就勾选「已完成」，也要补上完成时刻，否则趋势图统计不到。"""
    add_task(title="创建即完成", status=True)
    row = db_tasks(limit=1)[0]
    assert row["status"] == 1
    assert row["completed_at"] is not None
