#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从《清一山长知乎 2026（原创）-新增61篇.docx》抽取 61 篇文章 -> articles.json
日期严格取【目录(TOC)标题】；不解析正文回退。
输出：articles.json（含 date/title/type/shoulu/body/images/zhihu），并把图片转 webp 入库 assets/_shared/<md5>.webp
"""
import os, re, json, hashlib, io
from collections import Counter
from docx import Document
from docx.oxml.ns import qn
from PIL import Image

DOCX = r"E:/workbuddy/原创文整理/清一山长知乎 2026（原创）-新增61篇.docx"
REPO = r"E:/workbuddy/2026-10-08-21-02-05/qysz"
ASSETS = os.path.join(REPO, "assets", "_shared")
OUT_JSON = r"E:/workbuddy/2026-10-09-18-07-09/scripts/articles.json"
EXTRACT_IMAGES = True

os.makedirs(ASSETS, exist_ok=True)
d = Document(DOCX)
paras = d.paragraphs

# ---------------- 解析目录(TOC)：每条目恰为一个段落（标题内可含换行） ----------------
toc = []
started = False
for p in paras:
    t = p.text
    if not started:
        if "目录" in "".join(t.split()):
            started = True
            continue
        continue
    if p.style.name == "Heading 2":
        break
    if not t.strip():
        continue
    m = re.match(r"^\s*(\d+)\.\s*\[([^\]]+)\]\s*(.*)", t, re.S)
    if m:
        title = m.group(3).strip()
        pm = re.search(r"(\d+)\s*$", title)
        page = pm.group(1) if pm else ""
        if pm:
            title = title[: pm.start()].strip()
        title = title.replace("\r", "").replace("\n", "").strip()
        toc.append({"idx": int(m.group(1)), "date": m.group(2).strip(), "title": title, "page": page})
    else:
        print("UNMATCHED TOC LINE:", repr(t[:50]))

def norm_date(s):
    if not s:
        return ""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s.strip()

for e in toc:
    e["date"] = norm_date(e["date"])

# ---------------- 按 H2 切分正文 + 图片 + 类型/收录于 ----------------
h2pos = [i for i, p in enumerate(paras) if p.style.name == "Heading 2"]
arts = []
for ai in range(len(h2pos)):
    s = h2pos[ai]
    e = h2pos[ai + 1] if ai + 1 < len(h2pos) else len(paras)
    art = {
        "idx": ai + 1,
        "h2_title": paras[s].text,
        "body": [],          # 文本段 或 __IMG__<hash> 标记
        "images": [],        # hash 列表
        "type": "想法",
        "shoulu": "",
        "zhihu": [],
    }
    for p in paras[s + 1:e]:
        txt = p.text
        is_meta = False
        if txt.strip().startswith("收录于"):
            parts = re.split(r"[·・:：]", txt, 1)
            art["shoulu"] = parts[-1].strip() if len(parts) > 1 else txt.strip()
            is_meta = True
        if "赞同了该文章" in txt:
            art["type"] = "文章"
            is_meta = True
        if re.search(r"发布于\d{4}", txt):
            is_meta = True
        if re.search(r"\d+\s*赞同\s*·\s*\d+\s*评论\s*回答", txt) or (
            txt.strip().endswith("回答") and "赞同" in txt
        ):
            if "赞同了该文章" not in txt:
                art["type"] = "回答"
            is_meta = True
        if txt.strip() and all(c in "—-—-" for c in txt.strip()):
            is_meta = True
        # 图片
        imgs = []
        if EXTRACT_IMAGES:
            for r in p._p.findall(qn("w:r")):
                for blip in r.findall(".//" + qn("a:blip")):
                    emb = blip.get(qn("r:embed"))
                    if emb and emb in d.part.rels:
                        try:
                            ip = d.part.rels[emb].target_part
                            data = ip.blob
                            h = hashlib.md5(data).hexdigest()
                            ext = os.path.splitext(ip.partname)[1].lower().lstrip(".")
                            imgs.append((h, ext, data))
                        except Exception:
                            pass
        if is_meta:
            continue
        if txt.strip():
            art["body"].append(txt)
        for (h, ext, data) in imgs:
            outp = os.path.join(ASSETS, h + ".webp")
            if not os.path.exists(outp):
                try:
                    Image.open(io.BytesIO(data)).save(outp, "WEBP")
                except Exception:
                    with open(os.path.join(ASSETS, h + "." + ext), "wb") as f:
                        f.write(data)
            art["images"].append(h)
            art["body"].append("__IMG__" + h)
    arts.append(art)

# ---------------- 对齐 TOC 的 date/title ----------------
assert len(arts) == len(toc), f"arts {len(arts)} != toc {len(toc)}"
for a, e in zip(arts, toc):
    a["title"] = e["title"] if e["title"] else a["h2_title"]
    a["date"] = e["date"]
    a["toc_title"] = e["title"]
    if not a["date"]:
        a["date_missing"] = True

# zhihu 来源 URL
for a in arts:
    for seg in a["body"]:
        for u in re.findall(r"https?://[^\s）】]+", seg):
            if "zhihu" in u:
                a["zhihu"].append(u)
    a["zhihu"] = list(dict.fromkeys(a["zhihu"]))

os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
json.dump(arts, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("articles:", len(arts))
print("type counts:", dict(Counter(a["type"] for a in arts)))
print("missing date:", [a["idx"] for a in arts if not a["date"]])
print("with images:", sum(1 for a in arts if a["images"]))
print("with zhihu:", sum(1 for a in arts if a["zhihu"]))
print("shoulu values:", sorted(set(a["shoulu"] for a in arts if a["shoulu"])))
print("webp written:", len(os.listdir(ASSETS)))
