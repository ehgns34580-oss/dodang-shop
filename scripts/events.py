#!/usr/bin/env python3
"""무신사 무진장(블프) 공개 행사 페이지를 헤드리스 브라우저로 열고,
페이지가 스스로 불러오는 행사 구성 파일(쿠폰·브랜드데이·라이브 일정·이벤트)을 기록해 data/events.json 에 저장.
행사 페이지 주소는 무신사 메인에 걸린 무진장 배너에서 찾고, 없으면 config.json 의 event_url 을 씀.
실패하거나 아무것도 못 읽으면 기존 파일을 유지. (Playwright 필요)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "events.json"
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
HOME = "https://www.musinsa.com/main/musinsa/recommend"
FALLBACK = C.get("event_url") or "https://www.musinsa.com/campaign/mujinjangsale/teasing"


def tt(m):
    t = (m.get("content") or {}).get("titleTimer") or {}
    return (t.get("title") or "").strip(), (t.get("subTitle") or "").strip()


def parse(modules):
    coupons, brand_days, lives, benefits = [], [], [], []
    for m in sorted(modules, key=lambda m: m.get("seq") or 0):
        kind, c = m.get("moduleType"), m.get("content") or {}
        title, sub = tt(m)
        base = {"start": m.get("displayStartDt"), "end": m.get("displayEndDt")}
        if kind == "KR_COUPON":
            coupons.append({**base, "title": title or c.get("couponName") or "", "name": c.get("couponName") or "", "sub": sub})
        elif kind == "CONTENTS_LIST":
            tabs = []
            for tab in c.get("moduleTabList") or []:
                brands = [
                    {"name": (x.get("title") or "").strip(), "desc": (x.get("subTitle") or "").strip(),
                     "label": (x.get("label") or "").strip(), "image": x.get("imageUrl") or ""}
                    for x in tab.get("contentsList") or [] if x.get("title")
                ]
                if brands:
                    tabs.append({"name": (tab.get("tabName") or "").strip(), "brands": brands})
            if tabs:
                brand_days.append({**base, "title": title or m.get("anchorTitle") or "브랜드데이", "tabs": tabs})
        elif kind == "LIVECOMMERCE":
            for x in c.get("chartList") or []:
                raw = (x.get("title") or "").strip()
                parts = re.split(r"\s*[|ㅣ]\s*", raw, maxsplit=1)
                brand, desc = (parts[0], parts[1]) if len(parts) == 2 else (raw, "")
                link = x.get("link") or ""
                if link.startswith("/"):
                    link = "https://www.musinsa.com" + link
                lives.append({
                    "brand": brand.strip(), "desc": (desc or x.get("subTitle") or "").strip(),
                    "date": x.get("onAirDateText") or "", "time": (x.get("onAirTimeText") or "").strip(),
                    "label": x.get("labelType") or "", "image": x.get("thumbnail") or "", "link": link,
                })
        elif title and kind in ("IMAGE", "IMAGEGOODS", "LIMITED_SALE", "BRAND_TOGGLE"):
            benefits.append({**base, "title": title, "sub": sub, "tag": m.get("anchorTitle") or ""})
    seen, uniq = set(), []
    for l in lives:
        k = (l["brand"], l["date"], l["time"])
        if k not in seen:
            seen.add(k)
            uniq.append(l)
    return coupons, brand_days, uniq, benefits


def main():
    from playwright.sync_api import sync_playwright

    modules = {}

    def on_response(r):
        if "campaign_service/rcb/cpcms" not in r.url or "module_" not in r.url:
            return
        try:
            j = r.json()
        except Exception:
            return
        if isinstance(j, dict) and j.get("uuid"):
            modules[j["uuid"]] = j

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome" if "--chrome" in sys.argv else None, headless=True)
        page = browser.new_page(locale="ko-KR", viewport={"width": 1280, "height": 2400})
        url = FALLBACK
        try:
            page.goto(HOME, wait_until="networkidle", timeout=60000)
            hrefs = page.eval_on_selector_all("a[href*='/campaign/mujinjang']", "els => els.map(e => e.href)")
            if hrefs:
                url = hrefs[0].split("?")[0]
        except Exception as exc:
            print(f"[events] 메인 열기 실패: {exc}", file=sys.stderr)
        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=60000)
        for _ in range(25):
            page.evaluate("window.scrollBy(0, 1800)")
            page.wait_for_timeout(500)
        page.wait_for_timeout(1500)
        name = page.title().split("|")[0].strip()
        text = page.inner_text("body")
        browser.close()

    coupons, brand_days, lives, benefits = parse(modules.values())
    if not (coupons or brand_days or lives):
        print(f"[events] {url} 에서 행사 정보를 못 읽음 → 기존 데이터 유지", file=sys.stderr)
        return
    period = re.search(r"\d{1,2}\.\d{1,2}\([^)]\)\s*-\s*\d{1,2}\.\d{1,2}\([^)]\)", text)
    data = {
        "name": name, "url": url, "period": period.group(0) if period else "",
        "fetched": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "coupons": coupons, "brand_days": brand_days, "lives": lives, "benefits": benefits,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[events] {name}: 쿠폰 {len(coupons)}, 브랜드데이 {sum(len(t['brands']) for b in brand_days for t in b['tabs'])}, 라이브 {len(lives)}, 이벤트 {len(benefits)}")


if __name__ == "__main__":
    main()
