# -*- coding: utf-8 -*-
"""项目配置。

个人学习任务管理与数据分析系统
姓名：佟政慷    学号：239001013    项目标识：SPD-1013
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


class Config:
    """默认配置（本机运行）。"""

    # ---------- 个性化信息：首页信息条、导出文件名、报告证据都取自这里 ----------
    STUDENT_NAME = "佟政慷"
    STUDENT_ID = "239001013"
    # 项目标识由学号后四位推导，不写死字符串：学号改了标识自动跟着变
    PROJECT_CODE = "SPD-" + STUDENT_ID[-4:]
    APP_NAME = "个人学习任务管理与数据分析系统"

    # ---------- 默认登录账号（首次建库时写入 users 表，密码只存哈希）----------
    # 如需修改：改这里的密码后删除 data/tasks.db 重新启动，或登录后在「数据管理」页改密码
    DEFAULT_USERNAME = "admin"
    DEFAULT_PASSWORD = "spd1013"

    # ---------- 数据持久化 ----------
    DATABASE = os.path.join(DATA_DIR, "tasks.db")
    BACKUP_DIR = os.path.join(DATA_DIR, "backups")

    # ---------- 安全相关 ----------
    # 固定 dev key 是为了重启后登录状态不失效；如需更换可设环境变量 SPD_SECRET_KEY
    SECRET_KEY = os.environ.get("SPD_SECRET_KEY", "spd-1013-local-dev-secret-key")
    # REST API 用请求头 X-API-KEY 校验，仅供本机演示，不是生产级鉴权
    API_KEY = os.environ.get("SPD_API_KEY", "spd1013-api-key")
    CSRF_ENABLED = True

    # ---------- 业务参数 ----------
    REMIND_DAYS = 3          # 距截止 N 天内视为「即将到期」
    PAGE_SIZE = 10           # 任务列表每页条数
    TREND_DAYS = 7           # 完成趋势统计天数
    SEED_ON_INIT = True      # 首次建库时写入演示数据

    # ---------- 上传限制 ----------
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024      # 单个上传文件最大 2 MB
    ALLOWED_UPLOAD_EXT = (".csv", ".xlsx")    # 导入文件后缀白名单


class TestConfig(Config):
    """pytest 用配置：临时数据库 + 关闭 CSRF 校验。"""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    CSRF_ENABLED = False
    SEED_ON_INIT = False
