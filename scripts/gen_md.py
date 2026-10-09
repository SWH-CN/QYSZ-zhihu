#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""articles.json -> 每篇独立 .md（项目 markdown 归档规范）
docs/2026/YYYY-MM-DD-<标题前20字>.md
YAML: title -> date -> type；正文逐字保留；文末 [^1] 来源脚注（有则加）
"""
import os, re, json
from collections import Counter

REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
OUT_DIR = os.path.join(REPO, "docs", "2026")
SRC = r"E:/workbuddy/2026-10-09-18-07-09/scripts/articles.json"
REPORT = r"E:/workbuddy/2026-10-09-18-07-09/scripts/md_report.txt"

os.makedirs(OUT_DIR, exist_ok=True)
arts = json.load(open(SRC, encoding="utf-8"))

def sanitize(s):
    out = []
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
            out.append(ch)
        elif ch.isalnum() or ch in "'\"":
            out.append(ch)
        else:
            out.append("-")
    return re.sub("-+", "-", "".join(out)).strip("-")

def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

used = {}
rows = []
for a in arts:
    date = a.get("date", "")
    title = a.get("title", "") or a.get("h2_title", "")
    slug = sanitize(title)[:20] or f"post{a['idx']:02d}"
    base = f"{date}-{slug}" if date else f"nodate-{slug}"
    if base in used:
        used[base] += 1
        base = f"{base}-{used[base]}"
    else:
        used[base] = 1
    lines = ["---", f"title: {yq(title)}", f"date: {yq(date)}", f"type: {yq(a.get('type',''))}", "---", ""]
    for seg in a.get("body", []):
        if seg.startswith("__IMG__"):
            h = seg[7:]
            lines.append(f"![图](../../assets/_shared/{h}.webp)")
            lines.append("")
        else:
            lines.append(seg)
            lines.append("")
    if a.get("zhihu"):
        lines.append("")
        for i, u in enumerate(a["zhihu"], 1):
            lines.append(f"[^{i}]: {u}")
    txt = "\n".join(lines).rstrip() + "\n"
    fp = os.path.join(OUT_DIR, base + ".md")
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    rows.append((a["idx"], base, os.path.getsize(fp), a.get("type", ""), date))

with open(REPORT, "w", encoding="utf-8") as f:
    f.write(f"total: {len(rows)}\n")
    f.write(f"type counts: {dict(Counter(r[3] for r in rows))}\n")
    f.write(f"missing date: {[r[0] for r in rows if not r[4]]}\n")
    for r in rows:
        f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n")

print("written:", len(rows), "->", OUT_DIR)
print("type counts:", dict(Counter(r[3] for r in rows)))
print("missing date:", [r[0] for r in rows if not r[4]])
print("total bytes:", sum(r[2] for r in rows))
for r in rows[:8]:
    print(" ", r[0], r[1], r[2])
