#!/usr/bin/env python3
"""무신사 큐레이터샵 공개 페이지를 헤드리스 브라우저로 열고 끝까지 스크롤하면서,
페이지가 스스로 불러오는 큐레이션 목록(제목·큐레이션ID·상품 사진/이름/가격)을 기록해 data/curations.json 에 저장.
(Playwright 필요: pip install playwright && playwright install chromium)
실패하거나 결과가 비정상적으로 적으면 기존 파일을 유지.
"""
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "curations.json"
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SHOP = "https://www.musinsa.com/curator/s/" + urllib.parse.quote(C["curator_shop_title"])


def slim_goods(g):
    return {
        "goods_no": str(g.get("goodsNo")),
        "brand": g.get("brandName") or "",
        "name": g.get("goodsName") or "",
        "image": g.get("imageUrl") or "",
        "price": g.get("finalPrice") or g.get("price") or 0,
        "normal_price": g.get("normalPrice") or 0,
        "discount": g.get("finalDiscount") or g.get("salesRate") or 0,
        "sold_out": bool(g.get("isSoldOut")),
        "link": g.get("linkUrl") or "",
    }


def main():
    from playwright.sync_api import sync_playwright

    curations, popular = {}, []

    def on_response(r):
        u = r.url
        if "/affiliate/v2/curations" not in u:
            return
        try:
            j = r.json()
        except Exception:
            return
        data = j.get("data")
        if "popular-products" in u:
            items = data if isinstance(data, list) else (data or {}).get("list") or (data or {}).get("goodsItems") or (data or {}).get("goods") or []
            if items:
                popular[:] = [slim_goods(g) for g in items if isinstance(g, dict) and g.get("goodsNo")]
        elif isinstance(data, dict) and "list" in data:
            for c in data["list"]:
                if "curationId" not in c or c.get("isPublished") is False:
                    continue
                curations[c["curationId"]] = {
                    "id": c["curationId"],
                    "title": c.get("title") or "",
                    "description": c.get("description") or "",
                    "order": c.get("ordNo") or 0,
                    "goods": [slim_goods(g) for g in c.get("goodsItems") or []],
                }

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome" if "--chrome" in sys.argv else None, headless=True)
        page = browser.new_page(locale="ko-KR", viewport={"width": 1280, "height": 2400})
        page.on("response", on_response)
        page.goto(SHOP, wait_until="networkidle", timeout=60000)
        last, stale = 0, 0
        for _ in range(120):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(900)
            stale = stale + 1 if len(curations) == last else 0
            last = len(curations)
            if stale >= 5:
                break
        browser.close()

    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if len(curations) < max(5, len(prev.get("curations", [])) // 2):
        print(f"[curator] 수집 {len(curations)}개로 너무 적음 → 기존 데이터 유지", file=sys.stderr)
        return
    data = {
        "curations": sorted(curations.values(), key=lambda c: -c["order"]),
        "popular": popular or prev.get("popular", []),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[curator] 큐레이션 {len(curations)}개, 인기상품 {len(data['popular'])}개")


if __name__ == "__main__":
    main()
