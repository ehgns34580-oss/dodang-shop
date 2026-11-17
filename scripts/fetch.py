#!/usr/bin/env python3
"""유튜브 채널의 새 영상을 가져와 설명란에서 착장/무신사 링크를 파싱해 data/videos.json 에 누적 저장.

- 기본: YouTube RSS (키 불필요, 최근 15개)
- 환경변수 YT_API_KEY 가 있으면 YouTube Data API 로 전체 업로드 목록을 가져옴 (과거 영상 백필)
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


def from_api(channel_id: str, key: str, max_pages: int = 20) -> list:
    uploads = "UU" + channel_id[2:]
    out, token = [], ""
    for _ in range(max_pages):
        q = urllib.parse.urlencode({"part": "snippet", "playlistId": uploads, "maxResults": 50, "key": key, "pageToken": token})
        d = json.loads(http_get(f"https://www.googleapis.com/youtube/v3/playlistItems?{q}"))
        ids = [it["snippet"]["resourceId"]["videoId"] for it in d.get("items", [])]
        # 길이로 shorts 판별 (<=180초)
        durations = {}
        if ids:
            q2 = urllib.parse.urlencode({"part": "contentDetails", "id": ",".join(ids), "key": key})
            for v in json.loads(http_get(f"https://www.googleapis.com/youtube/v3/videos?{q2}")).get("items", []):
                durations[v["id"]] = iso_duration(v["contentDetails"]["duration"])
        for it in d.get("items", []):
            sn = it["snippet"]
            vid = sn["resourceId"]["videoId"]
            if sn.get("title") in ("Private video", "Deleted video"):
                continue
            out.append({
                "id": vid,
                "title": sn["title"],
                "published": sn["publishedAt"],
                "description": sn.get("description", ""),
                "type": "shorts" if durations.get(vid, 999) <= 180 else "video",
            })
        token = d.get("nextPageToken")
        if not token:
            break
    return out


def iso_duration(s: str) -> int:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s)
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


# ---------------------------------------------------------------- main
def main():
    key = os.environ.get("YT_API_KEY", "").strip()
    try:
        raw = from_api(CONFIG["channel_id"], key) if key else from_rss(CONFIG["channel_id"])
    except Exception as exc:  # 네트워크 실패 시 기존 데이터 유지
        print(f"[fetch] 실패: {exc}", file=sys.stderr)
        sys.exit(0 if DATA.exists() else 1)

    db = {}
    if DATA.exists():
        db = {v["id"]: v for v in json.loads(DATA.read_text(encoding="utf-8"))}

    new = 0
    for v in raw:
        if v["id"] not in db:
            new += 1
        prev = db.get(v["id"], {})
        parsed = parse_description(v["description"])
        db[v["id"]] = {**prev, **v, **parsed}

    videos = sorted(db.values(), key=lambda x: x["published"], reverse=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[fetch] source={'api' if key else 'rss'} total={len(videos)} new={new}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"new={new}\n")


if __name__ == "__main__":
    main()
