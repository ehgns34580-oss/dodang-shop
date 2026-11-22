#!/usr/bin/env python3
"""코디샷에 박혀 있는 자막·제목 글자를 지워 깨끗한 코디 사진을 data/coordi_img/{영상ID}.jpg 로 저장.
1) EasyOCR 로 글자 위치 찾기  2) LaMa(AI 지우개)로 글자 자리를 주변 배경·옷에 맞게 채우기.
이미 처리한 영상은 건너뜀.  --pending : 처리할 게 있으면 종료코드 0, 없으면 1 (설치 전에 확인용)
(pip install torch easyocr simple-lama-inpainting)
"""
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "data" / "coordi.json"
IMG_DIR = ROOT / "data" / "coordi_img"
MIN_SCORE = 0.4
WIDTH = 720
VERSION = 1  # 지우는 방식이 바뀌면 올려서 전부 다시 처리
UA = {"User-Agent": "Mozilla/5.0 (dodang-shop updater)"}


def pending(meta):
    return [k for k, v in meta.items()
            if v and v.get("score", 0) >= MIN_SCORE
            and not (v.get("clean_v") == VERSION and (IMG_DIR / f"{k}.jpg").exists())]


def main():
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    todo = pending(meta)
    if "--pending" in sys.argv:
        print(f"[coordi_clean] 처리할 코디샷 {len(todo)}개")
        sys.exit(0 if todo else 1)
    if not todo:
        print("[coordi_clean] 새로 처리할 코디샷 없음")
        return

    import numpy as np
    import easyocr
    from PIL import Image, ImageDraw, ImageFilter
    from simple_lama_inpainting import SimpleLama

    reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    lama = SimpleLama()
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    cleaned = 0
    for vid in todo:
        m = meta[vid]
        try:
            raw = urllib.request.urlopen(urllib.request.Request(m["image"], headers=UA), timeout=30).read()
        except Exception as exc:
            print(f"[coordi_clean] {vid} 받기 실패: {exc}", file=sys.stderr)
            continue
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        boxes = reader.readtext(np.array(im), detail=1, paragraph=False, text_threshold=0.6, low_text=0.3)
        mask = Image.new("L", im.size, 0)
        d = ImageDraw.Draw(mask)
        n = 0
        for pts, _text, conf in boxes:
            if conf < 0.2:
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            h = max(ys) - min(ys)
            pad = max(6, int(h * 0.35))  # 글자 외곽선·그림자까지
            d.rectangle([min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad], fill=255)
            n += 1
        if n:
            mask = mask.filter(ImageFilter.MaxFilter(9))
            out = lama(im, mask)
            out = out.crop((0, 0, im.width, im.height)) if out.size != im.size else out
            cleaned += 1
        else:
            out = im
        out.save(IMG_DIR / f"{vid}.jpg", "JPEG", quality=84, optimize=True, progressive=True)
        m["clean_v"], m["texts"] = VERSION, n
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[coordi_clean] {len(todo)}개 처리, 글자 지운 사진 {cleaned}개")


if __name__ == "__main__":
    main()
