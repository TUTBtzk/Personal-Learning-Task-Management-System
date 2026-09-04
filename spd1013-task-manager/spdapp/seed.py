# -*- coding: utf-8 -*-
"""初始数据：登录用户、课程清单、约 20 条演示任务。

演示任务里刻意覆盖了「已逾期 / 今日到期 / 即将到期 / 已完成」四类样本，
并包含一条名称带项目标识的任务：软件项目开发综合实践-SPD1013
"""
from datetime import date, datetime, timedelta

from flask import current_app
from werkzeug.security import generate_password_hash

from .db import get_db

# 课程清单：(名称, 教师, 色标)
DEFAULT_COURSES = [
    ("高等数学", "王老师", "#0d6efd"),
    ("数据库原理", "李老师", "#6f42c1"),
    ("软件工程", "张老师", "#198754"),
    ("计算机网络", "刘老师", "#fd7e14"),
    ("大学英语", "陈老师", "#d63384"),
    ("软件项目开发综合实践", "支老师", "#0dcaf0"),
]

# 演示任务：(任务名称, 课程序号或 None, 截止日期偏移天数, 优先级, 状态, 备注, 完成于几天前)
DEMO_TASKS = [
    ("软件项目开发综合实践-SPD1013", 5, 6, 1, 0, "课程项目：完成系统开发并撰写课程报告（不超过10页）", None),
    ("数据库原理 第3章课后习题", 1, -2, 2, 1, "已提交", 1),
    ("数据库原理 实验四：多表连接查询", 1, 2, 1, 0, "需提交实验报告与 SQL 脚本", None),
    ("数据库原理 期末复习提纲整理", 1, 12, 3, 0, "", None),
    ("高等数学 第5章习题 P112 1-10", 0, -4, 2, 1, "", 5),
    ("高等数学 第6章预习", 0, 0, 3, 0, "今天到期", None),
    ("高等数学 阶段测验", 0, 9, 1, 0, "记得带计算器", None),
    ("软件工程 需求规格说明书初稿", 2, -1, 1, 0, "已逾期，需尽快补交", None),
    ("软件工程 小组 UML 建模作业", 2, 3, 2, 0, "画类图与时序图", None),
    ("软件工程 阅读《人月神话》第2章", 2, 7, 3, 1, "", 0),
    ("计算机网络 实验二：Wireshark 抓包分析", 3, -3, 2, 1, "实验报告已上传", 3),
    ("计算机网络 第4章作业", 3, 1, 1, 0, "明天到期", None),
    ("计算机网络 子网划分练习", 3, 5, 2, 0, "", None),
    ("大学英语 单元测试卷", 4, -5, 3, 1, "", 6),
    ("大学英语 口语 presentation 准备", 4, 4, 2, 0, "主题：科技与生活", None),
    ("大学英语 背诵 Unit5 单词", 4, 0, 3, 0, "今天到期", None),
    ("软件项目开发综合实践 系统截图取证", 5, 4, 1, 0, "覆盖新增/修改/完成/筛选/删除完整流程", None),
    ("软件项目开发综合实践 AI 辅助开发说明", 5, 5, 2, 0, "300 字以内", None),
    ("整理本周学习笔记", None, 2, 3, 0, "不属于具体课程", None),
    ("图书馆借书归还", None, -6, 3, 1, "", 2),
]


def _due(offset_days):
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _completed_ts(days_ago):
    day = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return f"{day} 20:30:00"


def seed_user():
    """写入默认登录用户，姓名/学号取自 config.py。"""
    db = get_db()
    cfg = current_app.config
    db.execute(
        "INSERT INTO users (username, password_hash, display_name, student_id) "
        "VALUES (?, ?, ?, ?)",
        (
            cfg["DEFAULT_USERNAME"],
            generate_password_hash(cfg["DEFAULT_PASSWORD"]),
            cfg["STUDENT_NAME"],
            cfg["STUDENT_ID"],
        ),
    )
    db.commit()


def seed_courses():
    db = get_db()
    db.executemany(
        "INSERT INTO courses (name, teacher, color) VALUES (?, ?, ?)",
        DEFAULT_COURSES,
    )
    db.commit()
    return [row["id"] for row in db.execute("SELECT id FROM courses ORDER BY id")]


def seed_tasks(course_ids):
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for title, idx, offset, priority, status, note, done_days in DEMO_TASKS:
        rows.append((
            title,
            course_ids[idx] if idx is not None else None,
            _due(offset),
            priority,
            status,
            note,
            now,
            now,
            _completed_ts(done_days) if status == 1 and done_days is not None else None,
        ))
    db.executemany(
        "INSERT INTO tasks (title, course_id, due_date, priority, status, note, "
        "created_at, updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    db.execute(
        "INSERT INTO operation_logs (action, target, detail) VALUES (?, ?, ?)",
        ("seed", "初始化", f"写入 {len(rows)} 条演示任务与 {len(course_ids)} 门课程"),
    )
    db.commit()


def seed_all(seed_demo=True):
    seed_user()
    course_ids = seed_courses()
    if seed_demo:
        seed_tasks(course_ids)
