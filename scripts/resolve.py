"""영상 ↔ 무신사 큐레이션 매칭 + 롱폼 타임라인 구간 정리 (build.py 에서 사용, 표준 라이브러리만)

연결 우선순위 (큐레이터샵 유입 최우선)
 1. 설명란의 curationId 가 큐레이터샵에 살아있음           → match="exact"
 2. overrides.json 의 curation_id                          → match="exact"
 3. 영상 제목 ≈ 큐레이션 제목                               → match="title"
 4. 설명란 제품명이 다른 큐레이션에 들어있음                → 그 큐레이션으로 연결 (제품별)
 5. 큐레이션이 지워졌고 설명란에 개별 상품 링크만 있음      → 개별 링크 (불가피한 경우)
 6. 아무 정보 없음                                         → 같은 주제 큐레이션을 '비슷한 추천템'으로 (match="topic")
"""
import re
import unicodedata
from difflib import SequenceMatcher

GOODS_RE = re.compile(r"https?://(?:www\.)?musinsa\.com/(?:curator/goods/[A-Za-z0-9_-]+|products/\d+|app/goods/\d+)[^\s)]*")
OTHER_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)+[a-z]{2,}/[^\s)]*")
CUR_ID_RE = re.compile(r"curationId=([0-9A-Z]{26})")
TIME_RE = re.compile(r"^\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[•·▪︎\-\*✔️☑️]*\s*(OUTER|TOP|INNER|PANTS|BOTTOM|SHOES|BAG|BELT|ACC|ETC|CAP|HAT|NECKLACE|RING|GLASSES|SOCKS|MUFFLER|SCARF)\s*[:：]\s*(.+?)\s*$", re.I)
NUMBERED_RE = re.compile(r"^\s*(\d+)\s*[).]\s*(.+?)\s*[:：]\s*(https?://\S+)")
SKIP_LABEL = re.compile(r"인트로|intro|아웃트로|outro|preview|프리뷰|오프닝|구독자\s*이벤트|이벤트|마무리|엔딩|ending|광고|안내|쿠폰|기획전|꿀팁|과정|관리|사이즈|가격", re.I)
LOOK_LABEL = re.compile(r"^\s*look\s*\d", re.I)

CAT_MAP = {"PANTS": "BOTTOM", "INNER": "TOP", "BELT": "ACC", "CAP": "ACC", "HAT": "ACC", "NECKLACE": "ACC", "RING": "ACC",
           "GLASSES": "ACC", "SOCKS": "ACC", "MUFFLER": "ACC", "SCARF": "ACC"}
