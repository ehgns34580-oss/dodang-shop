#!/usr/bin/env python3
"""인포크링크(link.inpock.co.kr/do_dang)에 걸어둔 '영상 제목 → 큐레이션 링크' 목록을 data/inpock.json 에 저장.
설명란에 링크가 없는 영상도 여기 제목으로 큐레이션을 찾을 수 있음. (표준 라이브러리만)"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "inpock.json"


def main():
    url = C.get("inpock_url")
    if not url:
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (dodang-shop updater)"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        blocks = json.loads(m.group(1))["props"]["pageProps"]["blocks"]
    except Exception as exc:
        print(f"[inpock] 실패: {exc}", file=sys.stderr)
        return
    links = []
    for b in blocks:
        u, t = b.get("url") or "", (b.get("title") or "").strip()
        if "musinsa.com" not in u or not t:
            continue
        cid = re.search(r"curationId=([0-9A-Z]{26})", u)
        title = re.sub(r"^\s*\d+\s*번\s*", "", t)
        title = re.sub(r"^[✅☑️\s]+", "", title).strip()
        links.append({"title": title, "url": u, "curation_id": cid.group(1) if cid else None})
    if links:
        OUT.write_text(json.dumps(links, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[inpock] 링크 {len(links)}개")


if __name__ == "__main__":
    main()
