# 个人学习任务管理与数据分析系统

> 软件项目开发综合实践 · 课程项目
> 姓名：**佟政慷**　学号：**239001013**　项目标识：**SPD-1013**

一个本机运行的 Web 应用：录入并管理学习任务，按课程 / 状态 / 优先级 / 截止日期做多条件筛选，
再把任务数据汇总成四张图表。技术栈 Flask 3 + SQLite + Bootstrap 5 + Chart.js 4，零外部服务依赖。

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开 <http://127.0.0.1:5000>，默认账号 `admin` / `spd1013`（可在「数据管理」页修改）。

首次启动会自动建库、写入账号与 6 门课程，并生成约 20 条演示任务；
数据库文件位于 `data/tasks.db`，删掉它再启动即可恢复出厂状态。

只监听 `127.0.0.1`，不对外网开放。需要热重载调试时用 `SPD_DEBUG=1 python app.py`。

## 功能

基础功能

- 任务的新增 / 编辑 / 删除 / 完成状态切换（列表页勾选即完成，统计数字同步刷新）
- 任务字段：名称、所属课程、截止日期、优先级（高 / 中 / 低）、完成状态、备注
- 关键词搜索（名称 + 备注）与按课程、状态、优先级、日期区间的多条件组合筛选
- 四项统计：总任务数、已完成、未完成、完成率

扩展功能

- **数据分析**：完成情况环形图、课程维度堆叠柱状图、优先级分布条形图、近 7 天完成趋势折线图
- **截止提醒**：已逾期 / 今天到期 / N 天内到期三档预设视图 + 导航栏铃铛角标
- **日历视图**：按月展示任务，点某天的 `+` 直接以该日期新建任务
- **导入导出**：CSV（带 BOM，Excel 直接双击可读）/ Excel 导出，导出即当前筛选结果；
  CSV / Excel 导入支持部分成功，坏行逐条报错；一键数据库备份（SQLite `backup()` 快照）
- **REST API**：`/api/*` 提供任务 CRUD、课程、统计与智能分类接口
- **智能分类**：从任务名称的关键词推断所属课程与优先级，新建任务时给出可一键采纳的建议

## 目录结构

```
spd1013-task-manager/
├─ app.py                 启动入口
├─ config.py              配置（个人信息、账号、业务参数、上传限制）
├─ requirements.txt
├─ data/                  运行时生成：tasks.db 与 backups/
├─ spdapp/
│  ├─ __init__.py         应用工厂：建库、注册蓝图、登录守卫、CSRF、模板过滤器
│  ├─ db.py               sqlite3 连接管理（g 作用域 + 外键开关）
│  ├─ schema.sql          建表语句
│  ├─ seed.py             初始账号、课程与演示任务
│  ├─ models/             唯一写 SQL 的一层：task/course/log/user/stats repo
│  ├─ services/           业务规则：校验、派生状态、统计、导入导出、分类、鉴权
│  ├─ views/              路由（不写 SQL）：auth/dashboard/tasks/calendar/data_io/api
│  ├─ templates/          Jinja2 模板
│  └─ static/             css / js / vendor（Bootstrap 与 Chart.js 均为本地文件）
└─ tests/                 pytest 用例（62 条）
```

分层约定：`views` → `services` → `models`，SQL 只出现在 `models/`，
所有参数都用 `?` 占位符传入；`ORDER BY` 无法参数化，改用字段白名单。

## REST API

读接口允许已登录会话直接调用（页面图表就是这么取数的），外部调用需带 `X-API-KEY`
（默认 `spd1013-api-key`，见 `config.py`）；**写接口只认请求头里的 key**。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks` | 任务列表，筛选 / 排序参数与页面完全一致，支持 `limit` |
| GET | `/api/tasks/<id>` | 单条任务 |
| POST | `/api/tasks` | 新建任务（JSON） |
| PUT | `/api/tasks/<id>` | 修改任务（JSON） |
| DELETE | `/api/tasks/<id>` | 删除任务 |
| POST | `/api/tasks/<id>/toggle` | 切换完成状态 |
| GET | `/api/courses` | 课程列表 |
| GET | `/api/stats` | 仪表盘全部统计数据（与页面同源） |
| GET | `/api/classify?title=` | 智能分类建议 |
| GET | `/api/meta` | 项目与身份信息 |

```bash
# 读：带 key
curl -H "X-API-KEY: spd1013-api-key" http://127.0.0.1:5000/api/stats

# 写：新建一条任务
curl -X POST http://127.0.0.1:5000/api/tasks \
     -H "X-API-KEY: spd1013-api-key" -H "Content-Type: application/json" \
     -d "{\"title\":\"接口创建的任务\",\"due_date\":\"2026-09-09\",\"priority\":1}"
```

响应统一为 `{"code": 0, "msg": "ok", "data": ...}`，出错时 `code` 与 HTTP 状态码一致
（401 未授权 / 404 不存在 / 422 校验失败）。

## 测试

```bash
python -m pytest -q          # 62 passed
```

每个用例都用一个全新的临时数据库文件（不用 `:memory:`——SQLite 内存库是「一个连接一个库」，
而应用每个请求都新建连接）。除了功能正确性，用例还专门覆盖了容易出错的边界：

- 空库时完成率的零除保护、趋势图补零、优先级补零
- 排序字段注入 `id; DROP TABLE tasks--` 被白名单丢弃，数据完好
- 非法筛选值（`status=abc`、`due_from=2026-13-45`）被忽略而不是 500
- 页码越界夹到最后一页、删除后的站内跳转不接受外部地址
- 写接口缺少 `X-API-KEY` 时返回 401，会话本身不足以授权
- 导入的部分成功语义：坏行跳过并报原因，好行照常入库

## 安全说明

单用户本机项目，安全措施按「能讲清楚」的标准做，不假装生产级：
密码经 Werkzeug PBKDF2 加盐哈希存储；写操作有会话绑定的 CSRF 令牌；
`X-API-KEY` 明文写在配置里、不过期、无速率限制，仅供本机演示与接口验证。
