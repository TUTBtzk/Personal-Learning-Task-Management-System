# -*- coding: utf-8 -*-
"""CSV / Excel 导入导出、数据库备份、修改密码。"""
import io
import os
import sqlite3

from conftest import day

CSV_HEADER = "任务名称,所属课程,截止日期,优先级,完成状态,备注\n"


def upload(client, filename, data):
    """模拟表单上传：元组的第二个元素是文件名，后缀白名单就是按它判定的。"""
    return client.post("/import",
                       data={"file": (io.BytesIO(data), filename)},
                       content_type="multipart/form-data",
                       follow_redirects=True)


def test_export_csv_has_bom_and_headers(add_task, logged_in, app):
    add_task(title="导出用任务", due_date=day(1))
    resp = logged_in.get("/export", query_string={"format": "csv"})

    assert resp.status_code == 200
    # BOM 是给 Excel 看的：少了它，双击打开中文全是乱码
    assert resp.data.startswith(b"\xef\xbb\xbf")

    text = resp.data.decode("utf-8-sig")
    assert text.splitlines()[0] == \
        "任务名称,所属课程,截止日期,优先级,完成状态,备注,创建时间,完成时间"
    assert "导出用任务" in text
    # 文件名带项目标识，截图里一眼能看出是本人的导出文件
    assert app.config["PROJECT_CODE"] in resp.headers["Content-Disposition"]


def test_export_respects_current_filters(add_task, logged_in):
    """页面上筛出什么，导出的就是什么——导出链接把当前筛选参数一起带上了。"""
    add_task(title="要导出的实验报告")
    add_task(title="不该导出的读书笔记")

    text = logged_in.get(
        "/export", query_string={"format": "csv", "q": "实验"}
    ).data.decode("utf-8-sig")
    assert "要导出的实验报告" in text
    assert "不该导出的读书笔记" not in text


def test_export_xlsx_is_openable(add_task, logged_in):
    from openpyxl import load_workbook

    add_task(title="Excel 导出任务", priority="1", status=True)
    resp = logged_in.get("/export", query_string={"format": "xlsx"})
    assert resp.status_code == 200

    ws = load_workbook(io.BytesIO(resp.data)).active
    assert ws.max_row == 2                      # 表头 + 1 条数据
    assert [c.value for c in ws[1]][:3] == ["任务名称", "所属课程", "截止日期"]
    assert ws["A2"].value == "Excel 导出任务"
    assert ws["D2"].value == "高" and ws["E2"].value == "已完成"
    assert ws.freeze_panes == "A2"              # 冻结首行，滚动时表头还在
def test_import_partial_success(logged_in, db_tasks, courses):
    """两条好行 + 三条坏行：坏行跳过并逐条报原因，好行照样入库。"""
    lines = [
        f"导入任务一,{courses[0]['name']},{day(1)},高,未完成,来自 CSV 的备注",
        f"导入任务二,,{day(2)},中,已完成,",
        f",{courses[1]['name']},{day(3)},中,未完成,",
        "日期坏行,,2026/09/09,中,未完成,",
        f"优先级坏行,,{day(4)},特急,未完成,",
    ]
    body = upload(logged_in, "tasks.csv",
                  (CSV_HEADER + "\n".join(lines) + "\n").encode("utf-8-sig")
                  ).get_data(as_text=True)

    assert "导入完成：成功 2 条，失败 3 条" in body
    assert "任务名称为空" in body
    assert "不是 YYYY-MM-DD 格式" in body
    assert "应为 高 / 中 / 低" in body

    rows = db_tasks()
    assert {r["title"] for r in rows} == {"导入任务一", "导入任务二"}
    first = next(r for r in rows if r["title"] == "导入任务一")
    assert first["priority"] == 1 and first["course_name"] == courses[0]["name"]
    second = next(r for r in rows if r["title"] == "导入任务二")
    assert second["status"] == 1 and second["completed_at"] is not None


def test_import_creates_unknown_course(logged_in, app, db_tasks):
    """课程名陌生就自动建一门，而不是让整行失败。"""
    csv_text = CSV_HEADER + f"陌生课程的任务,人工智能导论,{day(1)},中,未完成,\n"
    upload(logged_in, "tasks.csv", csv_text.encode("utf-8-sig"))

    assert db_tasks(limit=1)[0]["course_name"] == "人工智能导论"
    from spdapp.models import course_repo
    with app.app_context():
        assert "人工智能导论" in [c["name"] for c in course_repo.list_courses()]


