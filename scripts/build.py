#!/usr/bin/env python3
"""data/videos.json + data/overrides.json → site/ 정적 사이트 생성. 표준 라이브러리만 사용."""
import json
import shutil
from datetime import datetime
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
CATEGORY_ORDER = ["OUTER", "TOP", "BOTTOM", "SHOES", "BAG", "ACC", "ETC"]


# ---------------------------------------------------------------- data
def load():
    videos = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8"))
    ov_path = ROOT / "data" / "overrides.json"
    overrides = json.loads(ov_path.read_text(encoding="utf-8")) if ov_path.exists() else {}
    out = []
    for v in videos:
        o = overrides.get(v["id"], {})
        if o.get("hidden"):
            continue
        v = {**v, **{k: val for k, val in o.items() if k != "looks"}, "_override_looks": o.get("looks")}
        v.setdefault("products", [])
        v["model_stats"] = v.get("model_stats") or C["default_model_stats"]
        out.append(v)
    return out


def build_looks(videos):
    looks = []
    for v in videos:
        by_url = {p["url"]: p for p in v["products"]}
        if v.get("_override_looks"):
            for i, lk in enumerate(v["_override_looks"]):
                looks.append({"id": f"{v['id']}-{i+1}", "video": v, "t": lk.get("t", 0), "label": lk.get("label", f"LOOK {i+1}"), "products": lk.get("products", []), "image": lk.get("image")})
        elif v["type"] == "video" and v.get("looks"):
            for i, lk in enumerate(v["looks"]):
                prods = [by_url[lk["product_url"]]] if lk.get("product_url") in by_url else []
                looks.append({"id": f"{v['id']}-{i+1}", "video": v, "t": lk["t"], "label": lk["label"], "products": prods})
        else:
            looks.append({"id": v["id"], "video": v, "t": 0, "label": v["title"], "products": v["products"]})
    return looks


# ---------------------------------------------------------------- helpers
def thumb(vid, frame=None):
    # frame 1/2/3 = 유튜브 자동 생성 프레임(영상 25/50/75% 지점)
    return f"https://i.ytimg.com/vi/{vid}/{'hq' + str(frame) if frame else 'hqdefault'}.jpg"


def look_img(lk):
    if lk.get("image"):
        return lk["image"]
    v = lk["video"]
    if v["type"] != "video" or not v.get("chapters"):
        return thumb(v["id"])
    dur = max(c["t"] for c in v["chapters"]) + 30
    frac = lk["t"] / dur
    return thumb(v["id"], 1 if frac < 0.375 else 2 if frac < 0.625 else 3)


def yt_url(v, t=0):
    base = f"https://www.youtube.com/shorts/{v['id']}" if v["type"] == "shorts" else f"https://www.youtube.com/watch?v={v['id']}"
    return base + (f"&t={t}s" if t and v["type"] != "shorts" else "")


