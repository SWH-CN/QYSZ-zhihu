#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 60 篇新文章的 posts/2026/<slug>/index.html（套用既有 post 模板）
同时产出 new_posts.json（meta 记录 + 正文）供后续索引同步使用。
slug 与 docs/2026/*.md 同名，保证 md 与 html 一一对应。
"""
import os, re, json, html
from urllib.parse import quote

REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
TPL = os.path.join(REPO, "posts", "2026", "2026-01-01-富二代教育-责任和荣誉是如何培养的", "index.html")
POSTS = os.path.join(REPO, "posts", "2026")
ARTS = r"E:/workbuddy/2026-10-09-18-07-09/scripts/articles.json"
CMAP = r"E:/workbuddy/2026-10-09-18-07-09/scripts/category_map.json"
DEDUP = r"E:/workbuddy/2026-10-09-18-07-09/scripts/dedup.json"
META = os.path.join(REPO, "search", "meta.json")
OUT = r"E:/workbuddy/2026-10-09-18-07-09/scripts/new_posts.json"

arts = {a["idx"]: a for a in json.load(open(ARTS, encoding="utf-8"))}
cmap = {c["idx"]: c for c in json.load(open(CMAP, encoding="utf-8")) if c.get("status") == "new"}
dd = json.load(open(DEDUP, encoding="utf-8"))
meta = json.load(open(META, encoding="utf-8"))
tpl = open(TPL, encoding="utf-8").read()

existing = set(os.listdir(POSTS))
total = 2118 + len(dd["new"])          # 现有总篇数 + 新增

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

def esc(s):
    return html.escape(s or "", quote=False)

def esc_attr(s):
    return html.escape(s or "", quote=True)

def plain_text(a):
    parts = []
    for seg in a.get("body", []):
        if seg.startswith("__IMG__"):
            continue
        for ln in seg.split("\n"):
            if ln.strip():
                parts.append(ln.strip())
    return "\n".join(parts)

# 同 L2 的既有文章（用于“相关文章”）
by_l2 = {}
for m in meta:
    by_l2.setdefault((m.get("L1"), m.get("L2")), []).append(m)

def related(l1, l2, k=5):
    cands = list(by_l2.get((l1, l2), []))
    if len(cands) < k:
        for (a1, a2), v in by_l2.items():
            if a1 == l1 and a2 != l2:
                cands += v
    cands.sort(key=lambda m: m.get("date", ""), reverse=True)
    out, seen = [], set()
    for m in cands:
        if m["url"] in seen:
            continue
        seen.add(m["url"])
        out.append(m)
        if len(out) >= k:
            break
    return out

def build_html(a, l1, l2, total):
    title = a["title"]
    date = a["date"]
    summary = plain_text(a)[:160].replace("\n", " ")
    # 正文
    content = []
    for seg in a.get("body", []):
        if seg.startswith("__IMG__"):
            h = seg[7:]
            content.append(f'<p><img src="/QYSZ-zhihu/assets/_shared/{h}.webp" alt="" loading="lazy" class="post-img" /></p>')
        else:
            for ln in seg.split("\n"):
                if ln.strip():
                    content.append(f"<p>{esc(ln.strip())}</p>")
    content_s = "".join(content)
    nav = ('<nav class="breadcrumb" data-astro-cid-t2castq5><a href="/QYSZ-zhihu/" data-astro-cid-t2castq5>首页</a>'
           '<span class="sep" data-astro-cid-t2castq5>/</span>'
           f'<a href="/QYSZ-zhihu/categories/{quote(l1)}/" data-astro-cid-t2castq5>{esc(l1)}</a>'
           '<span class="sep" data-astro-cid-t2castq5>/</span>'
           f'<a href="/QYSZ-zhihu/categories/{quote(l1)}/{quote(l2)}/" data-astro-cid-t2castq5>{esc(l2)}</a></nav>')
    pmeta = (f'<div class="post-meta" data-astro-cid-t2castq5><time datetime="{esc_attr(date)}" data-astro-cid-t2castq5>{esc(date)}</time>'
             f'<span class="post-type" data-astro-cid-t2castq5>{esc(a.get("type",""))}</span>'
             f'<span class="post-year" data-astro-cid-t2castq5>{date[:4]}年</span></div>')
    cards = "".join(
        f'<article class="post-card" data-astro-cid-sbmovh4h><h3 class="post-title" data-astro-cid-sbmovh4h>'
        f'<a href="{esc_attr(m["url"])}" data-astro-cid-sbmovh4h>{esc(m["title"])}</a></h3></article>'
        for m in related(l1, l2))
    aside = (f'<aside class="related-section" data-astro-cid-t2castq5><h2 class="related-title" data-astro-cid-t2castq5>相关文章</h2>'
             f'<div class="related-list" data-astro-cid-t2castq5>{cards}</div></aside>')

    h = tpl
    h = re.sub(r'(<meta name="description" content=")[^"]*(")',
               lambda m: m.group(1) + esc_attr(summary) + m.group(2), h, count=1)
    h = re.sub(r"<title>[^<]*</title>", f"<title>{esc(title)} — 清一山长文集</title>", h, count=1)
    h = re.sub(r'<nav class="breadcrumb".*?</nav>', nav, h, count=1, flags=re.S)
    h = re.sub(r'(<h1 class="post-title"[^>]*>)[^<]*(</h1>)',
               lambda m: m.group(1) + esc(title) + m.group(2), h, count=1)
    h = re.sub(r'<div class="post-meta".*?</div>', pmeta, h, count=1, flags=re.S)
    h = re.sub(r'(<div class="post-content"[^>]*>).*?(</div></article>)',
               lambda m: m.group(1) + content_s + m.group(2), h, count=1, flags=re.S)
    h = re.sub(r'<aside class="related-section".*?</aside>', aside, h, count=1, flags=re.S)
    h = re.sub(r"共 \d+ 篇", f"共 {total} 篇", h)
    return h

records = []
written = 0
for n in dd["new"]:
    idx = n["idx"]
    a = arts[idx]
    c = cmap[idx]
    l1, l2 = c["L1"], c["L2"]
    slug = f"{a['date']}-{sanitize(a['title'])[:20]}" or f"post{idx:02d}"
    base = slug
    i = 2
    while base in existing:
        base = f"{slug}-{i}"
        i += 1
    existing.add(base)
    d = os.path.join(POSTS, base)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n").write(build_html(a, l1, l2, total))
    written += 1
    records.append({
        "slug": base, "year": "2026", "title": a["title"], "date": a["date"], "type": a.get("type", ""),
        "L1": l1, "L2": l2, "summary": plain_text(a)[:160].replace("\n", " "),
        "url": f"/QYSZ-zhihu/posts/2026/{base}/", "body": plain_text(a), "idx": idx,
    })

json.dump(records, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("posts written:", written, "->", POSTS)
print("total in footer:", total)
for r in records[:6]:
    print("  ", r["slug"], "|", r["L1"], "/", r["L2"])
