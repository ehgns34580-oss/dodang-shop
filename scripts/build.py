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
NAV_EVENT = ""  # 무신사 행사(무진장 등) 진행 중이면 메뉴 맨 앞에 '블프 혜택' 추가


def load_json(name, default):
    p = ROOT / "data" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ---------------------------------------------------------------- data
def load():
    videos = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8"))
    cur_path = ROOT / "data" / "curations.json"
    ink_path = ROOT / "data" / "inpock.json"
    inpock = json.loads(ink_path.read_text(encoding="utf-8")) if ink_path.exists() else []
    cat = Catalog(json.loads(cur_path.read_text(encoding="utf-8")) if cur_path.exists() else {}, SHOP, inpock)
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


def product_grid(items, note=True, hint_text=None, ranked=False):
    if not items:
        return ""
    cards = []
    for n, it in enumerate(items, 1):
        price = ""
        if it.get("price"):
            disc = f'<b class="disc">{it["discount"]}%</b>' if it.get("discount") else ""
            price = f'<span class="price">{disc}{won(it["price"])}</span>'
        pic = (f'<div class="pimg"><img loading="lazy" src="{e(img(it["image"]))}" alt="{e(it["name"])}">'
               + (f'<span class="rnum">{n}</span>' if ranked else "")
               + ('<span class="soldout">품절</span>' if it.get("sold_out") else "") + "</div>") if it.get("image") else \
            f'<div class="pimg noimg"><span>{e(it.get("category") or "ITEM")}</span></div>'
        brand = f'<span class="brand">{e(it["brand"])}</span>' if it.get("brand") else f'<span class="brand">{e(it.get("category") or "")}</span>'
        cards.append(ext(it["link"], f'{pic}<div class="pinfo">{brand}<span class="pname">{e(it["name"])}</span>{price}</div>', "pcard"))
    direct_only = all(it.get("direct") for it in items)
    hint = ""
    if note and hint_text:
        hint = f'<p class="hint">{e(hint_text)}</p>'
    elif note:
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
  <nav>{NAV_EVENT.replace("{root}", root)}<a href="{root}coordi.html">코디</a><a href="{root}rank.html">랭킹</a><a href="{root}collections.html">모음집</a><a href="{root}shorts.html">SHORTS</a><a href="{root}videos.html">VIDEO</a><a href="{root}products.html">ITEMS</a></nav>
  {ext(SHOP, "큐레이터샵", "shopbtn")}
</header>
<main>{body}</main>
<footer>
  <div class="logo">{e(C["site_name"])}</div>
  <div class="links">{ext(C["youtube_url"], "YouTube")}{ext(C["instagram_url"], "Instagram")}{ext(SHOP, "무신사 큐레이터샵")}</div>
  <p class="fdisc">{e(C["disclosure"])}</p>
