# -*- coding: utf-8 -*-
"""数据管理页：CSV/Excel 导入导出、数据库备份、操作日志、修改密码。"""
import io
import os

from flask import (Blueprint, flash, redirect, render_template, request,
                   send_file, session, url_for)

from ..models import log_repo, task_repo
from ..services import auth_service, io_service, task_service

bp = Blueprint("data_io", __name__)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@bp.route("/data")
def index():
    return render_template(
        "data_io.html",
        logs=log_repo.recent_logs(limit=30),
        log_total=log_repo.count_logs(),
        backups=io_service.list_backups(),
        template_headers=io_service.HEADERS[:6],
        result=session.pop("import_result", None),
    )


@bp.route("/export")
def export():
    """导出当前筛选结果：页面上看到的是哪批数据，导出的就是哪批。"""
    fmt = (request.args.get("format") or "csv").lower()
    filters = task_service.parse_filters(request.args)
    sort = request.args.get("sort") or "due_date"
    order = request.args.get("order") or "asc"
    rows = task_repo.list_tasks(filters, sort, order)

    if fmt == "xlsx":
        payload, mime = io_service.export_xlsx(rows), XLSX_MIME
        filename = io_service.export_filename("xlsx")
    else:
        payload, mime = io_service.export_csv(rows), "text/csv"
        filename = io_service.export_filename("csv")

    # 用 send_file 而不是手拼 Content-Disposition：中文文件名的编码由 Flask 处理
    return send_file(io.BytesIO(payload), mimetype=mime,
                     as_attachment=True, download_name=filename)


@bp.route("/import", methods=["POST"])
def import_data():
    """导入任务。坏行跳过并汇报原因，不因为个别行出错让整个文件白导。"""
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("请先选择要导入的 CSV 或 Excel 文件", "danger")
        return redirect(url_for("data_io.index"))

    try:
        result = io_service.import_tasks(file.filename, file.read())
    except ValueError as exc:
        flash(f"导入失败：{exc}", "danger")
        return redirect(url_for("data_io.index"))

    failed_total = len(result["failed"])
    result["failed"] = result["failed"][:10]     # 结果暂存在 session（cookie）里，只留前 10 条
    result["failed_total"] = failed_total
    result["filename"] = file.filename
    session["import_result"] = result

    flash(f"导入完成：成功 {result['success']} 条，失败 {failed_total} 条",
          "success" if result["success"] else "warning")
    return redirect(url_for("data_io.index"))


@bp.route("/backup", methods=["POST"])
def backup():
    path = io_service.backup_database()
    flash(f"数据库已备份：{os.path.basename(path)}", "success")
    return redirect(url_for("data_io.index"))


@bp.route("/password", methods=["POST"])
def change_password():
    error = auth_service.change_password(
        session.get("uid"),
        request.form.get("old_password"),
        request.form.get("new_password"),
        request.form.get("confirm_password"),
    )
    if error:
        flash(error, "danger")
        return redirect(url_for("data_io.index"))
    auth_service.logout()
    flash("密码修改成功，请用新密码重新登录", "success")
    return redirect(url_for("auth.login"))
