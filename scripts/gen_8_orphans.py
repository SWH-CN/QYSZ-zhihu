#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建 8 篇「孤儿想法帖」的 post 页。

背景：这 8 篇想法帖此前从未生成过自己的 post 页——它们的 meta 记录
被错误指向了同日另一篇文章的 slug（slug 冲突），而全站 98 处卡片
仍指向它们本应拥有的独立 slug，导致死链。

数据来源：清一山长知乎 2026（原创）-目录补齐.docx（想法原帖原文）
作者：已从该 docx 提取，见 ../2026-10-10-12-41-40/found8.json

策略：
- slug 沿用现有卡片 href => 98 处引用原地生效，无需改动任何 HTML
- title 沿用 meta/卡片现有标题 => 卡片、时间线、页面三者显示一致
- body  用 docx 中的想法原帖原文（严格逐字）
- summary 沿用既有口径「（无正文内容，仅含标题与来源链接）」，
  与全站同类想法帖保持一致（不擅自改变口径）
"""
import os, re, json, html
from urllib.parse import quote

REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
TPL = os.path.join(REPO, "posts", "2026", "2026-01-01-富二代教育-责任和荣誉是如何培养的", "index.html")
POSTS = os.path.join(REPO, "posts", "2026")
META = os.path.join(REPO, "search", "meta.json")
OUT = r"E:/workbuddy/2026-10-10-12-41-40/new8.json"
TOTAL = 2180  # index.html 现有总数 2172 + 本次新增 8

# (slug, 站点标题, docx原帖原文, 日期, L1, L2, 知乎来源)
DATA = [
    ("2026-05-23-见识一下粉丝的消费方式", "见识一下粉丝的消费方式", "见识一下粉丝消费方式",
     "2026-05-23", "商业与科技", "财富与阶层", "https://www.zhihu.com/pins/2041651774952585213"),
    ("2026-01-17-英语这门语言确实很弱智", "英语这门语言确实很弱智", "英语的确很弱智",
     "2026-01-17", "新教育", "英语突破与升学", "https://www.zhihu.com/pins/1995997734340166099"),
    ("2026-06-13-中国人真的做得出", "中国人真的做得出", "中国人真的做的出",
     "2026-06-13", "社会与文化", "社会现象评论", "https://www.zhihu.com/pins/2049257851667984519"),
    ("2026-03-20-体制内工作的要点，真厉害", "体制内工作的要点，真厉害", "这个体制内工作的要点、真厉害",
     "2026-03-20", "社会与文化", "文明与体制", "https://www.zhihu.com/pins/2018427724214063296"),
    ("2026-02-15-通，比补更有价值", "通，比补更有价值", "通比补更有价值",
     "2026-02-15", "社会与文化", "杂感随笔", "https://www.zhihu.com/pins/2006535811701707742"),
    ("2026-02-01-美国人，实在可怕", "美国人，实在可怕", "可怕的美国人",
     "2026-02-01", "社会与文化", "社会现象评论", "https://www.zhihu.com/pins/2001425559880761405"),
    ("2026-01-21-千万远离货车", "千万远离货车", "远离货车",
     "2026-01-21", "社会与文化", "杂感随笔", "https://www.zhihu.com/pins/1997464335988061260"),
    ("2026-01-05-有钱人家养出来的活宝", "有钱人家养出来的活宝", "这就是有钱人家养出来的活宝",
     "2026-01-05", "社会与文化", "杂感随笔", "https://www.zhihu.com/pins/1991514454995772865"),
]

PLACEHOLDER = "（无正文内容，仅含标题与来源链接）"


def esc(s):
    return html.escape(s or "", quote=False)


def esc_attr(s):
    return html.escape(s or "", quote=True)


def main():
    tpl = open(TPL, encoding="utf-8").read()
    meta = json.load(open(META, encoding="utf-8"))
    by_title = {m["title"]: m for m in meta}

    # 同 L2 的既有文章（用于「相关文章」）
    by_l2 = {}
    for m in meta:
        by_l2.setdefault((m.get("L1"), m.get("L2")), []).append(m)

    def related(l1, l2, self_url, k=5):
        cands = list(by_l2.get((l1, l2), []))
        if len(cands) < k:
            for (a1, a2), v in by_l2.items():
                if a1 == l1 and a2 != l2:
                    cands += v
        cands.sort(key=lambda m: m.get("date", ""), reverse=True)
        out, seen = [], {self_url}
        for m in cands:
            if m["url"] in seen:
                continue
            seen.add(m["url"])
            out.append(m)
            if len(out) >= k:
                break
        return out

    records = []
    for slug, title, body, date, l1, l2, src in DATA:
        url = f"/QYSZ-zhihu/posts/2026/{slug}/"
        # summary 沿用既有口径
        prev = by_title.get(title)
        summary = prev.get("summary") if prev else None
        if not summary or summary.startswith("（无正文"):
            summary = PLACEHOLDER
        ptype = (prev or {}).get("type", "想法")

        content_s = f"<p>{esc(body)}</p>"

        nav = ('<nav class="breadcrumb" data-astro-cid-t2castq5><a href="/QYSZ-zhihu/" data-astro-cid-t2castq5>首页</a>'
               '<span class="sep" data-astro-cid-t2castq5>/</span>'
               f'<a href="/QYSZ-zhihu/categories/{quote(l1)}/" data-astro-cid-t2castq5>{esc(l1)}</a>'
               '<span class="sep" data-astro-cid-t2castq5>/</span>'
               f'<a href="/QYSZ-zhihu/categories/{quote(l1)}/{quote(l2)}/" data-astro-cid-t2castq5>{esc(l2)}</a></nav>')
        pmeta = (f'<div class="post-meta" data-astro-cid-t2castq5><time datetime="{esc_attr(date)}" data-astro-cid-t2castq5>{esc(date)}</time>'
                 f'<span class="post-type" data-astro-cid-t2castq5>{esc(ptype)}</span>'
                 f'<span class="post-year" data-astro-cid-t2castq5>{date[:4]}年</span></div>')
        cards = "".join(
            f'<article class="post-card" data-astro-cid-sbmovh4h><h3 class="post-title" data-astro-cid-sbmovh4h>'
            f'<a href="{esc_attr(m["url"])}" data-astro-cid-sbmovh4h>{esc(m["title"])}</a></h3></article>'
            for m in related(l1, l2, url))
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
        h = re.sub(r"共 \d+ 篇", f"共 {TOTAL} 篇", h)

        d = os.path.join(POSTS, slug)
        existed = os.path.exists(os.path.join(d, "index.html"))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n").write(h)
        print(("  [覆盖] " if existed else "  [新建] ") + slug)

        records.append({
            "slug": slug, "year": "2026", "title": title, "date": date, "type": ptype,
            "L1": l1, "L2": l2, "summary": summary,
            "url": url, "body": body, "source": src,
        })

    json.dump(records, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("records ->", OUT, len(records))


if __name__ == "__main__":
    main()
