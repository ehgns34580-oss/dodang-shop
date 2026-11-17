# 도댕패션 착장정보 사이트

유튜브에 영상이 올라오면 **30분 안에 자동으로** 착장 정보 페이지가 생기고, 모든 제품 클릭은 **도댕 무신사 큐레이터샵**으로 연결되는 정적 사이트입니다.

### 연결 우선순위
1. 설명란 큐레이션 링크가 큐레이터샵에 살아있으면 → 그 큐레이션
2. 제목이 같은 큐레이션이 있으면 → 그 큐레이션
3. 설명란 제품명이 다른 큐레이션에 있으면 → 그 큐레이션
4. 큐레이션이 지워졌고 개별 상품 링크만 있으면 → 개별 링크 (불가피한 경우만)
5. 아무 정보 없으면 → 같은 주제 큐레이션을 '비슷한 추천템'으로

### 스크립트
- `scripts/fetch.py` 새 영상(RSS, 30분마다) + 상세(설명란·날짜·장면 미리보기)
- `scripts/channel.py` 채널 전체 영상 목록 스캔 (매일)
- `scripts/curator.py` 큐레이터샵 큐레이션 + 상품 사진/가격 (3시간마다)
- `scripts/resolve.py` 영상↔큐레이션 매칭, 롱폼 제품별 구간
- `scripts/build.py` 사이트 생성
서버·DB·비용 없이 GitHub Actions + GitHub Pages로 돌아갑니다.

```
YouTube 업로드 ─▶ (30분마다) scripts/fetch.py ─▶ data/videos.json ─▶ scripts/build.py ─▶ site/ ─▶ GitHub Pages
                       설명란 파싱                    + data/overrides.json(수동 보정)
```

## 페이지 구성
| 경로 | 내용 |
|---|---|
| `/` | 메인: LOOK / 최근 착용 제품 / SHORTS / VIDEO |
| `/looks.html` | 모든 코디 (롱폼은 `LOOK 1-1` 타임라인 단위, 숏폼은 영상 단위) |
| `/look/{id}.html` | 코디 상세: 해당 시점부터 재생되는 영상 + 카테고리별 착용 제품 |
| `/v/{영상ID}.html` | 영상 상세: 착용 제품 전체, 무신사 큐레이션, 코디 모아보기 |
| `/shorts.html`, `/videos.html` | 숏폼 / 롱폼 목록 |
| `/products.html` | 영상에 나온 모든 제품 (카테고리 필터 + 검색) |

## 자동으로 인식되는 설명란 형식
지금 롱폼 설명란 형식 그대로 인식합니다.

```
☑️ MODEL STATS: [ 도댕 183 / 71kg ]          ← 모델 정보

1) 미니멀 울 블렌드 발마칸 코트 : https://www.musinsa.com/curator/goods/4aJD7aw2   ← 제품명 : 링크
2) 니트 : https://www.musinsa.com/curator/goods/XXXX

https://www.musinsa.com/curator/shop/PR7sqA?curationId=...   ← 큐레이션 링크 (버튼으로 표시)

00:27 1) 미니멀 울 블렌드 발마칸 코트                     ← 타임라인
01:14 LOOK 1-1                                          ← 코디 단위 페이지 자동 생성 (1번 제품과 연결)
```

- 카테고리(OUTER/TOP/BOTTOM/SHOES/BAG/ACC/ETC)는 제품명 키워드로 자동 분류됩니다.
- 무신사 큐레이터 링크는 **그대로** 사용하므로 수수료 추적이 유지됩니다.
- 29cm·W컨셉·쿠팡 등 다른 쇼핑몰 링크도 `제품명 : 링크` 형식이면 인식합니다.

> 💡 **숏폼 팁** — 숏폼 설명란에 큐레이션 링크만 있으면 사이트에 "무신사 큐레이션에서 착장 보기" 버튼만 나옵니다.
> 착장을 사이트에 바로 보여주려면 숏폼 설명란에도 `OUTER 노이어 알파카 코트 : https://www.musinsa.com/curator/goods/...` 처럼 한 줄씩 적어주세요.

## 수동 보정: `data/overrides.json`
설명란에 못 넣은 착장, 카테고리 수정, 영상 숨기기 등은 GitHub 웹에서 이 파일만 고치면 됩니다 (저장하면 자동 재배포).

```json
{
  "ZeArmCftFXo": {
    "curation_id": "01M7J37RP7P00NM221H1R47Q0E",
    "products": [
      {"category": "OUTER", "name": "노이어 알파카 부클 맥시 코트 (브라운)", "url": "https://www.musinsa.com/curator/goods/XXXX"}
    ],
    "looks": [
      {"label": "LOOK 1", "t": 3, "products": [ ... ]}
    ],
    "hidden": false
  }
}
```
영상 ID = 유튜브 주소의 `shorts/` 또는 `v=` 뒤 11자리.

## 처음 설정 (10분)
1. GitHub에서 새 저장소 생성 (예: `dodang-shop`) 후 이 폴더를 push
   ```bash
   git init && git add . && git commit -m "init" && git branch -M main
   git remote add origin https://github.com/<아이디>/dodang-shop.git && git push -u origin main
   ```
2. 저장소 **Settings → Pages → Build and deployment → Source: GitHub Actions**
3. **Actions** 탭 → "새 영상 자동 업데이트 & 배포" → **Run workflow** (첫 배포)
4. 완료되면 `https://<아이디>.github.io/dodang-shop/` 에서 확인

### (선택) 과거 영상 전부 불러오기
RSS는 최근 15개만 줍니다. 전체 백필을 원하면 Google Cloud Console에서 **YouTube Data API v3** 키를 발급받아
**Settings → Secrets and variables → Actions → New repository secret** 에 `YT_API_KEY` 로 등록하세요. (무료 할당량으로 충분)

### (선택) 내 도메인 연결
도메인(예: `dodangshop.com`) 구매 후 Settings → Pages → Custom domain 에 입력하고, DNS에 GitHub Pages용 레코드를 추가합니다.

## 로컬에서 미리보기
```bash
python3 scripts/fetch.py && python3 scripts/build.py && python3 -m http.server -d site 8000
```
