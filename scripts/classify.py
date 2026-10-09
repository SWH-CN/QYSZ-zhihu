#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分类推断：为 60 篇新文章分配既有 L1/L2（不新建分类）。
只按【标题】匹配（正文会误命中），优先级：关键词规则 > 收录于映射 > 按类型兜底。
输出 scripts/category_map.json 供复核。
"""
import os, re, json
from collections import Counter

SRC = r"E:/workbuddy/2026-10-09-18-07-09/scripts/articles.json"
DEDUP = r"E:/workbuddy/2026-10-09-18-07-09/scripts/dedup.json"
OUT = r"E:/workbuddy/2026-10-09-18-07-09/scripts/category_map.json"

arts = json.load(open(SRC, encoding="utf-8"))
dd = json.load(open(DEDUP, encoding="utf-8"))
new_idx = {n["idx"] for n in dd["new"]}

# 关键词规则（有序，先命中先得）——只映射到既有 L2
RULES = [
    (r"涨停|A股|个股|中化国际|新华医疗|大盘|仓位|建仓", "投资理财", "个股实战交易"),
    (r"锦标赛|泰拳|拳手|设擂|擂台|奖牌|金牌|决赛|对抗赛|木兰|陆鸽|全败|卫冕|出战|冠军|运动员|赢了|输了|领军|全队",
     "武术格斗", "太极征泰战报"),
    (r"传武|传统武术|武术|晚清十大高手|体操表演|太极|格斗|散打", "武术格斗", "传武论道与体制"),
    (r"财新|清黑|黑子|造谣|抹黑|碰瓷|举报|猎熊|熊黄|熊杰|黄小燕|团伙作案|过气媒体|老挝|中老|通报|法院",
     "新教育", "社区纷争与论辩"),
    (r"家长|父母|家庭|公主|传承|刷题|心理因素|自控|孩子", "新教育", "家庭与品格教育"),
    (r"英语|升学|留学|雅思|托福", "新教育", "英语突破与升学"),
    (r"今日三语|今日学堂|磨丁|学制|学完12年|4年学完|记者10问|记者十问|15岁上大学|办学|教育模式|教育成果|教育结果|教育界华为|国际学校|教学制度|新教育|学堂",
     "新教育", "学堂运营与课程"),
    (r"哈姆雷特|莎士比亚|俞敏洪|刘强东|985|研究生|自学|学历|福报|格局|人生打卡", "人生哲理", "思维与认知"),
    (r"南非|能源|人类文明|体制|毛主席|国学|传统文化|自由|管理者", "社会与文化", "文明与体制"),
    (r"帮扶老人|按闹分配|索赔|媒体|热搜|刘翔|代言", "社会与文化", "社会现象评论"),
    (r"饮食|两餐|晚餐|健康|身体", "人生哲理", "人生意义与幸福"),
]

SHOULU_MAP = {
    "清一太极武术理论与实践": ("武术格斗", "传武论道与体制"),
    "新教育天书": ("新教育", "学堂运营与课程"),
    "富裕家庭的教育与传承问题研究": ("新教育", "家庭与品格教育"),
    "清一公社 百年传承": ("新教育", "学堂运营与课程"),
    "清一新教育家长考评题库": ("新教育", "学堂运营与课程"),
    "价值文章转载": ("社会与文化", "杂感随笔"),
}

FALLBACK = {"想法": ("社会与文化", "杂感随笔"),
            "回答": ("新教育", "社区纷争与论辩"),
            "文章": ("新教育", "学堂运营与课程")}

out = []
for a in arts:
    if a["idx"] not in new_idx:
        out.append({"idx": a["idx"], "title": a["title"], "status": "skip"})
        continue
    text = a["title"]                      # 只用标题，避免正文误命中
    l1 = l2 = rule = None
    for pat, _l1, _l2 in RULES:
        if re.search(pat, text):
            l1, l2, rule = _l1, _l2, "kw:" + re.sub(r"[|\\]", "/", pat)[:20]
            break
    if not l1:
        sh = a.get("shoulu", "")
        if sh in SHOULU_MAP:
            (l1, l2), rule = SHOULU_MAP[sh], "shoulu:" + sh
    if not l1:
        l1, l2 = FALLBACK.get(a.get("type", ""), ("社会与文化", "杂感随笔"))
        rule = "fallback:" + a.get("type", "")
    out.append({"idx": a["idx"], "title": a["title"], "date": a["date"], "type": a["type"],
                "shoulu": a.get("shoulu", ""), "L1": l1, "L2": l2, "rule": rule, "status": "new"})

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
new = [o for o in out if o["status"] == "new"]
print("classified:", len(new))
print("L1 counts:", dict(Counter(o["L1"] for o in new)))
print("L2 counts:", dict(Counter(f"{o['L1']}/{o['L2']}" for o in new)))
print("\n=== 明细 ===")
for o in new:
    print(f"  {o['idx']:2d} {o['L1']}/{o['L2']:<16} [{o['rule'][:22]:<22}] {o['title'][:32]!r}")
