#!/usr/bin/env python3
"""영상마다 유튜브가 만들어 두는 고화질 중간 장면 3장(숏폼 oar1~3, 롱폼 maxres1~3)을 받아
사람 자세 인식(MediaPipe)으로 '머리부터 발끝까지 다 나온 전신샷'을 골라 data/coordi.json 에 저장.
이미 검사한 영상은 건너뜀. (pip install mediapipe)
"""
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "data" / "videos.json"
OUT = ROOT / "data" / "coordi.json"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 400
UA = {"User-Agent": "Mozilla/5.0 (dodang-shop updater)"}

NOSE, L_ANKLE, R_ANKLE, L_HEEL, R_HEEL, L_HIP, R_HIP = 0, 27, 28, 29, 30, 23, 24


def frames(v):
    names = ["oar1", "oar2", "oar3"] if v.get("type") == "shorts" else ["maxres1", "maxres2", "maxres3"]
    return [(n, f"https://i.ytimg.com/vi/{v['id']}/{n}.jpg") for n in names]


def fullbody_score(lm):
    """0이면 전신 아님. 머리·골반·발목이 모두 잘 보이고, 머리~발목이 화면 세로의 55% 이상이면 점수."""
    vis = lambda i: getattr(lm[i], "visibility", 1.0) or 0.0
    ankle = max((L_ANKLE, R_ANKLE), key=vis)
    if vis(NOSE) < 0.5 or vis(ankle) < 0.5 or max(vis(L_HIP), vis(R_HIP)) < 0.5:
        return 0.0
    top, bottom = lm[NOSE].y, max(lm[ankle].y, lm[L_HEEL].y if vis(L_HEEL) > .5 else 0, lm[R_HEEL].y if vis(R_HEEL) > .5 else 0)
    span = bottom - top
    if span < 0.55 or bottom > 0.99 or top < 0.0:
        return 0.0
    center = (lm[L_HIP].x + lm[R_HIP].x) / 2
    return round(span * min(vis(NOSE), vis(ankle)) * (1 - abs(center - 0.5)), 3)


def main():
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions

    videos = json.loads(VIDEOS.read_text(encoding="utf-8"))
    videos = videos if isinstance(videos, list) else list(videos.values())
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [v for v in videos if v["id"] not in done][:LIMIT]
    if not todo:
        print("[coordi] 새로 검사할 영상 없음")
        return

    tmp = Path(tempfile.mkdtemp())
    model = tmp / "pose.task"
    model.write_bytes(urllib.request.urlopen(urllib.request.Request(MODEL_URL, headers=UA), timeout=60).read())
    opts = PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)), num_poses=1)
    found = 0
    with PoseLandmarker.create_from_options(opts) as det:
        for v in todo:
            best = None
            for name, url in frames(v):
                try:
                    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
                except Exception:
                    continue
                f = tmp / f"{v['id']}_{name}.jpg"
                f.write_bytes(data)
                try:
                    res = det.detect(mp.Image.create_from_file(str(f)))
                except Exception:
                    continue
                if res.pose_landmarks:
                    s = fullbody_score(res.pose_landmarks[0])
                    if s > 0 and (not best or s > best["score"]):
                        best = {"frame": name, "image": url, "score": s}
            done[v["id"]] = best or {}
            found += bool(best)
    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(1 for x in done.values() if x)
    print(f"[coordi] 이번에 {len(todo)}개 검사, 전신샷 {found}개 발견 (누적 {total}개)")


if __name__ == "__main__":
    main()
