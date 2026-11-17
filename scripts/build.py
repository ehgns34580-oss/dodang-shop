#!/usr/bin/env python3
"""data/*.json → site/ 정적 사이트 생성 (표준 라이브러리만).
모든 제품 클릭은 도댕 무신사 큐레이터샵(큐레이션)으로 연결. 큐레이션이 없을 때만 개별 상품 링크."""
import json
import shutil
import sys
from datetime import datetime
from html import escape as e
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve import CAT_ORDER, Catalog, resolve_video  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SHOP = C["curator_shop_url"]


# ---------------------------------------------------------------- data
def load():
    videos = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8"))
    cur_path = ROOT / "data" / "curations.json"
    cat = Catalog(json.loads(cur_path.read_text(encoding="utf-8")) if cur_path.exists() else {}, SHOP)
    ov_path = ROOT / "data" / "overrides.json"
    overrides = json.loads(ov_path.read_text(encoding="utf-8")) if ov_path.exists() else {}
    out = []
    for v in videos:
        if not v.get("title") or not v.get("published"):
            continue
        o = overrides.get(v["id"], {})
        if o.get("hidden"):
            continue
        resolve_video(v, cat, o)
        v["model_stats"] = v.get("model_stats") or C["default_model_stats"]
        out.append(v)
    out.sort(key=lambda v: v["published"], reverse=True)
    return out, cat


# ---------------------------------------------------------------- helpers
def thumb(vid):
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def img(url, w=390):
    if not url:
        return ""
    return url.split("?")[0] + f"?w={w}" if "msscdn.net" in url else url


