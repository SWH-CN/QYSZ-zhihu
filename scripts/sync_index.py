#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同步站点索引（幂等：已存在则不重复添加）
- search/meta.json + bodies-N.json
- sitemap-0.xml
- timeline/index.html
- categories/<L1>/index.html 与 categories/<L1>/<L2>/index.html
- index.html（年份计数 / footer / 最新文章）
- README.md（全量重新生成）
"""
import os, re, json, html, shutil
from collections import Counter, defaultdict
from urllib.parse import quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# REPO 默认取脚本所在目录的上一级（即仓库根）；换机 clone 后零配置即可用，可用环境变量 QYSZ_REPO 覆盖
REPO = os.environ.get("QYSZ_REPO", os.path.dirname(SCRIPT_DIR))
# NEW 默认取脚本同目录的 new_posts.json（流水线生成的中间产物）；可用 QYSZ_NEW 覆盖
NEW = os.environ.get("QYSZ_NEW", os.path.join(SCRIPT_DIR, "new_posts.json"))
CHUNK = 100

recs = json.load(open(NEW, encoding="utf-8"))
META_F = os.path.join(REPO, "search", "meta.json")
meta = json.load(open(META_F, encoding="utf-8"))
have = {m["url"] for m in meta}

# ---------- 1. meta.json ----------
added = [r for r in recs if r["url"] not in have]
if added:
    for r in added:
        meta.append({k: r[k] for k in ("slug", "year", "title", "date", "type", "L1", "L2", "summary", "url")})
    json.dump(meta, open(META_F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("meta.json: +%d -> %d" % (len(added), len(meta)))

# ---------- 2. bodies-N.json ----------
# 读取既有 bodies（对应原始 meta 顺序）
orig = []
i = 0
while True:
    p = os.path.join(REPO, "search", f"bodies-{i}.json")
    if not os.path.exists(p):
        break
    orig += json.load(open(p, encoding="utf-8"))
    i += 1
print("existing bodies:", len(orig))

# 按当前 meta.json 顺序重建：新增记录用 new_posts.json 的正文，其余顺序取原始 body
new_by_url = {r["url"]: r["body"].replace("\n", " ") for r in recs}
bodies, oi = [], 0
for m in meta:
    if m["url"] in new_by_url:
        bodies.append(f"首页 / {m['L1']} / {m['L2']} {m['title']} {m['date']} {m['type']} {m['year']}年 "
                      f"{new_by_url[m['url']]}")
    else:
        bodies.append(orig[oi])
        oi += 1
# 命中 new_by_url 的记录不消耗 orig，故判据是 oi + 命中数 == len(meta)；
# 幂等重跑时 orig 里已含这批正文（不会被消耗），用旧的 oi == len(orig) 会误判失败。
nnew = sum(1 for m in meta if m["url"] in new_by_url)
if len(bodies) == len(meta) and oi + nnew == len(meta):
    # 先写全部新分片（覆盖式），再只清理多余的高位分片。
    # 绝不能「先删全部再写」——本机安全钩子会异步吞掉刚删的文件，只留 bodies-9.json。
    nshard = (len(bodies) + CHUNK - 1) // CHUNK
    for i in range(nshard):
        with open(os.path.join(REPO, "search", f"bodies-{i}.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bodies[i * CHUNK:(i + 1) * CHUNK], fh, ensure_ascii=False, indent=0)
    for f in os.listdir(os.path.join(REPO, "search")):
        if f.startswith("bodies-") and f.endswith(".json"):
            try:
                if int(f[len("bodies-"):-len(".json")]) >= nshard:
                    os.remove(os.path.join(REPO, "search", f))
            except ValueError:
                pass
    print("bodies rewritten:", len(bodies), "shards:", nshard)
else:
    print("!! 对齐失败，跳过重写", len(bodies), len(meta), oi, len(orig))

# ---------- 3. sitemap-0.xml ----------
sm = os.path.join(REPO, "sitemap-0.xml")
s = open(sm, encoding="utf-8").read()
blocks = []
for r in added:
    loc = "https://swh-cn.github.io/QYSZ-zhihu/posts/2026/" + quote(r["slug"]) + "/"
    if loc not in s:
        blocks.append(f"<url><loc>{loc}</loc></url>")
if blocks:
    s = s.replace("</urlset>", "".join(blocks) + "</urlset>")
    open(sm, "w", encoding="utf-8", newline="\n").write(s)
print("sitemap: +%d" % len(blocks))

# ---------- 通用：卡片 HTML ----------
def esc(x): return html.escape(x or "", quote=False)

def card_full(r):
    return (f'<article class="post-card" data-astro-cid-sbmovh4h><h3 class="post-title" data-astro-cid-sbmovh4h>'
            f'<a href="{r["url"]}" data-astro-cid-sbmovh4h>{esc(r["title"])}</a></h3>'
            f'<div class="post-meta" data-astro-cid-sbmovh4h><time datetime="{r["date"]}" data-astro-cid-sbmovh4h>{r["date"]}</time>'
            f'<span class="post-type" data-astro-cid-sbmovh4h>{esc(r["type"])}</span>'
            f'<span class="post-cat" data-astro-cid-sbmovh4h>{esc(r["L1"])} &gt; {esc(r["L2"])}</span></div>'
            f'<p class="post-summary" data-astro-cid-sbmovh4h>{esc(r["summary"][:120])}</p></article>')

def card_short(r):
    return (f'<article class="post-card" data-astro-cid-sbmovh4h><h3 class="post-title" data-astro-cid-sbmovh4h>'
            f'<a href="{r["url"]}" data-astro-cid-sbmovh4h>{esc(r["title"])}</a></h3></article>')

def insert_after(container_pat, text, cards, path):
    """在容器开标签后插入卡片（幂等）"""
    m = re.search(container_pat, text)
    if not m:
        return None, text
    ins = "".join(c for c in cards if c.split('href="')[1].split('"')[0] not in text)
    if not ins:
        return 0, text
    return len(re.findall(r'<article class="post-card"', ins)), text[:m.end()] + ins + text[m.end():]

def bump_count(text, n):
    m = re.search(r'(<span class="page-count"[^>]*>)(\d+)( 篇</span>)', text)
    if m:
        return text[:m.start(2)] + str(int(m.group(2)) + n) + text[m.end(2):]
    return text

# ---------- 4. categories ----------
by_l2 = defaultdict(list)
for r in added:
    by_l2[(r["L1"], r["L2"])].append(r)
cat_done = 0
for (l1, l2), rs in by_l2.items():
    rs.sort(key=lambda r: r["date"], reverse=True)
    p = os.path.join(REPO, "categories", l1, l2, "index.html")
    if not os.path.exists(p):
        print("   !! missing cat page", l1, l2)
        continue
    t = open(p, encoding="utf-8").read()
    n, t2 = insert_after(r'<div class="post-list"[^>]*>', t, [card_full(r) for r in rs], p)
    if n:
        t2 = bump_count(t2, n)
        open(p, "w", encoding="utf-8", newline="\n").write(t2)
        cat_done += n
print("categories L2: +%d" % cat_done)

by_l1 = defaultdict(list)
for (l1, l2), rs in by_l2.items():
    by_l1[l1] += rs
l1_done = 0
for l1, rs in by_l1.items():
    rs.sort(key=lambda r: r["date"], reverse=True)
    p = os.path.join(REPO, "categories", l1, "index.html")
    if not os.path.exists(p):
        print("   !! missing L1 page", l1)
        continue
    t = open(p, encoding="utf-8").read()
    n, t2 = insert_after(r'<div class="post-list"[^>]*>', t, [card_full(r) for r in rs], p)
    if n:
        t2 = bump_count(t2, n)
        open(p, "w", encoding="utf-8", newline="\n").write(t2)
        l1_done += n
print("categories L1: +%d" % l1_done)

# ---------- 5. timeline ----------
# 后面 index.html 的最近文章列表也要用，先算好
new_rs = sorted(added, key=lambda r: r["date"], reverse=True)
# 时间线是「年 → 月 → 卡片」三层分组结构，不能靠往头部插卡片来更新：
# 那样会把新文章全塞进第一个月份组，且 month-count / 总数都不会变。
# 改为整体重建，见 fix_timeline.py（须在本脚本之后运行）。
import subprocess, sys
r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "fix_timeline.py")],
                   capture_output=True, text=True, encoding="utf-8")
print("timeline: 重建完成" if r.returncode == 0 else "timeline: 重建失败\n" + (r.stdout or "") + (r.stderr or ""))

# ---------- 6. index.html ----------
years = Counter()
for y in sorted(os.listdir(os.path.join(REPO, "posts"))):
    py = os.path.join(REPO, "posts", y)
    if os.path.isdir(py):
        years[y] = len([d for d in os.listdir(py) if os.path.isdir(os.path.join(py, d))])
total_posts = sum(years.values())

ip = os.path.join(REPO, "index.html")
x = open(ip, encoding="utf-8").read()
# 年份卡片：按磁盘实际数量写回（幂等）
for yy, cnt in years.items():
    x = re.sub(r'(<span class="cat-name"[^>]*>' + yy + r'</span><span class="cat-count"[^>]*>)\d+( 篇</span>)',
               lambda m, c=cnt: m.group(1) + str(c) + m.group(2), x, count=1)
# footer：按磁盘实际总数（幂等）
x = re.sub(r"共 \d+ 篇", f"共 {total_posts} 篇", x)
# 最新文章：插入新卡到 latest-list 开头，并裁剪到 20
def div_end(text, start):
    """返回与 start 处容器 div 配对的 </div> 起始下标"""
    depth, i = 1, start
    op = re.compile(r"<div\b"); cl = re.compile(r"</div>")
    while depth > 0:
        m1 = op.search(text, i); m2 = cl.search(text, i)
        if not m2:
            return len(text)
        if m1 and m1.start() < m2.start():
            depth += 1; i = m1.end()
        else:
            depth -= 1; i = m2.end()
            if depth == 0:
                return m2.start()
    return len(text)

allc = []
mm = re.search(r'<div class="latest-list"[^>]*>', x)
if mm:
    end = div_end(x, mm.end())
    inner = x[mm.end():end]
    existing_cards = re.findall(r'<article class="post-card".*?</article>', inner, re.S)
    new_cards = [card_full(r) for r in new_rs if r["url"] not in inner]
    allc = (new_cards + existing_cards)[:20]
    x = x[:mm.end()] + "".join(allc) + x[end:]
open(ip, "w", encoding="utf-8", newline="\n").write(x)
print("index.html: 2026 ->", re.search(r'>2026</span><span class="cat-count"[^>]*>(\d+) 篇', x).group(1),
      "| footer:", re.search(r"共 \d+ 篇", x).group(0), "| latest cards:", len(allc))

# ---------- 7. README.md 全量重生成 ----------
total = total_posts
allmeta = json.load(open(META_F, encoding="utf-8"))
l1c = Counter(m.get("L1") for m in allmeta)
# 只统计知乎文章（排除 blog 章节，meta 里含 266 章博客）
chars = sum(len(b) for m, b in zip(allmeta, bodies) if "/posts/" in m["url"])
wan = chars / 10000.0
recent = sorted(allmeta, key=lambda m: m.get("date", ""), reverse=True)[:10]
rd = []
rd.append("# 清一山长文集\n")
rd.append(f"> 「清一山长」知乎公开内容的静态归档站点 · 2021–2026 · 共 {total} 篇 · 另含博客专栏 266 章\n")
rd.append("本仓库是 **清一山长** 在平台发布的公开内容（回答 / 想法 / 文章）的离线归档，并额外收录其「博客全集」按原书目录整理的独立板块。站点使用 [Astro](https://astro.build) 构建为纯静态页面，并通过 GitHub Pages 部署。所有内容仅用于个人学习与资料整理，著作权归原作者所有。\n")
rd.append("## ✨ 站点特性\n")
rd.append("- **全文检索**：内置客户端搜索，输入关键词即可快速定位文章\n- **多维筛选**：支持按「年份 + 内容类型（回答 / 想法 / 文章）」组合过滤\n- **时间线**：首页以「按年份」时间线卡片呈现各年发文量，点击年份卡片直达对应年份的帖子列表；时间线页亦按年份分节\n- **标签聚合**：跨年份按主题标签检索\n- **分类浏览**：按六大主题分类（人生哲理 / 商业与科技 / 投资理财 / 新教育 / 武术格斗 / 社会与文化）聚合内容，入口 `/categories/`\n- **博客专栏**：独立「博客」板块，按原书目录「篇 → 章」组织，共 11 篇、266 章，入口 `/blog/`\n- **零后端**：纯静态 HTML，加载快，可离线阅读\n")
rd.append("## 📊 数据概况\n")
rd.append("| 指标     | 数值           |\n| ------ | ------------ |\n")
rd.append(f"| 收录时间范围 | 2021 – 2026  |\n| 知乎文章总数 | {total} 篇       |\n| 总字数    | 约 {wan:.0f} 万字     |\n| 内容类型   | 回答 · 想法 · 文章 |\n| 博客专栏   | 11 篇 / 266 章 |\n| 主题分类   | 6 类          |\n")
rd.append("### 各年发文量\n\n| 年份 | 篇数 |\n| --- | --- |\n")
for y in sorted(years):
    rd.append(f"| {y} | {years[y]} |\n")
rd.append("\n### 各主题分类篇数\n\n| 分类 | 篇数 |\n| --- | --- |\n")
for k, v in l1c.most_common():
    rd.append(f"| {k} | {v} |\n")
rd.append("\n## 🗂 目录结构\n\n```\nQYSZ-zhihu/\n├── index.html              # 首页（按年份时间线卡片，一览各年发文量）\n├── tags/                   # 标签筛选页\n├── timeline/               # 时间线浏览页\n├── search/                 # 全文搜索页\n├── docs/                   # Markdown 源（按年份归档，YYYY-MM-DD-标题前20字.md）\n├── categories/             # 分类浏览页（6 大主题）\n│   ├── 人生哲理/\n│   ├── 商业与科技/\n│   ├── 投资理财/\n│   ├── 新教育/\n│   ├── 武术格斗/\n│   └── 社会与文化/\n├── posts/\n│   ├── 2021/               # 按年份归档\n│   │   └── YYYY-MM-DD-标题.../\n│   ├── 2022/\n│   ├── ...\n│   └── 2026/\n├── blog/                   # 博客专栏（按「篇 → 章」组织，11 篇 / 266 章）\n│   ├── _articles.json      # 博客目录与元数据\n│   ├── index.html\n│   └── 第一篇-解读精英教育系列/ …\n├── assets/_shared/         # 共享静态资源\n├── styles/                 # 样式表\n├── _astro/                 # Astro 构建产物\n├── sitemap-0.xml           # 站点地图（SEO）\n├── sitemap-index.xml\n├── favicon.ico / favicon.svg\n└── .nojekyll               # 禁用 GitHub Pages 的 Jekyll 处理\n```\n")
rd.append("每篇知乎文章以 `posts/YYYY/YYYY-MM-DD-标题前若干字/` 的目录形式存放，便于按时间回溯；同时保留 `docs/YYYY/` 下的 Markdown 源。博客文章按「篇 → 章」两级目录组织，保留原书结构。\n")
rd.append("## 🆕 最近更新\n\n")
for m in recent:
    rd.append(f"- [{m['date']}] [{m['title']}](https://swh-cn.github.io{m['url']})（{m.get('L1','')} / {m.get('L2','')}）\n")
rd.append("\n## 🌐 在线访问\n\n站点已部署在 GitHub Pages：\n\n**<https://swh-cn.github.io/QYSZ-zhihu/>**\n\n> 仓库的 `gh-pages` 分支为部署分支。根目录下的 `.nojekyll` 文件用于跳过 Jekyll 处理，以保留 `_astro` 等带下划线的目录。\n")
rd.append("## 🛠 技术栈\n\n- **框架**：[Astro](https://astro.build)（SSG 静态站点生成）\n- **部署**：GitHub Pages（`gh-pages` 分支）\n- **检索 / 筛选 / 分类**：纯前端实现，无需后端服务\n")
rd.append("## 🔄 内容更新\n\n站点由知乎导出数据经「Markdown 归档流水线」（如 `markdown-archive-to-site` 类工具）生成并部署。如需补充或更新内容：\n\n1. 将新的知乎内容整理为带元信息的 Markdown（建议包含标题、发布日期、类型、来源链接）；\n2. 重新构建站点，生成静态产物；\n3. 推送至 `gh-pages` 分支完成部署。\n")
rd.append("## ⚠️ 免责声明\n\n- 本归档仅用于**个人学习与交流**，不构成任何商业用途。\n- 所有内容的著作权归原作者 **清一山长** 所有。\n- 如涉及侵权或作者要求删除，请联系维护者下架相关内容。\n- 知乎原文以平台发布为准；本归档可能存在抓取 / 排版差异，引用时请核对原文。\n")
rd.append("## 📄 许可\n\n文章内容的版权归原作者所有。站点代码与归档结构可自由复用；转载文章请保留原作者署名与来源链接。\n")
open(os.path.join(REPO, "README.md"), "w", encoding="utf-8", newline="\n").write("".join(rd))
print("README.md regenerated: total", total, "| 万字 %.0f" % wan, "| years", dict(years))

# ---------- 8. search/index.html（强制分块加载版，防止被内嵌单体索引覆盖） ----------
# 历史教训：内嵌全站索引的单体搜索页（~1.8MB）在国内网络下加载极慢，搜索会“转圈无结果”。
# 此步每次归档都用分块加载模板覆盖 search/index.html，保证该页始终是“小页面 + 分块拉取
# meta.json/bodies-N.json”的版本，不被任何“重新生成”或手改覆盖回内嵌版。
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_template.html")
DST = os.path.join(REPO, "search", "index.html")
if os.path.exists(TEMPLATE):
    shutil.copyfile(TEMPLATE, DST)
    print("search/index.html: 强制覆盖为分块加载版（防内嵌版回归）")
else:
    print("!! 未找到 search_template.html，跳过 search/index.html 覆盖")