</footer>
<script src="{root}assets/app.js"></script>{analytics()}
</body></html>'''


def analytics():
    """방문자 집계(GoatCounter). config.json 의 goatcounter 에 사이트 이름이 있을 때만 넣음."""
    code = (C.get("goatcounter") or "").strip()
    if not code:
        return ""
    return f'\n<script data-goatcounter="https://{e(code)}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'


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


def long_row(v, root=""):
    """롱폼 1개 = 영상 카드 + 제품별 카드 가로 스크롤"""
    secs = "".join(card_html({"video": v, "sec": s, "href": f"look/{v['id']}-{k + 1}.html"}, root) for k, s in enumerate(v["sections"]))
    q = (v["title"] + " " + " ".join(it["name"] for it in v["items"])).lower()
    return f'''<div class="lrow searchable" data-q="{e(q)}">
  <a class="lhead" href="{root}v/{v["id"]}.html"><div class="img h"><img loading="lazy" src="{thumb(v["id"])}" alt=""></div>
  <div class="meta"><b>{e(v["title"])}</b><span>{fmt_date(v["published"])} · 제품 {len(v["sections"]) or len(v["items"])}개</span></div></a>
  <div class="lsecs">{secs}</div></div>'''


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
        head = "이 영상 속 아이템, 도댕 추천 상품"
        cur = v.get("curation")
        cta = (ext(primary_link(v), f"큐레이터샵 ‘{cur['title']}’ 모아보기 ↗", "btn big") if cur else
               ext(SHOP, "도댕 큐레이터샵 전체 보기 ↗", "btn big"))
        grid = product_grid(v["items"], hint_text="영상 주제와 같은 도댕 큐레이터샵 상품이에요. 누르면 해당 상품 페이지로 이동해요.")
    else:
        head = "도댕 큐레이터샵 인기템"
        cta = ext(SHOP, "도댕 큐레이터샵 전체 보기 ↗", "btn big")
        grid = product_grid(v["items"], hint_text="지금 도댕 큐레이터샵에서 가장 많이 보는 상품이에요.")
    return f'<div class="items-block"><h3>{e(head)}</h3>{cta}{grid}</div>'


# ---------------------------------------------------------------- 코디 / 랭킹 / 모음집 / 행사
def goods_item(g, link=None):
    return {"name": g["name"], "brand": g["brand"], "image": g["image"], "price": g["price"],
            "discount": g["discount"], "sold_out": g.get("sold_out"), "link": link or g.get("link") or SHOP}


def coordi_list(videos):
    """전신샷이 자동으로 찾아진 영상 = 코디. 실제 착용 제품이 있는 영상을 앞으로."""
    found = load_json("coordi.json", {})
    out = [(v, found[v["id"]]) for v in videos if found.get(v["id"], {}).get("score", 0) >= 0.4 and v["items"]]
    out.sort(key=lambda x: x[0]["published"], reverse=True)
    out.sort(key=lambda x: x[0]["match"] in ("topic", None))
    return out


def coordi_card(v, f, root=""):
    real = v["match"] not in ("topic", None)
    sub = f"착용 제품 {len(v['items'])}개" if real else "비슷한 추천템"
    pos = "center 30%" if v["type"] == "shorts" else "center"
    return f'''<a class="card searchable" data-q="{e(v["title"].lower())}" href="{root}coordi/{v["id"]}.html">
  <div class="img c"><img loading="lazy" src="{e(f["image"])}" alt="{e(v["title"])} 코디" style="object-position:{pos}"></div>
  <div class="meta"><b>{e(v["title"])}</b><span>{sub}</span></div></a>'''


def most_curated(cat, limit=20):
    """큐레이션에 여러 번 담긴 상품 = 도댕이 반복해서 추천한 상품"""
    cnt, first = {}, {}
    for c in cat.curations:
        for g in c["goods"]:
            if g.get("sold_out"):
                continue
            cnt[g["goods_no"]] = cnt.get(g["goods_no"], 0) + 1
            first.setdefault(g["goods_no"], g)
    top = sorted(cnt, key=lambda k: -cnt[k])[:limit]
    return [goods_item(first[k]) for k in top if cnt[k] > 1]


def live_card(l):
    pic = f'<div class="limg"><img loading="lazy" src="{e(img(l["image"], 480))}" alt=""><span class="badge">{e(l["label"])}</span></div>' if l.get("image") else ""
    return ext(l["link"] or SHOP, f'''{pic}<div class="ltime"><b>{e(l["date"])}</b> {e(l["time"])}</div>
  <div class="lbrand">{e(l["brand"])}</div><p class="ldesc">{e(l["desc"])}</p>''', "live")


def build_extra(videos, cat):
    global NAV_EVENT
    ev = load_json("events.json", {})
    curated_brands = {}
    for c in cat.curations:
        for g in c["goods"]:
            if not g.get("sold_out"):
                curated_brands.setdefault(g["brand"], {})[g["goods_no"]] = g

    # ---- 블프/무진장 혜택
    if ev and (ev.get("lives") or ev.get("brand_days") or ev.get("coupons")):
        NAV_EVENT = '<a class="hot" href="{root}sale.html">블프 혜택</a>'
        parts = []
        cards = [f'<div class="bcard coupon"><span class="tag">쿠폰</span><b>{e(c["name"] or c["title"])}</b><p>{e(c["sub"])}</p></div>' for c in ev.get("coupons", [])]
        cards += [f'<div class="bcard"><span class="tag">{e(b["tag"])}</span><b>{e(b["title"])}</b>' + (f'<p>{e(b["sub"])}</p>' if b["sub"] else "") + "</div>" for b in ev.get("benefits", [])]
        if cards:
            parts.append(section("놓치면 아쉬운", "쿠폰 · 이벤트", f'<div class="bgrid">{"".join(cards)}</div>'))
        if ev.get("lives"):
            parts.append(section("방송 시간에 맞춰 들어가면 추가 할인", "라이브 특가 일정", f'<div class="lgrid">{"".join(live_card(l) for l in ev["lives"])}</div>'))
        for bd in ev.get("brand_days", []):
            blocks = []
            for tab in bd["tabs"]:
                rows = []
                for b in tab["brands"]:
                    mine = list(curated_brands.get(b["name"], {}).values())[:4]
                    labels = "".join(f'<span class="lab">{e(x.strip())}</span>' for x in b["label"].split(",") if x.strip())
                    rows.append(f'''<div class="brow"><div class="bhead"><b>{e(b["name"])}</b>{labels}<span>{e(b["desc"])}</span></div>
{('<p class="bpick">도댕 큐레이터샵에 담긴 ' + e(b["name"]) + ' 상품</p>' + product_grid([goods_item(g) for g in mine], note=False)) if mine else ""}</div>''')
                blocks.append(f'<div class="btab"><h3>{e(tab["name"])}</h3>{"".join(rows)}</div>')
            parts.append(section("기간별 참여 브랜드 · 도댕 추천 상품까지", e(bd["title"]), "".join(blocks)))
        sale_curs = [c for c in cat.curations if any(k in c["title"] for k in ("블프", "무진장", "특가", "세일"))]
        if sale_curs:
            parts.append(section("도댕이 블프용으로 따로 모은", "블프 큐레이션", collection_grid(cat, sale_curs)))
        head = f'''<div class="ehero"><p>{e(ev.get("period", ""))}</p><h1>{e(ev.get("name") or "무신사 무진장")}</h1>