def frame_style(v, t):
    """유튜브 스토리보드(장면 미리보기)에서 t초 장면을 잘라 CSS 배경으로"""
    sb = v.get("storyboard")
    if not sb:
        return f"background-image:url('{thumb(v['id'])}');background-size:cover;background-position:center"
    per = sb["cols"] * sb["rows"]
    idx = max(0, min(sb["count"] - 1, int(t * 1000 // sb["interval"])))
    sheet, pos = divmod(idx, per)
    col, row = pos % sb["cols"], pos // sb["cols"]
    url = sb["url"].replace("$M", str(sheet))
    x = col / (sb["cols"] - 1) * 100 if sb["cols"] > 1 else 0
    y = row / (sb["rows"] - 1) * 100 if sb["rows"] > 1 else 0
    return f"background-image:url('{url}');background-size:{sb['cols'] * 100}% {sb['rows'] * 100}%;background-position:{x:.2f}% {y:.2f}%"


def yt_url(v, t=0):
    if v["type"] == "shorts":
        return f"https://www.youtube.com/shorts/{v['id']}"
    return f"https://www.youtube.com/watch?v={v['id']}" + (f"&t={t}s" if t else "")


def fmt_date(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y.%m.%d")


def fmt_t(t):
    return f"{t // 60:02d}:{t % 60:02d}"


def won(n):
    return f"{n:,}원" if n else ""


def ext(url, inner, cls="", extra=""):
    return f'<a href="{e(url)}" target="_blank" rel="noopener sponsored" class="{cls}" {extra}>{inner}</a>'


def primary_link(v):
    return v.get("curation_link") or SHOP


def product_grid(items, note=True):
    if not items:
        return ""
    cards = []
    for it in items:
        price = ""
        if it.get("price"):
            disc = f'<b class="disc">{it["discount"]}%</b>' if it.get("discount") else ""
            price = f'<span class="price">{disc}{won(it["price"])}</span>'
        pic = (f'<div class="pimg"><img loading="lazy" src="{e(img(it["image"]))}" alt="{e(it["name"])}">'
               + ('<span class="soldout">품절</span>' if it.get("sold_out") else "") + "</div>") if it.get("image") else \
            f'<div class="pimg noimg"><span>{e(it.get("category") or "ITEM")}</span></div>'
        brand = f'<span class="brand">{e(it["brand"])}</span>' if it.get("brand") else f'<span class="brand">{e(it.get("category") or "")}</span>'
        cards.append(ext(it["link"], f'{pic}<div class="pinfo">{brand}<span class="pname">{e(it["name"])}</span>{price}</div>', "pcard"))
    direct_only = all(it.get("direct") for it in items)
    hint = ""
    if note:
        hint = ('<p class="hint">이 영상의 큐레이션이 종료되어 개별 상품 페이지로 연결돼요.</p>' if direct_only else
                '<p class="hint">제품을 누르면 도댕 큐레이터샵에서 착장 전체를 한 번에 볼 수 있어요.</p>')
    return f'<div class="pgrid">{"".join(cards)}</div>{hint}'


def page(title, body, root, desc=None, og_image=None):
    desc = desc or C["hero_sub"]
    og = f'<meta property="og:image" content="{e(og_image)}">' if og_image else ""
    return f'''<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">{og}
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="{root}assets/style.css">
</head><body>
<header class="top">
  <a class="logo" href="{root}index.html">{e(C["site_name"])}</a>
  <nav><a href="{root}looks.html">LOOK</a><a href="{root}shorts.html">SHORTS</a><a href="{root}videos.html">VIDEO</a><a href="{root}products.html">ITEMS</a></nav>
  {ext(SHOP, "큐레이터샵", "shopbtn")}
</header>
<main>{body}</main>
<footer>
  <div class="logo">{e(C["site_name"])}</div>
  <div class="links">{ext(C["youtube_url"], "YouTube")}{ext(C["instagram_url"], "Instagram")}{ext(SHOP, "무신사 큐레이터샵")}</div>
  <p class="fdisc">{e(C["disclosure"])}</p>
</footer>
<script src="{root}assets/app.js"></script>
</body></html>'''


def section(eyebrow, title, inner, more_href=None, root="", cls=""):
    more = f'<a class="more" href="{root}{more_href}">더보기 →</a>' if more_href else ""
    return f'<section class="{cls}"><div class="sec-head"><p>{e(eyebrow)}</p><h2>{e(title)}</h2>{more}</div>{inner}</section>'


def embed(v, t=0):
    q = f"?enablejsapi=1&rel=0&playsinline=1" + (f"&start={t}" if t else "")
    ratio = "v" if v["type"] == "shorts" else "h"
    return f'<div class="embed {ratio}"><iframe id="yt" src="https://www.youtube.com/embed/{v["id"]}{q}" title="{e(v["title"])}" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'


def search_box(placeholder):
    return f'<div class="filters"><input class="q" type="search" placeholder="{e(placeholder)}" data-target=".searchable"></div>'


# ---------------------------------------------------------------- cards
def look_cards(videos):
    """LOOK 목록: 숏폼 1개 = 카드 1개, 롱폼은 제품 설명 구간마다 카드 1개"""
    cards = []
    for v in videos:
        if v["type"] == "video" and v["sections"]:
            for i, s in enumerate(v["sections"]):
                cards.append({"video": v, "sec": s, "href": f"look/{v['id']}-{i + 1}.html", "idx": i})
        else:
            cards.append({"video": v, "sec": None, "href": f"v/{v['id']}.html"})
    return cards


def card_html(c, root=""):
    v, s = c["video"], c["sec"]
    if s is None:
        n = len(v["items"])
        sub = f"착장 {n}개" if n and v["match"] not in ("topic", None) else ("비슷한 추천템" if v["match"] == "topic" else "영상 보기")
        return f'''<a class="card searchable" data-q="{e(v["title"].lower())}" href="{root}{c["href"]}">
  <div class="img v"><img loading="lazy" src="{thumb(v["id"])}" alt=""><span class="badge">SHORTS</span></div>
  <div class="meta"><b>{e(v["title"])}</b><span>{sub}</span></div></a>'''
    pic = next((it["image"] for it in s["items"] if it.get("image")), "")
    inner = (f'<img loading="lazy" src="{e(img(pic))}" alt="" class="prod">' if pic else
             f'<div class="frame" style="{frame_style(v, s["t"] + 12)}"></div>')
    first = s["items"][0]["name"] if s["items"] else v["title"]
    return f'''<a class="card searchable" data-q="{e((s["label"] + " " + v["title"]).lower())}" href="{root}{c["href"]}">
  <div class="img p">{inner}<span class="badge">{fmt_t(s["t"])}</span></div>
  <div class="meta"><b>{e(s["label"] if s["kind"] == "look" else first)}</b><span>{e(v["title"])}</span></div></a>'''


def video_card(v, root=""):
    cls = "v" if v["type"] == "shorts" else "h"
    return f'''<a class="card searchable" data-q="{e(v["title"].lower())}" href="{root}v/{v["id"]}.html">
  <div class="img {cls}"><img loading="lazy" src="{thumb(v["id"])}" alt=""></div>
  <div class="meta"><b>{e(v["title"])}</b><span>{fmt_date(v["published"])}</span></div></a>'''


# ---------------------------------------------------------------- pages
def write(path, html):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


def items_block(v, cat):
    """영상 상세의 '착용 제품' 블록 (매칭 종류별 문구)"""
    link = primary_link(v)
    if v["match"] in ("exact", "title", "manual"):
        head = "착용 제품"
        cta = ext(link, "도댕 큐레이터샵에서 착장 한 번에 보기 ↗", "btn big")
        grid = product_grid(v["items"])
    elif v["match"] == "items":
        head = "착용 제품"
        cta = ext(SHOP, "도댕 큐레이터샵 둘러보기 ↗", "btn big")
        grid = product_grid(v["items"])
    elif v["match"] == "topic":
        head = "이 영상과 비슷한 도댕 추천템"
        cta = ext(link, f"‘{v['curation']['title']}’ 큐레이션 보기 ↗", "btn big")
        grid = product_grid(v["items"][:12])
    else:
        head = "도댕 큐레이터샵 인기템"
        cta = ext(SHOP, "도댕 큐레이터샵 둘러보기 ↗", "btn big")
        grid = product_grid([{**{"name": g["name"], "brand": g["brand"], "image": g["image"], "price": g["price"], "discount": g["discount"]}, "link": SHOP} for g in cat.popular])
    return f'<div class="items-block"><h3>{e(head)}</h3>{cta}{grid}</div>'


def build():
    videos, cat = load()
    shorts = [v for v in videos if v["type"] == "shorts"]
    longs = [v for v in videos if v["type"] == "video"]
    cards = look_cards(videos)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")

    pop_items = [{"name": g["name"], "brand": g["brand"], "image": g["image"], "price": g["price"], "discount": g["discount"], "link": SHOP} for g in cat.popular]

    # ---- index
    hero_title = "<br>".join(e(x) for x in C["hero_title"].split("\n"))
    body = f'''
<div class="hero" style="--bg:url('{thumb(videos[0]["id"])}')">
  <h1>{hero_title}</h1><p>{e(C["hero_sub"])}</p>
  <div class="hero-cta"><a class="btn light" href="looks.html">코디 보러가기</a>{ext(SHOP, "도댕 큐레이터샵 ↗", "btn ghost-light")}</div>
  <p class="count">영상 {len(videos)}개 · 착장 정보 {sum(1 for v in videos if v["items"])}개</p>
</div>
{section("영상 속 코디 모아보기", "LOOK", '<div class="grid g6">' + "".join(card_html(c) for c in cards[:12]) + "</div>", "looks.html")}
{section("지금 도댕 큐레이터샵에서 가장 많이 보는", "BEST ITEMS", product_grid(pop_items, note=False) + '<div class="center">' + ext(SHOP, "큐레이터샵 전체 보기 ↗", "btn") + "</div>") if pop_items else ""}
{section("숏폼 영상 코디 정보 보기", "SHORTS", '<div class="grid g6">' + "".join(video_card(v) for v in shorts[:12]) + "</div>", "shorts.html")}
{section("롱폼 영상 코디 정보 보기", "VIDEO", '<div class="grid g3">' + "".join(video_card(v) for v in longs[:6]) + "</div>", "videos.html")}
'''
    write("index.html", page(C["site_title"], body, "", og_image=thumb(videos[0]["id"])))

    # ---- lists
    write("looks.html", page(f"LOOK | {C['site_title']}", section(f"영상 속 코디 {len(cards)}개", "LOOK", search_box("코디·제품·영상 제목 검색") + '<div class="grid g6">' + "".join(card_html(c) for c in cards) + "</div>"), ""))
    write("shorts.html", page(f"SHORTS | {C['site_title']}", section(f"숏폼 {len(shorts)}개 코디 정보", "SHORTS", search_box("영상 제목 검색") + '<div class="grid g6">' + "".join(video_card(v) for v in shorts) + "</div>"), ""))
    write("videos.html", page(f"VIDEO | {C['site_title']}", section(f"롱폼 {len(longs)}개 코디 정보", "VIDEO", search_box("영상 제목 검색") + '<div class="grid g3">' + "".join(video_card(v) for v in longs) + "</div>"), ""))

    # ---- items (영상에 실제로 나온 제품, 중복 제거)
    seen, all_items = set(), []
    for v in videos:
        if v["match"] in ("topic", None):
            continue
        for it in v["items"]:
            key = (it.get("brand", ""), it["name"])
            if key in seen:
                continue
            seen.add(key)
            all_items.append({**it, "video": v})
    chips = "".join(f'<button data-c="{c}">{c}</button>' for c in CAT_ORDER if any(i["category"] == c for i in all_items))
    grid = "".join(
        f'<div class="searchable" data-c="{it["category"]}" data-q="{e((it.get("brand", "") + " " + it["name"]).lower())}">' + product_grid([it], note=False)
        + f'<a class="from" href="v/{it["video"]["id"]}.html">▶ {e(it["video"]["title"])}</a></div>'
        for it in all_items)
    body = section(f"영상에 나온 제품 {len(all_items)}개", "ITEMS", f'''
<div class="filters"><input class="q" type="search" placeholder="브랜드·제품명 검색" data-target=".searchable">
<div class="chips"><button data-c="" class="on">ALL</button>{chips}</div></div>
<div class="items-grid">{grid}</div>
<p class="hint">제품을 누르면 도댕 큐레이터샵 큐레이션으로 이동해요.</p>''')
    write("products.html", page(f"ITEMS | {C['site_title']}", body, ""))

    # ---- video detail
    for i, v in enumerate(videos):
        chapters = ""
        if v["type"] == "video" and v["sections"]:
            chapters = section("누르면 해당 제품 설명부터 재생돼요", "제품별로 보기",
                               '<div class="grid g4">' + "".join(card_html({"video": v, "sec": s, "href": f"look/{v['id']}-{k + 1}.html"}, "../")
                                                                  for k, s in enumerate(v["sections"])) + "</div>")
        prev_v = videos[i - 1] if i > 0 else None
        next_v = videos[i + 1] if i + 1 < len(videos) else None
        pager = '<div class="pager">' + (f'<a href="{prev_v["id"]}.html">← 최신 영상</a>' if prev_v else "<span></span>") + (f'<a href="{next_v["id"]}.html">이전 영상 →</a>' if next_v else "") + "</div>"
        body = f'''
<div class="detail">
  {embed(v)}
  <div class="info">
    <span class="tag">{"SHORTS" if v["type"] == "shorts" else "VIDEO"}</span>
    <h1>{e(v["title"])}</h1>
    <p class="sub">{fmt_date(v["published"])} · 모델 {e(v["model_stats"])}</p>
    {items_block(v, cat)}
    <div class="actions">{ext(yt_url(v), "▶ 유튜브에서 보기", "btn ghost")}</div>
  </div>
</div>
{chapters}{pager}'''
        write(f"v/{v['id']}.html", page(f"{v['title']} | {C['site_title']}", body, "../", desc=f"{v['title']} 착장 정보 · 도댕 무신사 큐레이터샵", og_image=thumb(v["id"])))

    # ---- long-form section (제품 설명 시작 시점)
    for v in longs:
        secs = v["sections"]
        for k, s in enumerate(secs):
            prev_s = f'<a href="{v["id"]}-{k}.html">← 이전 제품</a>' if k > 0 else "<span></span>"
            next_s = f'<a href="{v["id"]}-{k + 2}.html">다음 제품 →</a>' if k + 1 < len(secs) else ""
            subs = "".join(f'<button class="seek" data-t="{x["t"]}">▶ {fmt_t(x["t"])} {e(x["label"])}</button>' for x in s["sub"])
            link = s["link"] or primary_link(v)
            title = s["label"] if s["kind"] == "look" else (s["items"][0]["name"] if s["items"] else s["label"])
            body = f'''
<div class="detail">
  {embed(v, s["t"])}
  <div class="info">
    <span class="tag">{fmt_t(s["t"])} · {"LOOK" if s["kind"] == "look" else "ITEM"}</span>
    <h1>{e(title)}</h1>
    <p class="sub"><a href="../v/{v["id"]}.html">{e(v["title"])}</a></p>
    <div class="seeks"><button class="seek" data-t="{s["t"]}">▶ {fmt_t(s["t"])} 설명 처음부터</button>{subs}</div>
    <div class="items-block"><h3>착용 제품</h3>{ext(link, "도댕 큐레이터샵에서 보기 ↗", "btn big")}{product_grid(s["items"]) if s["items"] else ""}</div>
  </div>
</div>
<div class="pager">{prev_s}{next_s}</div>'''
            write(f"look/{v['id']}-{k + 1}.html", page(f"{title} | {C['site_title']}", body, "../", og_image=img(s["items"][0]["image"]) if s["items"] and s["items"][0].get("image") else thumb(v["id"])))

    write("404.html", page("페이지를 찾을 수 없어요", '<section class="cta"><h2>페이지를 찾을 수 없어요</h2><a class="btn" href="' + (C.get("base_url") or "/") + '">홈으로</a></section>', ""))
    (OUT / ".nojekyll").write_text("")
    stats = {}
    for v in videos:
        stats[v["match"]] = stats.get(v["match"], 0) + 1
    print(f"[build] videos={len(videos)} (shorts {len(shorts)}, long {len(longs)}) cards={len(cards)} items={len(all_items)} match={stats}")


if __name__ == "__main__":
    build()
