# -*- coding: utf-8 -*-
"""智能任务分类：从任务名称的关键词推断所属课程与优先级。

纯规则实现，不引入任何模型。理由：规则可解释、可单测、零依赖，
在报告里三句话就能讲清「为什么给出这个建议」；换成模型反而讲不清也跑不稳。
"""
from ..models import course_repo

# 课程别名表：键会用「包含匹配」去找真实课程（「数学」能命中「高等数学」）
COURSE_KEYWORDS = {
    "数据库": ["数据库", "sql", "db", "建表", "范式", "事务", "索引", "触发器"],
    "高等数学": ["高数", "数学", "微积分", "求导", "积分", "极限", "线代", "矩阵"],
    "软件工程": ["软工", "软件工程", "uml", "需求", "用例", "类图", "设计模式"],
    "计算机网络": ["网络", "tcp", "ip", "http", "抓包", "子网", "路由", "wireshark"],
    "英语": ["英语", "english", "单词", "作文", "听力", "口语", "unit", "四级", "六级"],
    "软件项目开发综合实践": ["综合实践", "课程项目", "spd", "项目报告", "答辩"],
}

# 优先级关键词：命中「实验/报告/答辩」这类硬性交付物判为高，学习性任务判为低
HIGH_PRIORITY_WORDS = ["实验", "报告", "大作业", "答辩", "考试", "测验", "截止",
                       "提交", "论文", "presentation", "项目", "汇报"]
LOW_PRIORITY_WORDS = ["预习", "复习", "整理", "阅读", "笔记", "背诵", "了解", "旁听"]


def suggest(title):
    """返回建议字典：course_id / course_name / priority / priority_label / reason。"""
    text = (title or "").strip().lower()
    result = {
        "course_id": None, "course_name": None,
        "priority": None, "priority_label": None,
        "reason": "", "matched": False,
    }
    if not text:
        return result

    reasons = []
    courses = course_repo.list_courses()

    # 规则 1：任务名里直接出现了完整课程名
    for c in courses:
        if c["name"].lower() in text:
            result["course_id"], result["course_name"] = c["id"], c["name"]
            reasons.append(f"名称含课程名「{c['name']}」")
            break

    # 规则 2：走别名关键词表
    if result["course_id"] is None:
        for key, words in COURSE_KEYWORDS.items():
            hit = next((w for w in words if w in text), None)
            if hit is None:
                continue
            match = next((c for c in courses
                          if key in c["name"] or c["name"] in key), None)
            if match:
                result["course_id"], result["course_name"] = match["id"], match["name"]
                reasons.append(f"关键词「{hit}」→ {match['name']}")
                break

    # 规则 3：优先级
    high_hit = next((w for w in HIGH_PRIORITY_WORDS if w in text), None)
    low_hit = next((w for w in LOW_PRIORITY_WORDS if w in text), None)
    if high_hit:
        result["priority"], result["priority_label"] = 1, "高"
        reasons.append(f"关键词「{high_hit}」→ 高优先级")
    elif low_hit:
        result["priority"], result["priority_label"] = 3, "低"
        reasons.append(f"关键词「{low_hit}」→ 低优先级")
    else:
        result["priority"], result["priority_label"] = 2, "中"
        reasons.append("未命中关键词 → 默认中优先级")

    result["matched"] = result["course_id"] is not None or high_hit or low_hit
    result["matched"] = bool(result["matched"])
    result["reason"] = "；".join(reasons)
    return result