<p>쿠폰, 라이브, 브랜드데이를 한 페이지에 정리했어요. 하루 몇 번씩 자동으로 업데이트돼요.</p>
<div class="hero-cta">{ext(ev.get("url") or "https://www.musinsa.com", "무신사 행사 페이지 ↗", "btn light")}{ext(SHOP, "도댕 큐레이터샵 ↗", "btn ghost-light")}</div></div>'''
        write("sale.html", page(f"블프 혜택 정리 | {C['site_title']}", head + "".join(parts), "", desc=f"{ev.get('name', '무신사 무진장')} 쿠폰·라이브·브랜드데이 한눈에 정리"))

    # ---- 랭킹
    pop = [goods_item(g) for g in cat.popular if g.get("price")]
    multi = most_curated(cat)
    body = ""
    if pop:
        body += section("지금 도댕 큐레이터샵에서 가장 많이 보는", "인기 랭킹 TOP " + str(len(pop)), product_grid(pop, note=False, ranked=True))
    if multi:
        body += section("도댕이 여러 큐레이션에 반복해서 담은", "찐 추천 랭킹", product_grid(multi, note=False, ranked=True))
    write("rank.html", page(f"랭킹 | {C['site_title']}", body + '<div class="center">' + ext(SHOP, "큐레이터샵 전체 보기 ↗", "btn") + "</div>", ""))

    # ---- 모음집 (큐레이션 전체)
    write("collections.html", page(f"모음집 | {C['site_title']}", section(f"큐레이션 {len(cat.curations)}개", "모음집", collection_grid(cat, cat.curations)), ""))

    # ---- 코디
    co = coordi_list(videos)
    write("coordi.html", page(f"코디 | {C['site_title']}", section(f"영상 속 전신 코디 {len(co)}개 · 누르면 착용 제품까지", "코디",
          search_box("영상 제목 검색") + '<div class="grid g5">' + "".join(coordi_card(v, f) for v, f in co) + "</div>"), ""))
    for i, (v, f) in enumerate(co):
        real = v["match"] not in ("topic", None)
        prev_c = f'<a href="{co[i - 1][0]["id"]}.html">← 이전 코디</a>' if i > 0 else "<span></span>"
        next_c = f'<a href="{co[i + 1][0]["id"]}.html">다음 코디 →</a>' if i + 1 < len(co) else ""
        body = f'''
