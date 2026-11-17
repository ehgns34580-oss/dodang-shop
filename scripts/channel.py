#!/usr/bin/env python3
"""유튜브 채널의 '동영상'·'Shorts' 탭을 끝까지 스크롤해 전체 영상 ID 목록을 data/channel_ids.json 에 저장.
(Playwright 필요) 하루 1번 정도면 충분 — 새 영상은 RSS 로 30분마다 잡힘."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "channel_ids.json"
IDS_JS = r"""[...new Set([...document.querySelectorAll('a[href*="/watch?v="],a[href*="/shorts/"]')]
  .map(a => (a.getAttribute('href').match(/(?:v=|shorts\/)([\w-]{11})/) || [])[1]).filter(Boolean))]"""


def main():
    from playwright.sync_api import sync_playwright

    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"videos": [], "shorts": []}
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome" if "--chrome" in sys.argv else None, headless=True)
        page = browser.new_page(locale="ko-KR", viewport={"width": 1280, "height": 2000})
        for tab in ("videos", "shorts"):
            page.goto(f"https://www.youtube.com/channel/{C['channel_id']}/{tab}", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            last, stale = 0, 0
            for _ in range(150):
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(1200)
                n = len(page.evaluate(IDS_JS))
                stale = stale + 1 if n == last else 0
                last = n
                if stale >= 4:
                    break
            ids = page.evaluate(IDS_JS)
            # 스캔이 덜 됐을 때 기존 목록을 잃지 않도록 합집합
            out[tab] = ids + [i for i in prev.get(tab, []) if i not in ids]
            print(f"[channel] {tab}: {len(ids)}개 (누적 {len(out[tab])})")
        browser.close()
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
