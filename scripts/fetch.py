#!/usr/bin/env python3
"""유튜브 채널의 새 영상을 가져와 설명란에서 착장/무신사 링크를 파싱해 data/videos.json 에 누적 저장.

- YouTube RSS 로 최신 영상 감지 (30분마다)
- data/channel_ids.json(scripts/channel.py 가 채널 전체를 스캔한 결과)에 있는 과거 영상도 모두 포함
- 상세정보(설명란·날짜·장면 썸네일)는 영상 시청 페이지에서 1회만 읽고 저장
외부 라이브러리 없이 표준 라이브러리만 사용.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "videos.json"
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
UA = {"User-Agent": "Mozilla/5.0 (dodang-shop updater)"}

# ---------------------------------------------------------------- parsing
GOODS_RE = re.compile(r"https?://(?:www\.)?musinsa\.com/curator/goods/[A-Za-z0-9_-]+")
CURATION_RE = re.compile(r"https?://(?:www\.)?musinsa\.com/curator/(?:shop|s)/[^\s)]+")
OTHER_SHOP_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?(?:29cm\.co\.kr|wconcept\.co\.kr|kream\.co\.kr|zigzag\.kr|ably\.co\.kr|smartstore\.naver\.com|link\.coupang\.com|musinsa\.com/(?:products|app/goods))[^\s)]*")
STATS_RE = re.compile(r"MODEL\s*STATS?\s*[:：]?\s*\[?\s*(?:[^\d\]\s]+\s*)?(\d{3})\s*(?:cm)?\s*/\s*(\d{2,3})\s*(?:kg)?", re.I)
TIME_RE = re.compile(r"^\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s+(.+?)\s*$")
LOOK_RE = re.compile(r"LOOK\s*(\d+)(?:\s*[-–]\s*(\d+))?", re.I)
NUM_PREFIX_RE = re.compile(r"^\s*(?:\d+\s*[).]|[①-⑳]|[-•·▶️✔️☑️✅]+)\s*")

CATEGORIES = [
    ("OUTER", ["코트", "자켓", "재킷", "무스탕", "블루종", "패딩", "점퍼", "후리스", "플리스", "가디건", "베스트", "조끼", "아우터", "파카", "트렌치", "봄버", "MA-1", "jacket", "coat"]),
    ("TOP", ["니트", "티셔츠", "긴팔", "반팔", "셔츠", "맨투맨", "후드", "스웨터", "스웻", "탑", "카라", "폴로", "터틀넥", "헨리넥", "knit", "tee", "shirt"]),
    ("BOTTOM", ["팬츠", "슬랙스", "데님", "청바지", "진 ", "치노", "카고", "조거", "쇼츠", "반바지", "트라우저", "pants", "denim", "jean"]),
    ("SHOES", ["슈즈", "스니커즈", "운동화", "부츠", "로퍼", "더비", "구두", "샌들", "슬리퍼", "shoes", "sneaker", "boot"]),
    ("BAG", ["백팩", "가방", "토트", "크로스백", "숄더백", "메신저", "bag"]),
    ("ACC", ["벨트", "링", "반지", "목걸이", "팔찌", "목도리", "머플러", "스카프", "비니", "모자", "캡", "양말", "장갑", "안경", "선글라스", "시계", "belt", "ring", "muffler", "beanie", "cap"]),
]
CATEGORY_ORDER = ["OUTER", "TOP", "BOTTOM", "SHOES", "BAG", "ACC", "ETC"]


def guess_category(name: str) -> str:
    low = name.lower()
    for cat, words in CATEGORIES:
        if any(w.lower() in low for w in words):
            return cat
    return "ETC"


def clean_name(text: str) -> str:
    text = NUM_PREFIX_RE.sub("", text)
    text = re.sub(r"\s*[:：\-–>→]+\s*$", "", text).strip()
    return text.strip(" \t:：-")


def to_seconds(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def parse_description(desc: str) -> dict:
    lines = [l.rstrip() for l in (desc or "").splitlines()]
    products, seen = [], set()

    def add(name, url):
        url = url.rstrip(".,)")
        if url in seen:
            return
        seen.add(url)
        name = clean_name(name) or "착용 제품"
        products.append({"name": name, "url": url, "category": guess_category(name)})

    for i, line in enumerate(lines):
        for m in list(GOODS_RE.finditer(line)) + list(OTHER_SHOP_RE.finditer(line)):
            url = m.group(0)
            before = line[: m.start()]
            name = clean_name(TIME_RE.sub(r"\2", before)) if before.strip() else ""
            if not name and i > 0:
                # 이전 줄이 이름일 수 있음 (타임라인 형식: "00:27 1) 코트" 다음 줄에 링크)
                prev = lines[i - 1].strip()
                if prev and "http" not in prev:
                    tm = TIME_RE.match(prev)
                    name = clean_name(tm.group(2) if tm else prev)
            add(name, url)

    curation = None
    for line in lines:
        m = CURATION_RE.search(line)
        if m:
            curation = m.group(0).rstrip(".,)")
            break

    stats = None
    m = STATS_RE.search(desc or "")
    if m:
        stats = f"{m.group(1)}cm / {m.group(2)}kg"

    # 타임라인: 제품 섹션(번호) + LOOK x-y
    looks, chapters = [], []
    current_section = None
    for line in lines:
        tm = TIME_RE.match(line)
        if not tm:
            continue
        sec, label = to_seconds(tm.group(1)), tm.group(2).strip()
        chapters.append({"t": sec, "label": label})
        lm = LOOK_RE.search(label)
        if lm:
            looks.append({
                "t": sec,
                "label": f"LOOK {lm.group(1)}" + (f"-{lm.group(2)}" if lm.group(2) else ""),
                "group": int(lm.group(1)),
                "section": current_section,
            })
            continue
        nm = re.match(r"^\s*(\d+)\s*[).]\s*(.+)$", label)
        if nm:
            current_section = {"no": int(nm.group(1)), "name": nm.group(2).strip()}

    # LOOK 그룹 → 해당 번호 제품 매칭
    numbered = {}
    for line in lines:
        nm = re.match(r"^\s*(\d+)\s*[).]\s*(.+?)\s*[:：]\s*(" + GOODS_RE.pattern + ")", line)
        if nm:
            numbered[int(nm.group(1))] = nm.group(3)
    for lk in looks:
        lk["product_url"] = numbered.get(lk["group"])

    return {"products": products, "curation_url": curation, "model_stats": stats, "looks": looks, "chapters": chapters}


# ---------------------------------------------------------------- sources
def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def from_rss(channel_id: str) -> list:
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"))
    out = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns).get("href")
        out.append({
            "id": e.find("yt:videoId", ns).text,
            "title": e.find("a:title", ns).text or "",
            "published": e.find("a:published", ns).text,
            "description": e.find("m:group/m:description", ns).text or "",
            "type": "shorts" if "/shorts/" in link else "video",
        })
    return out


def from_watch(vid: str) -> dict:
    """영상 시청 페이지에서 제목·설명·업로드일·길이·스토리보드(장면 썸네일) 정보를 읽음"""
    html = http_get(f"https://www.youtube.com/watch?v={vid}&hl=ko").decode("utf-8", "replace")
    marker = "var ytInitialPlayerResponse = "
    i = html.find(marker)
    if i < 0:
        raise ValueError("playerResponse 없음")
    j, _ = json.JSONDecoder().raw_decode(html[i + len(marker):])
    vd = j.get("videoDetails") or {}
    mf = (j.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    if not vd.get("title"):
        raise ValueError(j.get("playabilityStatus", {}).get("reason", "비공개/삭제"))
    return {
        "id": vid,
        "title": vd["title"],
        "description": vd.get("shortDescription", ""),
        "published": mf.get("publishDate") or mf.get("uploadDate") or "",
        "length": int(vd.get("lengthSeconds") or 0),
        "storyboard": parse_storyboard((j.get("storyboards") or {}).get("playerStoryboardSpecRenderer", {}).get("spec", "")),
    }


def parse_storyboard(spec: str):
    """가장 고해상도 스토리보드 레벨 → 시트 URL 템플릿/격자 정보"""
    if not spec:
        return None
    parts = spec.split("|")
    base = parts[0]
    lv = len(parts) - 2
    w, h, count, cols, rows, interval, name, sigh = parts[-1].split("#")
    url = base.replace("$L", str(lv)).replace("$N", name) + "&sigh=" + sigh
    return {"url": url, "w": int(w), "h": int(h), "count": int(count), "cols": int(cols), "rows": int(rows), "interval": int(interval) or 5000}


def iso_utc(s: str) -> str:
    from datetime import datetime, timezone
    return datetime.fromisoformat(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------------------------------------------------------------- main
def main():
    import time

    db = {}
    if DATA.exists():
        db = {v["id"]: v for v in json.loads(DATA.read_text(encoding="utf-8"))}
    known = len(db)

    # 1) RSS: 최신 15개 (빠름)
    try:
        for v in from_rss(CONFIG["channel_id"]):
            db[v["id"]] = {**db.get(v["id"], {}), **v}
    except Exception as exc:
        print(f"[fetch] RSS 실패: {exc}", file=sys.stderr)

    # 2) 채널 전체 목록(scripts/channel.py 결과)에서 아직 없는 영상 추가
    ch_path = ROOT / "data" / "channel_ids.json"
    shorts_ids = set()
    if ch_path.exists():
        ch = json.loads(ch_path.read_text(encoding="utf-8"))
        shorts_ids = set(ch.get("shorts", []))
        for vid in ch.get("videos", []) + ch.get("shorts", []):
            db.setdefault(vid, {"id": vid})

    # 3) 상세정보 없는 영상 → 시청 페이지에서 보충 (롱폼은 장면 썸네일용 스토리보드 포함)
    todo = [v for v in db.values() if not v.get("detail")]
    for n, v in enumerate(todo, 1):
        try:
            d = from_watch(v["id"])
            if d["published"]:
                d["published"] = iso_utc(d["published"])
            else:
                d.pop("published")
            if "type" not in v:
                d["type"] = "shorts" if (v["id"] in shorts_ids or 0 < d["length"] <= 180) else "video"
            db[v["id"]] = {**v, **d, "detail": True}
        except Exception as exc:
            print(f"[fetch] {v['id']} 상세 실패: {exc}", file=sys.stderr)
            if not v.get("title"):
                db.pop(v["id"], None)
        if n % 25 == 0:
            print(f"[fetch] 상세 {n}/{len(todo)}")
        time.sleep(0.4)

    for vid, v in db.items():
        v.setdefault("type", "shorts" if vid in shorts_ids else "video")
        v.update(parse_description(v.get("description", "")))

    videos = sorted(db.values(), key=lambda x: x.get("published", ""), reverse=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    new = len(videos) - known
    print(f"[fetch] total={len(videos)} new={new}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"new={new}\n")


if __name__ == "__main__":
    main()