def fmt_date(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y.%m.%d")


def fmt_t(t):
    return f"{t // 60:02d}:{t % 60:02d}"


def ext_link(url, inner, cls=""):
    return f'<a href="{e(url)}" target="_blank" rel="noopener sponsored" class="{cls}">{inner}</a>'


def group_products(products):
    groups = {}
    for p in products:
        groups.setdefault(p.get("category") or "ETC", []).append(p)
    return [(c, groups[c]) for c in CATEGORY_ORDER if c in groups]


def product_table(products, curation_url=None):
    if not products:
        if curation_url:
            return f'''<div class="empty">착장 제품은 무신사 큐레이션에서 순서대로 확인할 수 있어요.
              {ext_link(curation_url, "무신사 큐레이션에서 착장 보기 ↗", "btn")}</div>'''
        return '<div class="empty">착장 정보 준비 중이에요.</div>'
    rows = []
    for cat, items in group_products(products):
        lis = "".join(f'<li>{ext_link(p["url"], e(p["name"]) + "<span class=arrow>↗</span>")}</li>' for p in items)
        rows.append(f'<div class="cat-row"><h4>{cat}</h4><ul>{lis}</ul></div>')
    return '<div class="ptable">' + "".join(rows) + "</div>"


def page(title, body, root, desc=None, og_image=None):
    desc = desc or C["hero_sub"]
    og = f'<meta property="og:image" content="{e(og_image)}">' if og_image else ""
    nav = f'''
<header class="top">
  <a class="logo" href="{root}index.html">{e(C["site_name"])}</a>
  <nav>
    <a href="{root}looks.html">LOOK</a><a href="{root}shorts.html">SHORTS</a><a href="{root}videos.html">VIDEO</a><a href="{root}products.html">ITEMS</a>
  </nav>
</header>'''
    foot = f'''
<footer>
  <div class="logo">{e(C["site_name"])}</div>
  <div class="links">{ext_link(C["youtube_url"], "YouTube")}{ext_link(C["instagram_url"], "Instagram")}{ext_link(C["curator_shop_url"], "무신사 큐레이터샵")}</div>
  <p class="disc">{e(C["disclosure"])}</p>
</footer>'''
    return f'''<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">{og}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="{root}assets/style.css">
</head><body>{nav}<main>{body}</main>{foot}</body></html>'''


def look_card(lk, root):
    v = lk["video"]
    badge = "SHORTS" if v["type"] == "shorts" else lk["label"]
    return f'''<a class="card look" href="{root}look/{lk["id"]}.html">
  <div class="img {"v" if v["type"] == "shorts" else "h"}"><img loading="lazy" src="{e(look_img(lk))}" alt=""><span class="badge">{e(badge)}</span></div>
  <div class="meta"><b>{e(v["title"] if v["type"] == "shorts" else lk["label"])}</b><span>{f"{len(lk['products'])} items" if lk["products"] else ("무신사 큐레이션" if v.get("curation_url") else "착장정보 준비 중")}</span></div>
</a>'''


def video_card(v, root):
    cls = "v" if v["type"] == "shorts" else "h"
    return f'''<a class="card" href="{root}v/{v["id"]}.html">
  <div class="img {cls}"><img loading="lazy" src="{thumb(v["id"])}" alt=""></div>
  <div class="meta"><b>{e(v["title"])}</b><span>{fmt_date(v["published"])}</span></div>
</a>'''


def section(eyebrow, title, inner, more_href=None, root=""):
    more = f'<a class="more" href="{root}{more_href}">더보기 →</a>' if more_href else ""
    return f'<section><div class="sec-head"><p>{e(eyebrow)}</p><h2>{e(title)}</h2>{more}</div>{inner}</section>'


def embed(v, t=0):
    start = f"?start={t}" if t else ""
    ratio = "v" if v["type"] == "shorts" else "h"
    return f'<div class="embed {ratio}"><iframe src="https://www.youtube-nocookie.com/embed/{v["id"]}{start}" title="{e(v["title"])}" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>'


# ---------------------------------------------------------------- pages
def write(path, html):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


def build():
    videos = load()
    looks = build_looks(videos)
    shorts = [v for v in videos if v["type"] == "shorts"]
    longs = [v for v in videos if v["type"] == "video"]

    all_products, seen = [], set()
    for v in videos:
        for p in v["products"]:
            if p["url"] not in seen:
                seen.add(p["url"])
                all_products.append({**p, "video": v})

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")

    # index
    hero_title = "<br>".join(e(x) for x in C["hero_title"].split("\n"))
    latest_items = "".join(
        f'<li><span class="n">{i+1}</span>{ext_link(p["url"], "<em>" + p["category"] + "</em>" + e(p["name"]))}</li>'
        for i, p in enumerate(all_products[:8]))
    body = f'''
<div class="hero" style="--bg:url('{thumb(videos[0]["id"]) if videos else ""}')">
  <h1>{hero_title}</h1><p>{e(C["hero_sub"])}</p>
  <a class="btn light" href="looks.html">착용 제품과 구매 링크 보기</a>
</div>
{section("영상 속 코디 모아보기", "LOOK", '<div class="grid g6">' + "".join(look_card(l, "") for l in looks[:12]) + "</div>", "looks.html")}
{section("최근 영상 착용 제품", "NEW ITEMS", f'<ol class="rank">{latest_items}</ol>', "products.html") if all_products else ""}
{section("숏폼 영상 코디 정보 보기", "SHORTS", '<div class="grid g6">' + "".join(video_card(v, "") for v in shorts[:12]) + "</div>", "shorts.html")}
{section("롱폼 영상 코디 정보 보기", "VIDEO", '<div class="grid g3">' + "".join(video_card(v, "") for v in longs[:6]) + "</div>", "videos.html")}
<section class="cta">{ext_link(C["curator_shop_url"], "도댕패션 무신사 큐레이터샵 전체 보기 ↗", "btn")}</section>
'''
    write("index.html", page(C["site_title"], body, "", og_image=thumb(videos[0]["id"]) if videos else None))

    # list pages
    write("looks.html", page(f"LOOK | {C['site_title']}", section("영상 속 코디 모아보기", "LOOK", '<div class="grid g6">' + "".join(look_card(l, "") for l in looks) + "</div>"), ""))
    write("shorts.html", page(f"SHORTS | {C['site_title']}", section("숏폼 영상 코디 정보", "SHORTS", '<div class="grid g6">' + "".join(video_card(v, "") for v in shorts) + "</div>"), ""))
    write("videos.html", page(f"VIDEO | {C['site_title']}", section("롱폼 영상 코디 정보", "VIDEO", '<div class="grid g3">' + "".join(video_card(v, "") for v in longs) + "</div>"), ""))

    chips = "".join(f'<button data-c="{c}">{c}</button>' for c in CATEGORY_ORDER if any(p["category"] == c for p in all_products))
    items = "".join(
        f'<li data-c="{p["category"]}" data-q="{e(p["name"].lower())}">{ext_link(p["url"], "<em>" + p["category"] + "</em><b>" + e(p["name"]) + "</b>")}'
        f'<a class="from" href="v/{p["video"]["id"]}.html">{e(p["video"]["title"])}</a></li>'
        for p in all_products)
    body = section("영상에 나온 모든 제품", "ITEMS", f'''
<div class="filters"><input id="q" type="search" placeholder="제품명 검색"><div class="chips"><button data-c="" class="on">ALL</button>{chips}</div></div>
<ul class="items" id="items">{items}</ul>
<script>
(()=>{{const q=document.getElementById('q'),lis=[...document.querySelectorAll('#items li')];let c='';
const f=()=>{{const s=q.value.trim().toLowerCase();lis.forEach(li=>li.hidden=!((!c||li.dataset.c===c)&&(!s||li.dataset.q.includes(s))))}};
q.oninput=f;document.querySelectorAll('.chips button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.chips button').forEach(x=>x.classList.remove('on'));b.classList.add('on');c=b.dataset.c;f()}});}})();
</script>''')
    write("products.html", page(f"ITEMS | {C['site_title']}", body, ""))

    # video detail
    for i, v in enumerate(videos):
        vlooks = [l for l in looks if l["video"]["id"] == v["id"]]
        look_list = ""
        if v["type"] == "video" and vlooks:
            look_list = section("사진을 클릭하면 코디별 착장 제품을 확인할 수 있어요", "코디 모아보기",
                                '<div class="grid g4">' + "".join(
                                    f'<a class="card look" href="../look/{l["id"]}.html"><div class="img h"><img loading="lazy" src="{e(look_img(l))}" alt=""><span class="badge">{fmt_t(l["t"])}</span></div><div class="meta"><b>{e(l["label"])}</b><span>{e(l["products"][0]["name"]) if l["products"] else ""}</span></div></a>'
                                    for l in vlooks) + "</div>")
        cur_btn = ext_link(v["curation_url"], "무신사 큐레이션 ↗", "btn ghost") if v.get("curation_url") else ""
        prev_v = videos[i - 1] if i > 0 else None
        next_v = videos[i + 1] if i + 1 < len(videos) else None
        pager = '<div class="pager">' + (f'<a href="{prev_v["id"]}.html">← 이전 영상</a>' if prev_v else "<span></span>") + (f'<a href="{next_v["id"]}.html">다음 영상 →</a>' if next_v else "") + "</div>"
        body = f'''
<div class="detail">
  {embed(v)}
  <div class="info">
    <span class="tag">{"SHORTS" if v["type"] == "shorts" else "VIDEO"}</span>
    <h1>{e(v["title"])}</h1>
    <p class="sub">{fmt_date(v["published"])} · 착용 제품 정보 [{e(v["model_stats"])}]</p>
    <div class="actions">{ext_link(yt_url(v), "▶ 영상 보러가기", "btn")}{cur_btn}</div>
    <p class="hint">제품명을 누르면 구매 페이지로 이동합니다.</p>
    {product_table(v["products"], v.get("curation_url"))}
  </div>
</div>
{look_list}{pager}'''
        write(f"v/{v['id']}.html", page(f"{v['title']} | {C['site_title']}", body, "../", desc=f"{v['title']} 착장 정보 · 무신사 구매 링크", og_image=thumb(v["id"])))

    # look detail
    for i, l in enumerate(looks):
        v = l["video"]
        prev_l = looks[i - 1] if i > 0 else None
        next_l = looks[i + 1] if i + 1 < len(looks) else None
        pager = '<div class="pager">' + (f'<a href="{prev_l["id"]}.html">← 이전 코디</a>' if prev_l else "<span></span>") + (f'<a href="{next_l["id"]}.html">다음 코디 →</a>' if next_l else "") + "</div>"
        title = l["label"] if v["type"] == "video" else v["title"]
        body = f'''
<div class="detail">
  {embed(v, l["t"])}
  <div class="info">
    <span class="tag">{e(l["label"]) if v["type"] == "video" else "SHORTS"}</span>
    <h1>{e(title)}</h1>
    <p class="sub">착용 제품 정보 [{e(v["model_stats"])}]</p>
    <p class="hint">제품명을 누르면 구매 페이지로 이동합니다.<br>{e(C["disclosure"])}</p>
    {product_table(l["products"], v.get("curation_url"))}
    <div class="actions">{ext_link(yt_url(v, l["t"]), "▶ 이 코디 영상에서 보기", "btn")}<a class="btn ghost" href="../v/{v["id"]}.html">영상 전체 착장 보기</a></div>
  </div>
</div>{pager}'''
        write(f"look/{l['id']}.html", page(f"{title} | {C['site_title']}", body, "../", og_image=thumb(v["id"])))

    # machine-readable feed + 404
    (OUT / "videos.json").write_text(json.dumps([{k: v[k] for k in ("id", "title", "type", "published", "products", "curation_url")} for v in videos], ensure_ascii=False), encoding="utf-8")
    write("404.html", page("페이지를 찾을 수 없어요", '<section class="cta"><h2>페이지를 찾을 수 없어요</h2><a class="btn" href="' + (C["base_url"] or "/") + '">홈으로</a></section>', ""))
    (OUT / ".nojekyll").write_text("")
    print(f"[build] videos={len(videos)} looks={len(looks)} products={len(all_products)} → {OUT}")


if __name__ == "__main__":
    build()