CATEGORIES = [
    ("OUTER", ["코트", "자켓", "재킷", "무스탕", "블루종", "패딩", "점퍼", "후리스", "플리스", "가디건", "베스트", "조끼", "아우터", "파카", "트렌치", "봄버", "트러커", "블레이저", "jacket", "coat", "cardigan", "blouson", "trucker"]),
    ("TOP", ["니트", "티셔츠", "긴팔", "반팔", "셔츠", "맨투맨", "후드", "스웨터", "스웻", "카라", "폴로", "터틀넥", "헨리넥", "슬리브", "이너", "knit", "tee", "shirt", "sleeve"]),
    ("BOTTOM", ["팬츠", "슬랙스", "데님", "청바지", "치노", "카고", "조거", "쇼츠", "반바지", "트라우저", "pants", "denim", "jean", "trouser", "chino"]),
    ("SHOES", ["슈즈", "스니커즈", "운동화", "부츠", "로퍼", "더비", "구두", "샌들", "슬리퍼", "shoes", "sneaker", "boot", "loafer"]),
    ("BAG", ["백팩", "가방", "토트", "크로스백", "숄더백", "메신저", "쇼퍼백", "bag", "messenger"]),
    ("ACC", ["벨트", "링", "반지", "목걸이", "팔찌", "목도리", "머플러", "스카프", "비니", "모자", "캡", "양말", "장갑", "안경", "선글라스", "시계", "belt", "ring", "necklace", "beanie", "cap"]),
]
CAT_ORDER = ["OUTER", "TOP", "BOTTOM", "SHOES", "BAG", "ACC", "ETC"]
SYNONYMS = {
    "반팔": ["반팔", "하프 슬리브", "하프슬리브", "숏 슬리브", "숏슬리브", "short sleeve", "반소매"],
    "바람막이": ["바람막이", "윈드", "아노락", "windbreaker"],
    "청바지": ["데님", "청바지", "denim", "jean"],
    "바지": ["팬츠", "슬랙스", "데님", "치노", "pants"],
    "카라": ["카라", "폴로", "collar"],
    "긴팔": ["긴팔", "롱 슬리브", "롱슬리브", "long sleeve"],
    "롱슬리브": ["롱 슬리브", "롱슬리브", "긴팔", "long sleeve"],
    "신발": ["슈즈", "로퍼", "구두", "스니커즈", "운동화", "부츠", "더비"],
    "구두": ["구두", "더비", "로퍼", "옥스포드"],
    "가방": ["가방", "백", "bag"],
    "셔츠": ["셔츠", "shirt"],
    "니트": ["니트", "knit"],
    "스트라이프": ["스트라이프", "stripe"],
    "무지": ["무지", "베이직", "basic", "에센셜"],
}
TOPIC_WORDS_EXTRA = ["샌들", "바람막이", "스트라이프", "롱슬리브", "무지", "블레이저", "수트", "셋업", "로퍼", "이지팬츠", "와이드", "카고",
                     "조거", "후드", "맨투맨", "폴로", "카라티", "반바지", "쇼츠", "모자", "비니", "안경", "시계", "목걸이", "반지", "양말",
                     "백팩", "크로스백", "점퍼", "베스트", "체크", "옥스포드", "린넨", "스웨트"]
TOPIC_WORDS = ["무스탕", "블루종", "발마칸", "트러커", "레더", "스웨이드", "가디건", "패딩", "경량", "코듀로이", "후리스", "플리스", "봄버", "크롭",
               "코트", "니트", "헨리넥", "셔츠", "청바지", "생지", "데님", "슬랙스", "치노", "바지", "반팔", "긴팔", "카라", "구두", "운동화", "부츠",
               "신발", "가방", "벨트", "머플러", "자켓", "아우터", "하객"]


