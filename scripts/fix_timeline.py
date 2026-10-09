#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建 timeline/index.html 的月份分组（幂等）。

背景：sync_index.py 之前只把新文章卡片插进了「第一个」月份组（2026年7月），
导致 8/9 月分组缺失、month-count 与总数都没更新。本脚本整体重建
<div class="timeline">…</div>：
  - 复用页面里已有的 post-card 原始 markup（保留原有转义/属性，不重造标题）
  - 按 (年, 月) 降序分组，月内按日期降序
  - 重算 month-count 与 page-desc 的总数
日期取自 search/meta.json，回退用 URL 的日期前缀。
"""
import json
import os
import re
from collections import OrderedDict

REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
TL = os.path.join(REPO, "timeline", "index.html")
META_F = os.path.join(REPO, "search", "meta.json")

CID_T = 'data-astro-cid-bojsfbo5'   # timeline 作用域
CID_C = 'data-astro-cid-sbmovh4h'   # post-card 作用域

# ---------- 1. 日期表 ----------
meta = json.load(open(META_F, encoding="utf-8"))
date_by_url = {}
for m in meta:
    if "/posts/" not in m.get("url", ""):
        continue
    d = (m.get("date") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        date_by_url[m["url"]] = d

def url_date(u):
    """meta 优先，回退 URL 前缀 YYYY-MM-DD"""
    if u in date_by_url:
        return date_by_url[u]
    m = re.search(r"/posts/\d{4}/(\d{4}-\d{2}-\d{2})-", u)
    return m.group(1) if m else None

h = open(TL, encoding="utf-8").read()

# ---------- 2. 抽出所有既有卡片（保原样） ----------
# 站点既有缺陷：2024-10-01 那张卡片缺了 </article>，会吞掉下一张卡。
# 表现为 </h3><article 直接相连，先补回闭合标签（幂等）。
h, nfix = re.subn(r'(</h3>)(<article class="post-card")', r"\1</article>\2", h)
print("补全缺失的 </article>:", nfix)

cards = re.findall(r'<article class="post-card".*?</article>', h, re.S)
print("既有卡片:", len(cards))
assert len(cards) == h.count('<article class="post-card"'), \
    "仍有卡片结构异常: %d != %d" % (len(cards), h.count('<article class="post-card"'))

items = []
seen = set()
nodate = []
for c in cards:
    m = re.search(r'<a href="([^"]+)"[^>]*>', c)
    if not m:
        continue
    url = m.group(1)
    d = url_date(url)
    if d is None:
        nodate.append(url)
        continue
    key = url
    if key in seen:          # 去重，防重复计数
        continue
    seen.add(key)
    items.append((d, url, c))

print("有效卡片:", len(items), "| 无日期:", len(nodate))
if nodate:
    print("  无日期样例:", nodate[:3])

# ---------- 3. 分组 ----------
groups = OrderedDict()
for d, url, c in items:
    groups.setdefault((d[:4], d[5:7]), []).append((d, url, c))

order = sorted(groups.keys(), key=lambda ym: (int(ym[0]), int(ym[1])), reverse=True)

# ---------- 4. 重建 ----------
def card_html(d, url, c):
    return c

parts = []
cur_year = None
declared = 0
for (y, mo) in order:
    rows = sorted(groups[(y, mo)], key=lambda x: x[0], reverse=True)
    if y != cur_year:
        if cur_year is not None:
            parts.append("</section>")
        parts.append(f'<section class="year-section" {CID_T}>'
                     f'<h2 class="year-title" {CID_T} id="{y}">{y}</h2>')
        cur_year = y
    label = f"{y}年{int(mo)}月"
    cnt = len(rows)
    declared += cnt
    parts.append(f'<details class="month-group" {CID_T}>'
                 f'<summary class="month-header" {CID_T}>'
                 f'<span class="month-label" {CID_T}>{label}</span>'
                 f'<span class="month-count" {CID_T}>{cnt} 篇</span>'
                 f'</summary>'
                 f'<div class="month-posts" {CID_T}>')
    for d, url, c in rows:
        parts.append(card_html(d, url, c))
    parts.append("</div></details>")
if cur_year is not None:
    parts.append("</section>")
new_block = f'<div class="timeline" {CID_T}>' + "".join(parts) + "</div>"

# ---------- 5. 替换 ----------
i = h.find('<div class="timeline"')
e = h.find("</main>")
assert i != -1 and e != -1, "未定位 timeline 容器"
tail = h[e - 6:e]
assert tail == "</div>", "timeline 容器结尾不是 </div>，实际=%r" % tail
h2 = h[:i] + new_block + h[e - 6:]

# page-desc 总数
h2 = re.sub(r'(<p class="page-desc"[^>]*>按月份分组，共 )\d+( 篇</p>)',
            lambda m: m.group(1) + str(len(items)) + m.group(2), h2, count=1)

open(TL, "w", encoding="utf-8", newline="\n").write(h2)

# ---------- 6. 输出核对 ----------
print("\n写入完成")
print("month-count 声明合计:", declared, "| 卡片数:", len(items))
print("page-desc:", re.search(r"按月份分组，共 \d+ 篇", h2).group(0))
print("月份组数:", h2.count('<details class="month-group"'),
      "| details 开闭:", h2.count("<details"), h2.count("</details>"))
print("\n2026 各月:")
for b in re.findall(r'<details class="month-group".*?</details>', h2, re.S):
    lab = re.search(r'<span class="month-label"[^>]*>([^<]+)</span>', b).group(1)
    if lab.startswith("2026"):
        cnt = re.search(r'<span class="month-count"[^>]*>(\d+) 篇</span>', b).group(1)
        n = b.count('<article class="post-card"')
        print(f"   {lab:10s} 声明 {cnt:>3s}  实际 {n:>3d}  {'OK' if int(cnt)==n else '<<< 不符'}")
print("\n年份分区:", re.findall(r'<h2 class="year-title"[^>]*id="(\d{4})">', h2))
