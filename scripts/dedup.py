#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""去重比对：61 篇 vs posts/2026 已存在文章。
同日期 + 标题模糊匹配（归一化后包含 或 相似度>=0.65）判定为已存在 -> skip。
输出 scripts/dedup.json: {new:[idx...], skip:[{idx,matched,score}]}
"""
import os, re, json
from difflib import SequenceMatcher

REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
POSTS = os.path.join(REPO, "posts", "2026")
SRC = r"E:/workbuddy/2026-10-09-18-07-09/scripts/articles.json"
OUT = r"E:/workbuddy/2026-10-09-18-07-09/scripts/dedup.json"

arts = json.load(open(SRC, encoding="utf-8"))
existing = [d for d in os.listdir(POSTS) if os.path.isdir(os.path.join(POSTS, d))]
print("existing posts/2026 dirs:", len(existing))

def norm(s):
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", s or "")

# 索引：日期 -> [(slug, norm_title_part)]
by_date = {}
for d in existing:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.*)$", d)
    if m:
        by_date.setdefault(m.group(1), []).append((d, norm(m.group(2))))
    else:
        by_date.setdefault("?", []).append((d, norm(d)))

new, skip = [], []
for a in arts:
    date, title = a["date"], a["title"]
    nt = norm(title)
    cands = by_date.get(date, [])
    best, bestscore = None, 0.0
    for slug, ent in cands:
        if not nt or not ent:
            continue
        if ent == nt or ent in nt or nt in ent:
            score = 1.0
        else:
            score = SequenceMatcher(None, ent, nt[: len(ent)] or nt).ratio()
        if score > bestscore:
            best, bestscore = slug, score
    if bestscore >= 0.65:
        skip.append({"idx": a["idx"], "title": title, "matched": best, "score": round(bestscore, 3)})
    else:
        new.append({"idx": a["idx"], "title": title, "date": date, "type": a["type"],
                    "shoulu": a.get("shoulu", ""), "best_guess": best, "score": round(bestscore, 3)})

json.dump({"new": new, "skip": skip}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("NEW (待生成):", len(new))
print("SKIP (已存在):", len(skip))
print("\n=== SKIP 明细 ===")
for s in skip:
    print(f"  {s['idx']:2d} [{s['score']}] {s['title'][:38]!r} -> {s['matched'][:50]!r}")
print("\n=== NEW 明细 ===")
for n in new:
    print(f"  {n['idx']:2d} {n['date']} [{n['type']}] shoulu={n['shoulu'][:14]!r} best={n['score']} | {n['title'][:40]!r}")
