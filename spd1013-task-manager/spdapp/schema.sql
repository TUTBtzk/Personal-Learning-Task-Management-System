-- 个人学习任务管理与数据分析系统  SPD-1013
-- 表结构：users / courses / tasks / operation_logs
-- 执行本脚本会重建全部表（原有数据清空）

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS operation_logs;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

-- 用户表：单用户，为首页信息条提供姓名与学号
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,                 -- 只存哈希，不存明文密码
    display_name  TEXT NOT NULL,                 -- 姓名
    student_id    TEXT NOT NULL,                 -- 学号
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 课程表
CREATE TABLE courses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,             -- 唯一约束：避免同一门课写成多条导致统计分裂
    teacher    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#0d6efd',  -- 色标：图表与日历统一配色
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 任务表（核心）
CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,                                      -- 任务名称
    course_id    INTEGER,                                               -- 所属课程，NULL = 未分类
    due_date     TEXT    NOT NULL,                                      -- 截止日期 YYYY-MM-DD
    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority IN (1,2,3)),-- 1 高 / 2 中 / 3 低
    status       INTEGER NOT NULL DEFAULT 0 CHECK (status IN (0,1)),     -- 0 未完成 / 1 已完成
    note         TEXT    NOT NULL DEFAULT '',                           -- 备注
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at TEXT,                                                  -- 完成时刻，趋势图数据来源
    FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE SET NULL
);

CREATE INDEX idx_tasks_due    ON tasks (due_date);
CREATE INDEX idx_tasks_status ON tasks (status);
CREATE INDEX idx_tasks_course ON tasks (course_id);

-- 操作日志表：记录每一次增删改，作为「完整操作过程」的证据
CREATE TABLE operation_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL,                    -- create/update/delete/toggle/import/export/backup
    target     TEXT NOT NULL DEFAULT '',         -- 任务标题快照（任务删除后仍可追溯）
    detail     TEXT NOT NULL DEFAULT '',         -- 变更摘要，如「优先级 中→高」
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX idx_logs_created ON operation_logs (created_at DESC);