<div class="detail">
  <div class="cphoto {"v" if v["type"] == "shorts" else "h"}"><img src="{e(f["image"])}" alt="{e(v["title"])} 코디"></div>
  <div class="info">
    <span class="tag">LOOK</span>
    <h1>{e(v["title"])}</h1>
    <p class="sub">모델 {e(v["model_stats"])} · {fmt_date(v["published"])}</p>
    {items_block(v, cat)}
    <div class="actions"><a class="btn ghost" href="../v/{v["id"]}.html">영상으로 보기</a></div>
  </div>
</div>
<div class="pager">{prev_c}{next_c}</div>'''
        write(f"coordi/{v['id']}.html", page(f"{v['title']} 코디 | {C['site_title']}", body, "../", desc=f"{v['title']} 코디 착용 제품 · 도댕 무신사 큐레이터샵", og_image=f["image"]))
    return ev, co, pop


def collection_grid(cat, curs):
    out = []
    for c in curs:
        pics = "".join(f'<img loading="lazy" src="{e(img(g["image"], 240))}" alt="">' for g in c["goods"][:4] if g.get("image"))
        out.append(ext(cat.link(c), f'<div class="cpics">{pics}</div><div class="meta"><b>{e(c["title"])}</b><span>{len(c["goods"])} ITEMS'
                       + (f' · {e(c["description"])}' if c.get("description") else "") + "</span></div>", "card coll"))
    return f'<div class="grid g4">{"".join(out)}</div>'


def build():
    videos, cat = load()
    shorts = [v for v in videos if v["type"] == "shorts"]
    longs = [v for v in videos if v["type"] == "video"]
    cards = look_cards(videos)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")

    ev, co, pop_items = build_extra(videos, cat)

    # ---- index
    hero_title = "<br>".join(e(x) for x in C["hero_title"].split("\n"))
    sale_bar = ""
    if NAV_EVENT:
        nxt = ev.get("lives", [])[:1]
        sale_bar = (f'<a class="salebar" href="sale.html"><b>{e(ev.get("name") or "무진장")}</b><span>{e(ev.get("period", ""))}'
                    + (f' · 다음 라이브 {e(nxt[0]["date"])} {e(nxt[0]["time"])} {e(nxt[0]["brand"])}' if nxt else "") + "</span><em>혜택 정리 보기 →</em></a>")
    body = f'''
{sale_bar}
<div class="hero" style="--bg:url('{thumb(videos[0]["id"])}')">
  <h1>{hero_title}</h1><p>{e(C["hero_sub"])}</p>
  <div class="hero-cta"><a class="btn light" href="{"coordi.html" if co else "shorts.html"}">코디 보러가기</a>{ext(SHOP, "도댕 큐레이터샵 ↗", "btn ghost-light")}</div>
  <p class="count">영상 {len(videos)}개 · 착장 정보 {sum(1 for v in videos if v["items"])}개</p>
</div>
{section("지금 도댕 큐레이터샵에서 가장 많이 보는", "랭킹", product_grid(pop_items[:10], note=False, ranked=True), "rank.html") if pop_items else ""}
{section("영상 속 전신 코디 · 누르면 착용 제품까지", "코디", '<div class="grid g5">' + "".join(coordi_card(v, f) for v, f in co[:10]) + "</div>", "coordi.html") if co else ""}
{section("숏폼 영상 코디 정보 보기", "SHORTS", '<div class="grid g6">' + "".join(card_html({"video": v, "sec": None, "href": f"v/{v['id']}.html"}) for v in shorts[:12]) + "</div>", "shorts.html")}
{section("롱폼 영상 · 제품별로 바로 보기", "VIDEO", "".join(long_row(v) for v in longs[:3]), "videos.html")}
'''
    write("index.html", page(C["site_title"], body, "", og_image=thumb(videos[0]["id"])))

    # ---- lists
    write("shorts.html", page(f"SHORTS | {C['site_title']}", section(f"숏폼 {len(shorts)}개 코디 정보", "SHORTS", search_box("영상 제목 검색") + '<div class="grid g6">' + "".join(card_html({"video": v, "sec": None, "href": f"v/{v['id']}.html"}) for v in shorts) + "</div>"), ""))
    write("videos.html", page(f"VIDEO | {C['site_title']}", section(f"롱폼 {len(longs)}개 · 제품별로 바로 보기", "VIDEO", search_box("영상 제목·제품명 검색") + "".join(long_row(v) for v in longs)), ""))
    write("looks.html", '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=shorts.html"><a href="shorts.html">SHORTS</a>')

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