def test_import_accepts_gbk_csv(logged_in, db_tasks):
    """Excel 另存的 CSV 常常是 GBK，编码要逐个试而不是直接抛 UnicodeDecodeError。"""
    csv_text = CSV_HEADER + f"GBK 编码的任务,,{day(1)},低,未完成,\n"
    body = upload(logged_in, "gbk.csv", csv_text.encode("gbk")).get_data(as_text=True)

    assert "成功 1 条" in body
    assert db_tasks(limit=1)[0]["title"] == "GBK 编码的任务"


def test_import_rejects_other_extensions(logged_in, db_tasks):
    body = upload(logged_in, "tasks.txt", "随便写点什么".encode()).get_data(as_text=True)
    assert "只支持 .csv 和 .xlsx 文件" in body
    assert db_tasks() == []


def test_import_without_file(logged_in):
    body = logged_in.post("/import", data={}, follow_redirects=True).get_data(as_text=True)
    assert "请先选择要导入的 CSV 或 Excel 文件" in body


def test_export_then_import_round_trip(add_task, logged_in, db_tasks, courses):
    """导出的文件能原样导回来，证明导出表头与导入模板严格一致。"""
    add_task(title="往返测试任务", course_id=courses[0]["id"], due_date=day(2), priority="1")
    exported = logged_in.get("/export", query_string={"format": "csv"}).data

    body = upload(logged_in, "回传.csv", exported).get_data(as_text=True)
    assert "成功 1 条，失败 0 条" in body
    assert [r["title"] for r in db_tasks()].count("往返测试任务") == 2
def test_backup_creates_valid_snapshot(add_task, logged_in, app):
    """备份走 SQLite 的 backup() API，产出的是能直接打开的一致性快照。"""
    add_task(title="备份前的任务")
    body = logged_in.post("/backup", follow_redirects=True).get_data(as_text=True)

    backup_dir = app.config["BACKUP_DIR"]
    files = [f for f in os.listdir(backup_dir) if f.endswith(".db")]
    assert len(files) == 1
    assert files[0] in body                     # 页面上能看到刚生成的备份

    conn = sqlite3.connect(os.path.join(backup_dir, files[0]))
    try:
        titles = [r[0] for r in conn.execute("SELECT title FROM tasks")]
    finally:
        conn.close()
    assert titles == ["备份前的任务"]


def test_change_password_validations(logged_in, app):
    def post(old, new, confirm):
        return logged_in.post("/password", data={
            "old_password": old, "new_password": new, "confirm_password": confirm,
        }, follow_redirects=True).get_data(as_text=True)

    assert "原密码不正确" in post("wrong-old", "spd-new-pass", "spd-new-pass")
    assert "新密码至少 6 位" in post(app.config["DEFAULT_PASSWORD"], "123", "123")
    assert "两次输入的新密码不一致" in post(
        app.config["DEFAULT_PASSWORD"], "spd-new-pass", "spd-new-pas5")


def test_change_password_then_relogin(logged_in, app):
    resp = logged_in.post("/password", data={
        "old_password": app.config["DEFAULT_PASSWORD"],
        "new_password": "spd-new-pass",
        "confirm_password": "spd-new-pass",
    }, follow_redirects=True)
    assert "密码修改成功" in resp.get_data(as_text=True)

    # 改完密码会强制登出：旧密码失效，新密码可用
    creds = {"username": app.config["DEFAULT_USERNAME"]}
    old_try = logged_in.post("/login", data=dict(creds, password=app.config["DEFAULT_PASSWORD"]))
    assert "账号或密码不正确" in old_try.get_data(as_text=True)

    new_try = logged_in.post("/login", data=dict(creds, password="spd-new-pass"),
                             follow_redirects=True)
    assert "仪表盘" in new_try.get_data(as_text=True)


def test_operation_log_records_import_and_backup(logged_in):
    """导入、导出、备份都要留痕，数据管理页的日志表能追溯每一次数据操作。"""
    upload(logged_in, "log.csv",
           (CSV_HEADER + f"留痕检查任务,,{day(1)},中,未完成,\n").encode("utf-8-sig"))
    logged_in.get("/export", query_string={"format": "csv"})
    logged_in.post("/backup")

    body = logged_in.get("/data").get_data(as_text=True)
    assert "log.csv" in body
    assert "成功 1 条，失败 0 条" in body
    assert "导出 1 条任务" in body
    assert "数据库快照" in body