def guess_category(name):
    low = name.lower()
    for cat, words in CATEGORIES:
        if any(w.lower() in low for w in words):
            return cat
    return "ETC"


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[\[\(（【].*?[\]\)）】]", " ", s)
    s = re.sub(r"[^0-9a-z가-힣]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return {t for t in norm(s).split() if len(t) >= 2}


def topic_terms(title):
    """영상 제목 → 상품 검색어 목록 (동의어 포함)"""
    words = [w for w in TOPIC_WORDS + TOPIC_WORDS_EXTRA if w in (title or "")]
    if any(w not in ("코트", "자켓", "아우터", "바지") for w in words):
        words = [w for w in words if w != "아우터"]
    terms = []
    for w in words:
        for t in SYNONYMS.get(w, [w]):
            if t not in terms:
                terms.append(t)
    return words, terms


def topics(s):
    found = {w for w in TOPIC_WORDS if w in (s or "")}
    # '코트'는 '발마칸 코트'처럼 겹치므로 상위어 제거
    if found - {"코트", "자켓", "아우터", "바지", "데님"}:
        found -= {"아우터"}
    return found


def to_seconds(ts):
    n = 0
    for part in ts.split(":"):
        n = n * 60 + int(part)
    return n


# ---------------------------------------------------------------- description parsing
def parse_sections(desc):
    """타임라인 구간 단위로 쪼갬: 각 구간의 큐레이션ID·상품링크·불릿 제품명을 모음. 같은 시간은 합침."""
    lines = (desc or "").splitlines()
    sections, cur = {}, None
    head = {"curation_ids": [], "goods": [], "bullets": []}
    for line in lines:
        tm = TIME_RE.match(line)
        if tm and not OTHER_RE.search(tm.group(2)):
            t = to_seconds(tm.group(1))
            cur = sections.setdefault(t, {"t": t, "label": tm.group(2).strip(), "curation_ids": [], "goods": [], "bullets": [], "other_links": []})
            # 라벨 안의 "1) 제품 : 링크"
            continue
        target = cur if cur is not None else head
        for cid in CUR_ID_RE.findall(line):
            if cid not in target["curation_ids"]:
                target["curation_ids"].append(cid)
        for m in GOODS_RE.finditer(line):
            before = re.sub(r"^\s*\d+\s*[).]\s*", "", line[: m.start()]).strip(" :：-")
            target["goods"].append({"url": m.group(0).rstrip(".,)"), "name": before})
        bm = BULLET_RE.match(line)
        if bm:
            cat = bm.group(1).upper()
            target["bullets"].append({"category": CAT_MAP.get(cat, cat if cat in CAT_ORDER else "ETC"), "name": bm.group(2).strip()})
        if cur is not None and "curationId" not in line and not GOODS_RE.search(line):
            for m in OTHER_RE.finditer(line):
                if "youtube.com" not in m.group(0) and "forms.gle" not in m.group(0) and "instagram" not in m.group(0):
                    cur["other_links"].append(m.group(0))
    out = sorted(sections.values(), key=lambda s: s["t"])
    return head, out


# ---------------------------------------------------------------- matching
class Catalog:
    def __init__(self, data, shop_url, inpock=None):
        self.shop_url = shop_url
        self.inpock = inpock or []
        self.curations = data.get("curations", [])
        self.popular = data.get("popular", [])
        self.by_id = {c["id"]: c for c in self.curations}
        self.goods_index = []  # (tokens, goods, curation)
        for c in self.curations:
            for g in c["goods"]:
                self.goods_index.append((tokens(g["brand"] + " " + g["name"]), g, c))

    def link(self, cur):
        return f"{self.shop_url}?curationId={cur['id']}"

    def by_title(self, title):
        nt, tt = norm(title), tokens(title)
        vt = topics(title)
        best, score = None, 0
        for c in self.curations:
            ct = topics(c["title"])
            if vt and ct and not (vt & ct):
                continue  # 핵심 품목이 다르면 제외 (반팔 영상 ↔ 코트 큐레이션 X)
            if bool(vt) != bool(ct):
                continue
            r = SequenceMatcher(None, nt, norm(c["title"])).ratio()
            j = len(tt & tokens(c["title"])) / max(1, len(tt | tokens(c["title"])))
            s = max(r, j + 0.15)
            if s > score:
                best, score = c, s
        return best if score >= 0.66 else None

    def find_goods(self, name, prefer=None):
        """제품명 → 큐레이터샵 안의 같은 상품. 흔한 단어(울·코트 등)만 겹치는 오매칭을 막기 위해 엄격하게."""
        nt = tokens(name)
        if len(nt) < 2:
            return None, None
        best, bc, score = None, None, 0
        for gt, g, c in self.goods_index:
            inter = nt & gt
            if not inter:
                continue
            s = len(inter) / len(nt)
            brand_hit = bool(tokens(g["brand"]) & nt)
            ok = (brand_hit and s >= 0.6) or (s >= 0.8 and len(inter) >= 3 and len(inter) / len(gt) >= 0.75)
            if not ok:
                continue
            s += 0.2 * brand_hit + (0.05 if prefer and c["id"] == prefer["id"] else 0)
            if s > score:
                best, bc, score = g, c, s
        return best, bc

    def by_inpock(self, title):
        """인포크링크에 걸어둔 '영상 제목 → 큐레이션' (제목이 거의 같아야 함)"""
        nt = norm(title)
        best, score = None, 0
        for it in self.inpock:
            r = SequenceMatcher(None, nt, norm(it["title"])).ratio()
            if r > score:
                best, score = it, r
        if best and score >= 0.8 and best.get("curation_id") in self.by_id:
            return self.by_id[best["curation_id"]]
        return None

    def topic_goods(self, title, limit=12):
        """영상 주제와 맞는 상품을 큐레이터샵 전체 상품에서 골라옴 (개별 상품 링크용)"""
        words, terms = topic_terms(title)
        if not terms:
            return []
        scored, seen = [], set()
        for _, g, c in self.goods_index:
            if g["goods_no"] in seen or g.get("sold_out"):
                continue
            name = (g["brand"] + " " + g["name"]).lower()
            hits = sum(1 for t in terms if t.lower() in name)
            if hits:
                seen.add(g["goods_no"])
                # 첫 번째(가장 구체적인) 주제어가 들어간 상품 우선
                primary = any(t.lower() in name for t in SYNONYMS.get(words[0], [words[0]]))
                scored.append((primary, hits, g, c))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [(g, c) for _, _, g, c in scored[:limit]]

    def by_topic(self, title):
        t = title
        for w in TOPIC_WORDS:
            if w in t:
                cands = [c for c in self.curations if w in c["title"]]
                if cands:
                    return max(cands, key=lambda c: (("블프" in c["title"]) * 0, len(c["goods"])))
        return None


def item_from_goods(g, link, category=None):
    return {"name": g["name"], "brand": g["brand"], "image": g["image"], "price": g["price"], "discount": g["discount"],
            "category": category or guess_category(g["name"]), "link": link, "sold_out": g.get("sold_out", False)}


def resolve_video(v, cat: Catalog, override=None):
    """영상에 curation / items / sections / match 를 채워 넣음"""
    override = override or {}
    head, sections = parse_sections(v.get("description", ""))
    all_ids = head["curation_ids"] + [cid for s in sections for cid in s["curation_ids"]]
    alive = [cid for cid in all_ids if cid in cat.by_id]

    curation, match = None, None
    if override.get("curation_id") in cat.by_id:
        curation, match = cat.by_id[override["curation_id"]], "exact"
    elif alive:
        curation, match = cat.by_id[alive[0]], "exact"
    elif cat.by_inpock(v.get("title", "")):
        curation, match = cat.by_inpock(v.get("title", "")), "exact"
    else:
        c = cat.by_title(v.get("title", ""))
        if c:
            curation, match = c, "title"

    url_names = {g["url"]: g["name"] for g in head["goods"] + [g for sc in sections for g in sc["goods"]] if g["name"]}

    def items_for(sec_or_head, sec_curation):
        """구간(또는 전체)의 제품 목록: 큐레이션 상품으로 연결 가능한 건 큐레이션 링크, 아니면 개별 링크"""
        out = []
        names = [(b["name"], b["category"], None) for b in sec_or_head["bullets"]]
        names += [(g["name"] or url_names.get(g["url"], ""), None, g["url"]) for g in sec_or_head["goods"]]
        seen_urls = set()
        uniq = []
        for name, category, url in names:
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            uniq.append((name, category, url))
        named_urls = {u for n, _, u in uniq if n and u}
        uniq = [(n, c, u) for n, c, u in uniq if n or u not in named_urls]
        for name, category, url in uniq:
            g, c = cat.find_goods(name, prefer=sec_curation) if name else (None, None)
            if g:
                out.append(item_from_goods(g, cat.link(c), category))
            elif url:
                out.append({"name": name or "착용 제품", "brand": "", "image": "", "price": 0, "discount": 0,
                            "category": category or guess_category(name), "link": url, "direct": True})
            elif name:
                out.append({"name": name, "brand": "", "image": "", "price": 0, "discount": 0,
                            "category": category or guess_category(name), "link": cat.shop_url, "direct": False})
        return out

    # 영상 전체 제품
    items = []
    if curation:
        items = [item_from_goods(g, cat.link(curation)) for g in curation["goods"]]
    else:
        merged = {"bullets": head["bullets"] + [b for s in sections for b in s["bullets"]],
                  "goods": head["goods"] + [g for s in sections for g in s["goods"]]}
        items = items_for(merged, None)
        if items:
            match = "items"
        else:
            picks = cat.topic_goods(v.get("title", ""))
            if picks:
                match = "topic"
                curation = cat.by_topic(v.get("title", ""))
                items = [{**item_from_goods(g, g.get("link") or cat.link(c)), "direct": True} for g, c in picks]
            else:
                match = None
                items = [{**item_from_goods(g, g.get("link") or cat.shop_url), "direct": True} for g in cat.popular]
    if override.get("products"):
        items = [{"name": p["name"], "brand": p.get("brand", ""), "image": p.get("image", ""), "price": 0, "discount": 0,
                  "category": p.get("category") or guess_category(p["name"]), "link": p.get("url") or (cat.link(curation) if curation else cat.shop_url)}
                 for p in override["products"]]
        match = match or "manual"

    # 롱폼 구간: 제품 설명 시작 시점 기준 카드
    secs = []
    if v.get("type") == "video":
        numbered = {}
        for line in (v.get("description") or "").splitlines():
            m = NUMBERED_RE.match(line)
            if m:
                numbered[int(m.group(1))] = (m.group(2).strip(), m.group(3))
        for s in sections:
            label = s["label"]
            has_data = s["curation_ids"] or s["goods"] or s["bullets"]
            if SKIP_LABEL.search(label) and not has_data:
                continue
            if LOOK_LABEL.match(label) and not has_data and secs and secs[-1].get("kind") == "product":
                secs[-1]["sub"].append({"t": s["t"], "label": label})  # LOOK 1-1 등은 직전 제품 구간에 붙임
                continue
            sec_cur = next((cat.by_id[c] for c in s["curation_ids"] if c in cat.by_id), None) or (curation if match == "exact" else None)
            sec_items = items_for(s, sec_cur)
            nm = re.match(r"^\s*(\d+)\s*[).]\s*(.+)$", label)
            if not sec_items and nm and int(nm.group(1)) in numbered:
                name, url = numbered[int(nm.group(1))]
                g, c = cat.find_goods(name, prefer=sec_cur)
                sec_items = [item_from_goods(g, cat.link(c)) if g else {"name": name, "brand": "", "image": "", "price": 0, "discount": 0,
                             "category": guess_category(name), "link": (cat.link(sec_cur) if sec_cur else url), "direct": not sec_cur}]
            if not sec_items:
                # 라벨 자체가 제품명인 경우 (예: "아우터1 | 쿠어 - 파일럿 레더 카라 점퍼")
                g, c = cat.find_goods(re.sub(r"^.*?\|", "", label), prefer=sec_cur)
                if g:
                    sec_items = [item_from_goods(g, cat.link(c))]
            clean = re.sub(r"^\s*\d+\s*[).]\s*", "", label)
            kind = "look" if LOOK_LABEL.match(label) else "product"
            if not sec_items and kind == "product":
                if not s["curation_ids"] or SKIP_LABEL.search(label):
                    continue  # 제품 정보 없는 일반 챕터는 카드로 만들지 않음
                pname = re.sub(r"^.*?\|\s*", "", label).strip(" -")
                sec_items = [{"name": pname, "brand": "", "image": "", "price": 0, "discount": 0,
                              "category": guess_category(pname), "link": cat.link(sec_cur) if sec_cur else cat.shop_url}]
            clean = re.sub(r"^\s*(아우터|상의|바지|하의|신발|가방|악세서리)\s*\d*\s*\|\s*", "", clean)
            secs.append({
                "t": s["t"], "label": clean, "raw_label": label,
                "kind": kind,
                "items": sec_items,
                "link": cat.link(sec_cur) if sec_cur else (cat.link(curation) if curation and match != "topic" else None),
                "sub": [],
            })
        for i, s in enumerate(secs):
            s["end"] = secs[i + 1]["t"] if i + 1 < len(secs) else (v.get("length") or s["t"] + 60)

    # 롱폼: 구간별 제품을 합쳐 영상 전체 착장으로 (여러 큐레이션이면 대표 링크는 큐레이터샵 메인)
    sec_items = [it for sc in secs for it in sc["items"]]
    curation_link = cat.link(curation) if curation else None
    if sec_items:
        seen, merged = set(), []
        for it in sec_items:
            key = (it.get("brand", ""), it["name"])
            if key not in seen:
                seen.add(key)
                merged.append(it)
        items = merged
        links = {sc["link"] for sc in secs if sc["link"]}
        curation_link = links.pop() if len(links) == 1 else (None if not links else cat.shop_url)
        if match in (None, "topic"):
            match = "items"

    v["curation"] = curation
    v["curation_link"] = curation_link
    v["match"] = match
    v["items"] = items
    v["sections"] = secs
    return v
