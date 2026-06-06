# 솔라핏 데이터 파이프라인

> 소형태양광 입지 추천 + 조례 Q&A 서비스 (RAG 기반)
> 프로젝트 개요·아키텍처는 [HANDOFF.md](./HANDOFF.md) 참고.

---

## 🚀 Quick Start (팀원용)

### 1) 코드 받기
```bash
cd C:\Projects          # 프로젝트를 받을 상위 폴더 (원하는 위치로)
git clone https://github.com/irishsun51/solarfit.git
cd solarfit             # → C:\Projects\solarfit 에 코드가 받아짐
```

### 2) 의존성 설치
```bash
pip install streamlit chromadb openai requests
```

### 3) API 키 설정
```bash
copy ini/.env.example ini/.env
```
`ini/.env` 파일을 메모장으로 열고 다음 값 입력:
```
KEPCO_API_KEY=발급받은_40자리키
LAW_API_KEY=OPEN_LAW_API
OPENAI_API_KEY=sk-proj-...
```
- **OpenAI 키 필수** (임베딩·LLM 답변에 사용)
- KEPCO·LAW 키는 데이터 재수집 시에만 필요

### 4) 데이터 받기 (선택 1 또는 2)

**선택 1 — 미리 적재된 DB 사용 (빠름, 추천)**
- 📦 **db.zip 다운로드**: https://drive.google.com/file/d/1ZXVjhcmcAT6Ly1sCFesNPE2B4LNSr3Iq/view?usp=drive_link
- 압축을 풀어 프로젝트 루트에 `db/` 폴더로 놓기
  → `db/solarfit.db` + `db/chroma_db/` 준비됨 → 바로 실행 가능 (OpenAI 키만 있으면 됨)

**선택 2 — 처음부터 적재 (OpenAI 비용 약 100원)**
```bash
python scripts/build_region.py
python scripts/init_db.py
python scripts/build_irradiance.py
python scripts/collect_ordinance.py --keywords 태양광 --scope chungnam --bodies
python scripts/build_ordinance_vectors.py
```

### 5) 실행
```bash
python -m streamlit run pages/site_diagnosis.py --server.port 9001 --browser.gatherUsageStats false
```

브라우저: http://localhost:9001 (검색창 하나로 동작 — 사이드바 없음)
- **지번** 입력 (예: `충남 논산시 부적면 충곡리 200`) → 부지 단일 진단
- **시군구명** 포함 질문 (예: `당진에 변전소 여유 있는 부지 있어?`) → 지역 단위 진단
- 그 외 질문 (예: `충남에서 규제가 느슨한 곳 추천해줘`) → 충남 추천 랭킹
- (구버전 조례 Q&A 화면 `solarfit.py`는 미사용 — 메인은 `pages/site_diagnosis.py`)

### 6) 사용 모델 (참고)
- 임베딩: `text-embedding-3-small` (OpenAI, 1536차원)
- LLM: `gpt-4o-mini` (OpenAI, 스트리밍)
- 벡터DB: ChromaDB (로컬, 무료)
- 관계형DB: SQLite (로컬, 무료)

질문당 비용: 약 0.9원

### (선택) DB 확인 도구 — DB Browser for SQLite
- `db/solarfit.db`(SQLite) 내용을 GUI로 열어보고 싶을 때 설치:
  - https://sqlitebrowser.org/dl/ → **"DB Browser for SQLite - Standard installer for 64-bit Windows"**
- `region` · `irradiance` · `ordinance` 테이블을 직접 조회·검색할 때 편리합니다.
- (벡터 DB인 `db/chroma_db/`는 이 도구로 안 열립니다 — 그건 ChromaDB 전용 포맷)

---

## 🔄 소스 변경 적용 (git)

코드를 수정한 뒤 GitHub에 반영하는 순서 (PowerShell):

```powershell
cd C:\Projects\SolarFit
git add .                      # 변경 파일 스테이징 (특정 파일만: git add solarfit.py)
git commit -m "수정 내용 요약"
git push                       # origin/main 에 반영
```

- `db/`, `ini/.env`, 원본 데이터(일사량·행정코드)는 `.gitignore`로 **자동 제외**됩니다.
- `LF will be replaced by CRLF` 경고는 Windows 줄바꿈 자동변환으로 **무해**합니다(무시).

**협업(권장)** — 각자 브랜치에서 작업 → push → Pull Request:

```powershell
git checkout -b 기능명          # 새 브랜치 생성
# ... 작업 ...
git add .; git commit -m "..."; git push -u origin 기능명
```

> `main`은 항상 동작하는 상태로 유지하고, 변경은 브랜치 → PR로 합치는 것을 권장합니다.

### 최신 코드 받기 (다른 사람이 push한 것)

```powershell
cd C:\Projects\SolarFit
git pull                       # origin/main 최신 받기
```

- **처음이면 `git clone`, 이미 받은 뒤면 `git pull`만** 하면 됩니다.
- `db/`(DB·벡터)는 git에 없으니, **DB가 갱신됐으면 Drive에서 `db.zip`을 다시 받아** 교체하세요.
- 내가 수정한 게 있는데 `pull`이 막히면(충돌) → 먼저 내 변경을 `commit` 하거나, 메시지 보고 알려주세요.

---

## 1. 폴더 구조

```
SolarFit/
├── HANDOFF.md / README.md / PROGRESS.md / ARCHITECTURE.md   문서
├── solarfit.py                     (구버전) 조례 Q&A 화면 — 현재 미사용
├── requirements.txt                의존성 (버전 고정)
├── .gitignore
│
├── ini/                            설정 (★ .env 는 커밋 금지)
│   ├── .env                        API 키
│   └── .env.example                키 템플릿 (커밋됨)
│
├── db/                             DB (★ git 제외 → Google Drive 공유)
│   ├── solarfit.db                 SQLite (region/irradiance/ordinance)
│   └── chroma_db/                  ChromaDB 벡터 인덱스 (4,251 청크)
│
├── log/                            로그 (result_*.log + API_<라벨>_<날짜>.log 자동 생성)
├── .streamlit/config.toml          UI 다크 테마
├── pages/
│   └── site_diagnosis.py          ★ 메인 엔트리 — 입지·수익·추천 진단 (지번/시군구/추천 라우팅)
│
├── data/                           데이터 (원본·가공은 git 제외, eval만 포함)
│   ├── 행정코드/                    code.go.kr 법정동코드
│   ├── 일사량/                      기상청 ASOS 월자료·관측소 메타
│   ├── SMP_REC/                    SMP·REC 단가 자료 (CSV·이미지)
│   ├── raw/kepco_dgen/             KEPCO API 응답 (지역별 JSON)
│   ├── land_use/                   VWorld 토지이용 시연 캐시 ({pnu}.json)
│   ├── byeolpyo/setback.json       충남 시군구별 이격 규제 데이터셋 (조문+별표 HWP)
│   ├── processed/region.csv        시군구 정규화 결과 (229건)
│   └── eval/                       평가 골드셋·결과 (★ git 포함)
│
├── src/
│   ├── solarfitRag.py              RAG (하이브리드 검색 + 답변 + 로깅)
│   ├── diagnose.py                 입지진단 diagnose(주소)·추천 recommend()·계통 get_grid()
│   ├── revenue.py                  수익 계산 (SMP/REC/발전량/투자지표)
│   └── api/                        API 클라이언트
│       ├── client.py               공통 베이스 (재시도/rate limit/API 로깅)
│       ├── kepco_dgen.py           KEPCO 분산전원
│       ├── law_go_kr.py            국가법령정보
│       └── land_use.py             VWorld 토지이용계획 (지번→PNU·용도지역·농지)
│
└── scripts/                        일회성 데이터 처리 스크립트
    ├── build_region.py             법정동코드 → region.csv
    ├── init_db.py                  SQLite 스키마 생성 + region·legal_dong_code 적재
    ├── collect_kepco_dgen.py       KEPCO 계통여유 수집 CLI
    ├── build_irradiance.py         일사량 정제·매핑·적재
    ├── collect_ordinance.py        자치법규 수집
    ├── collect_land_use.py         VWorld 토지이용 → data/land_use 캐시
    ├── build_ordinance_vectors.py  조례 임베딩 → ChromaDB
    ├── load_smp_rec.py             SMP·REC → smp_rec 테이블 적재
    ├── hwp_to_text.py              HWP5(별표) 텍스트 추출 (olefile+stdlib)
    ├── compare_hybrid.py           하이브리드 검색 on/off 비교 (로컬 확인·재측정)
    └── analyze_station_mapping.py  관측소↔시군구 매핑 분석
```

---

## 2. 환경 설정

```bash
# Python 3.14 (이미 설치됨)
# 의존성: requests, streamlit (이미 설치)

# 1) 환경변수 파일 만들기
copy ini/.env.example ini/.env
# ini/.env 에 다음 키 입력
#   KEPCO_API_KEY=...        (한국전력 빅데이터센터)
#   DATA_GO_KR_KEY=...       (공공데이터포털, 선택)
#   VWORLD_API_KEY=...       (VWorld 토지이용계획, 선택 — 발급 시 등록한 domain 필요)
#   OPENAI_API_KEY=...       (LLM/임베딩, 선택)
```

---

## 3. 데이터 처리 파이프라인

### 3-1. 행정코드 → region 테이블 (✅ 완료)

**목적:** 모든 데이터의 JOIN 키가 될 시군구 코드 정규화.

**원본:** `data/행정코드/법정동코드 전체자료.txt` (CP949, 50,100행)
**경로:** code.go.kr → 법정동 → 전체 다운로드

**처리 규칙:**
- `상태 == "존재"` 만
- 코드 끝 5자리 == `00000` (시군구 레벨)
- 시도 단독 행 제외, **단 세종 예외**
- **일반구 제외** (sigungu에 공백 포함 → "천안시 동남구" 등) — KEPCO API 중복 방지

**실행:**
```bash
python scripts/build_region.py   # → data/processed/region.csv (229건)
python scripts/init_db.py        # → db/solarfit.db 적재
```

**결과:**
- region 테이블 **229건** (서울 25, 경기 31, 충남 15, 충북 11, ...)
- 당진시 = `44270`, 세종 = `36110`

---

### 3-2. KEPCO 계통여유 (분산전원 연계정보) (✅ 충청 완료)

**목적:** 시군구별 신규 태양광 연결 가능 용량 수집.

**API:** https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do
**키:** `ini/.env`의 `KEPCO_API_KEY` (40자리, 빅데이터센터 발급)

**호출 단위:**
- 입력: `metroCd`(2자리) + `cityCd`(3자리) = 우리 `region_code` 앞 5자리
- 응답: 시군구 내 모든 변전소·변압기·DL의 여유용량(vol1/vol2/vol3, 단위 kW)

**중요: 일반구 케이스**
- `cityCd=110`(청주시 parent) 호출 시 → 청주시 4개 구 데이터 **모두 반환**
- → 일반구 코드(43111~4)는 region에서 제거 (3-1 단계). parent로만 호출.

**실행:**
```bash
# 충청도 (충북 11 + 충남 15)
python scripts/collect_kepco_dgen.py --scope chungcheong

# 다른 옵션
python scripts/collect_kepco_dgen.py --scope all          # 전국 229
python scripts/collect_kepco_dgen.py --scope gyeongsang   # 경상도
python scripts/collect_kepco_dgen.py --scope custom --regions 44270,44150
```

전체 `--scope` 값: `all, chungcheong, chungbuk, chungnam, gyeongsang, gyeongbuk, gyeongnam, jeolla, jeonbuk, jeonnam, gyeonggi, gangwon, jeju, seoul, busan, daegu, incheon, gwangju, daejeon, ulsan, sejong, custom`

**결과 저장:** `data/raw/kepco_dgen/{region_code}.json`
**현재:** 충청 26건 JSON. DB 적재 대신 **`src/diagnose.get_grid()`가 JSON 직접 조회**로 계통 여유 사용 (추천 랭킹 35%). 별도 테이블 불필요.

**응답 필드 의미:**
| 필드 | 의미 | 단위 |
|------|------|------|
| `vol1` | 변전소 여유용량 (가장 큰 단위) | kW |
| `vol2` | 변압기 여유용량 (중간) | kW |
| `vol3` | DL(배전선로) 여유용량 (가장 작은 단위, 실제 연결 가능량) | kW |

---

### 3-3. 일사량 — 전국 경사면 일사량(KMAPP 5년) (✅ 적용)

> ⚠ **2026-06-06 갱신:** 기존 기상청 ASOS 월자료(수평면·proxy 보강) → **전국 시군구 경사면 일사량(KMAPP `.nc`, SWDN_topo, 2016~2021 5년 평균)**으로 교체.
> 적재: `python scripts/load_tilted_irradiance.py --commit` (기존 테이블은 `irradiance_backup`로 자동 백업).
> 시군구마다 고유 격자값 → **proxy 보강 불필요**, 전국이 같은 경사면 기준이라 "전국 평균 대비" 비교가 일관됨.
> 아래 ASOS 설명은 **이전 방식(참고용)**.

**목적:** 시군구별 일사량(MJ/m²) — 발전 수익 계산용.

#### 원본 파일

| 파일 | 내용 | 비고 |
|------|------|------|
| `data/일사량/OBS_ASOS_MNH_*.csv` | 관측소·월별 합계 일사량 | CP949, 5,803행 |
| `data/일사량/META_관측지점정보_*.csv` | 관측소 코드·주소·위경도 | CP949, 146 관측소 |

**다운로드 경로:** data.kma.go.kr → 데이터 → 종관기상관측(ASOS) → 월자료 / 지점정보

#### 처리 단계

**Step 1. 관측소를 시군구에 매핑** (`parse_address()` → `region_lookup`)

META의 `지점주소`를 파싱해 각 관측소의 시도·시군구를 뽑고, `region` 테이블의 `region_code`와 매칭.

주소 형식 처리 규칙:
```
"강원특별자치도 고성군 토성면 봉포리"   → (강원특별자치도, 고성군)         # 일반 케이스
"경기도 수원시 권선구 고색동"           → (경기도, 수원시)                # 일반구 띄어쓰기
"경기도 수원시권선구 고색동"            → (경기도, 수원시)                # 일반구 붙여쓰기 ★
"세종특별자치시 새롬동"                → (세종특별자치시, 세종특별자치시)   # 세종 특수
""                                  → 매핑 실패
```

★ 부분이 보완된 핵심: 정규식 `^([가-힣]+시)([가-힣]+구)$`로 붙여쓰기 분리.
   → 수원·청주·포항·전주 4개 시 관측소를 정상 매핑.

**결과:** 146 관측소 중 **142개 직접 매핑**, 4개 미매핑 (주소 비어있는 예비 관측소 등).

**Step 2. 10년 평균 산출** (`parse_obs()`)

OBS 파일에서:
- 기간: `2015 ≤ year ≤ 2024`
- 결측 제외: `합계 일사량 > 0` 만
- 관측소별 월(1~12) 평균 산출

**결과:** 일사량 측정 관측소 **63개** 확보 (전체 146개 중 위경도/온도만 측정하는 곳 제외).

**Step 3. 시군구 → 관측소 할당** (`assign_missing_regions()`)

229개 시군구를 다음 우선순위로 할당:

| 케이스 | 처리 | 갯수 |
|--------|------|------|
| 시군구 안에 일사량 관측소 있음 | 그 관측소 데이터 직접 사용 | 57건 |
| 시군구 안에 관측소 없음 | 같은 시도 관측소들의 평균 좌표와 가장 가까운 관측소를 proxy로 사용 | 172건 |

> 시군구 중심좌표 데이터가 없어, "같은 시도 내에서 가장 평균에 가까운 관측소"가 보강 매핑의 기준입니다. 정확한 nearest-neighbor를 하려면 시군구 좌표 별도 수집 필요.

**Step 4. `irradiance` 테이블 적재**

```sql
irradiance (region_code, month, irradiance)   -- (현행) 229건: 시군구별 연 1행(month=0, 경사면 연 MJ)
                                              -- (이전 ASOS) 229 × 12 = 2,688건
```

#### 실행

```bash
python scripts/build_irradiance.py
```

#### 검증·점검 도구

```bash
python scripts/analyze_station_mapping.py
```

시군구별로 관측소 0/1/2+개 분포, 시도별 직접/보강 매핑 현황, 주소 매핑 실패 관측소 목록 출력.

#### 데이터 한계 (개선 불가, 데이터 자체 문제)

| 관측소 | 메타 | OBS 일사량 |
|--------|------|-----------|
| 천안(232) | 있음 | ❌ 측정 안 함 |
| 부여(236) | 있음 | ❌ 측정 안 함 |
| 금산(238) | 있음 | ❌ 측정 안 함 |
| 보령(235) | 있음 | ⚠ 2024~만 (2년치) |

→ (이전 ASOS 방식의 한계였음) **현행 경사면 데이터는 시군구마다 고유 격자값이라 위 proxy 보강이 불필요** — 이 한계는 해소됨.
→ 현행 한계는 "시군구 평균(경사면, 5년)이라 부지 단위 미시지형·차폐는 미반영" 정도.

#### 검증 (당진시 예시)

```
1월  269.2  /  2월  332.2  /  3월  483.4  /  4월  565.9
5월  655.4  /  6월  610.1  /  7월  512.9  /  8월  490.3
9월  441.5  / 10월  387.5  / 11월  272.1  / 12월  231.7
연합계 ≈ 5,252 MJ/m²   (한국 평균 4,500~5,500 범위, 5~6월 피크 정상)
```

---

### 3-4. 자치법규 수집 (국가법령정보 API) (✅ 충남 완료)

**목적:** 시군구·광역 자치법규(조례·고시·규칙)를 RAG 입력 데이터로 수집.

#### API

- 엔드포인트: `https://www.law.go.kr/DRF/lawSearch.do` (목록) + `lawService.do` (본문)
- 키: `LAW_API_KEY` (`ini/.env`, 우리는 `OPEN_LAW_API`)
- 핵심 파라미터:
  - `target=ordin` — 자치법규
  - `search=2` — **본문 검색** (조례명만 검색하는 `search=1`은 누락 많음)
  - `query=태양광` 등 키워드

#### 처리

1. 키워드별 검색 → 자치법규 메타(법령ID·법령명·지자체기관명·MST 등) 수집
2. **자치법규ID 기준 중복 제거**
3. 지자체기관명 → `region_code` 매핑 (시군구 = 5자리, 광역 = 시도코드+`000`)
4. 메타 → `ordinance` SQLite 테이블 적재
5. (옵션) 본문 → JSON 파일 (`data/raw/ordinance/{law_id}.json`)

#### 실행

```bash
# 메타만 (전국 검색 → 매핑 → DB)
python scripts/collect_ordinance.py --keywords 태양광,신재생에너지

# 본문까지 (충남만)
python scripts/collect_ordinance.py --keywords 태양광 --scope chungnam --bodies

# 광범위 확장 키워드
python scripts/collect_ordinance.py \
    --keywords 태양광,신재생에너지,발전사업,영농형,분산에너지,에너지자립,이격거리,개발행위,도시계획,발전시설,보급촉진,보급지원,입지선정 \
    --scope chungnam --bodies
```

#### 현재 결과

- 메타: 약 **1,188건** (전국, search=2 기준)
- 본문: **169건** (충남 시군구 + 충청남도 광역)
- 충남 시군구 자치법규 보유 현황: 15개 모두 1~16건

---

### 3-5. 조례 벡터화 (OpenAI 임베딩 → ChromaDB) (✅ 충남 완료)

**목적:** 자유 질문 의미 매칭을 위한 벡터 검색 인덱스.

#### 처리

1. `data/raw/ordinance/*.json` 본문 로드
2. 본문 → 조문 단위 청크 (`LawService.조문.조[]` 배열 그대로)
3. 청크 텍스트 = `{기관명} {법령명} {조제목}: {조내용}`
4. 메타데이터: `region_code, sido, sigungu, institution, level, law_id, law_name, law_type, mst, article_num, article_title`
5. OpenAI `text-embedding-3-small` (1536차원) 임베딩
6. ChromaDB `ordinance` 컬렉션 적재 (코사인 유사도, HNSW)

#### 실행

```bash
python scripts/build_ordinance_vectors.py
```

→ `db/chroma_db/` 폴더 자동 생성. 기존 컬렉션은 삭제 후 재생성 (idempotent).

#### 현재 결과

- ChromaDB `ordinance` 컬렉션: **4,251 청크**
- 충남 시군구·광역 모두 포함
- OpenAI 임베딩 비용: 약 80원 (누적)

---

### 3-6. RAG 모듈 (`src/solarfitRag.py`) (✅ 완료)

**목적:** 검색 + 답변 생성을 분리 가능한 모듈로.

#### 검색 전략 — **시군구 60% + 광역 40% 쿼터**

```
질문 → OpenAI 임베딩
   ↓
ChromaDB 시군구 청크 검색 (region_code=44270)
ChromaDB 광역 청크 검색 (region_code=44000, level=광역)
   ↓
시군구 3건 + 광역 2건 쿼터 합치기 → distance 정렬 → top-5
```

→ 단순 distance 정렬 시 광역 조례만 top-5 차지하는 문제 해결. 시군구 자체 조례 항상 포함.

#### 하이브리드 검색 (2026-06-05 추가) — 벡터 + 키워드 RRF

```
질문 ─┬─ (A) 순수 벡터 검색
      └─ (B) 키워드 필터 검색 (where_document $contains "이격" 등)
              ↓ RRF 융합 (순위 기반) → 쿼터 → top-5
```

- 순수 벡터가 놓치는 정답 조항을 **키워드 경로로 회수** 후 RRF(Reciprocal Rank Fusion) 융합
- 키워드는 **질문 원문**에서 변별력 높은 어근만 추출 (`태양광/발전/설치/지원` 등 코퍼스 14~25% 차지하는 비변별어 제외)
- `search/answer/answer_stream(..., hybrid=True, rewrite=True)` — **on/off 플래그**로 재측정 비교 지원
- 효과: "이격거리" 질문에서 벡터 top-5 밖이던 발전시설 이격 조항(계룡 제18조의2) 회수 → 조문 Recall↑
- 검증/비교: `python scripts/compare_hybrid.py "이격거리 기준" 44250`

#### 답변 생성

- 모델: OpenAI `gpt-4o-mini`
- 스트리밍 (`stream=True`) → Streamlit `st.write_stream` 실시간 표시
- 시스템 프롬프트: 참고 조례에 근거만 답변, 짧은 질문도 적극 매칭, 수치는 그대로 인용

#### 사용 예 (코드)

```python
from src.solarfitRag import OrdinanceRAG
rag = OrdinanceRAG()

# 비스트리밍
res = rag.answer("보조금 얼마야?", region_code="44270")
print(res["answer"], res["sources"])

# 스트리밍
gen, chunks = rag.answer_stream("보조금 얼마야?", region_code="44270")
for token in gen:
    print(token, end="", flush=True)
```

---

### 3-7. Streamlit UI 실 DB 연결 (`solarfit.py`) (✅ 완료)

- 좌측: 광역 드롭다운 + 시군구(조례 있는 곳만) + TOP5 임시 점수
- 우측: 핵심 지표 4칸 + 수익 시뮬레이션 + RAG Q&A 챗봇 (스트리밍·출처 표시)

```bash
python -m streamlit run pages/site_diagnosis.py --server.port 9001 --browser.gatherUsageStats false
```

브라우저: http://localhost:9001

---

### 3-8. 입지진단·추천 + 이격 규제 데이터셋 (2026-06-05) (✅ 충남)

**목적:** 메인 화면(`pages/site_diagnosis.py`)에서 **지번→부지 진단**, **시군구명→지역 진단**, **그 외→시군구 추천 랭킹**.

#### 충남 이격 규제 데이터셋 — `data/byeolpyo/setback.json`
- 충남 15개 시군구별 태양광 발전시설 **이격거리**(도로·주거·관광지·부지경계) + 난이도 + 출처·다운로드 링크
- 출처: **조문**(하이브리드 검색) + **별표(HWP)**. 별표 수치는 JSON 본문에 없고 HWP 첨부라 `scripts/hwp_to_text.py`로 추출
- ⭐ 당진·보령·홍성·태안은 조문엔 없고 **별표(HWP)에만** 이격이 있던 케이스 (조문만 보면 놓침)

#### `src/diagnose.py`
| 함수 | 입력 | 출력 |
|------|------|------|
| `diagnose(주소)` | 지번 주소 | `{이격, 지원, 용도지역, 종합판정}` 항목별 dict |
| `recommend(sido="44")` | 시도 prefix | 시군구 랭킹 리스트 |
| `get_grid(region_code)` | 시군구 코드 | 계통 여유 `{best_kw, status}` |

- `diagnose`: 주소→region_code → ①이격(setback **딕셔너리 조회**) ②지자체지원(**RAG 하이브리드**) ③용도지역(VWorld 캐시) ④종합판정(**LLM**)
- `recommend`: 일조량(SQLite) 40% / 계통(KEPCO JSON) 35% / 규제난이도(setback) 25% → 종합점수 순위
- `get_grid`: KEPCO `data/raw/kepco_dgen/{region}.json` **직접 조회** (DB 적재 불필요). 연계가능 = `min(vol1,vol2,vol3)`

```python
from src.diagnose import diagnose, recommend
res  = diagnose("충남 논산시 부적면 충곡리 200")   # 단일 진단
rank = recommend("44")                            # 충남 추천 랭킹 (천안 1위)
```

**화면 연결(완료):** `pages/site_diagnosis.py`가 메인 엔트리. 라우팅 — 지번→`diagnose()` 부지 진단 / 시군구명→`diagnose_region()` 지역 진단 / 그 외→`recommend()` 추천 랭킹. 모두 `@st.cache_data` 캐싱.

---

## 4. SQLite DB 스키마

**파일:** `db/solarfit.db`

| 테이블 | 건수 | 상태 | 설명 |
|--------|------|------|------|
| `region` | **229** | ✅ | 모든 JOIN의 허브 (시군구 코드) |
| `legal_dong_code` | **20,560** | ✅ | 법정동코드 (지번→PNU 변환용, region과 독립) |
| `irradiance` | **229** | ✅ | 시군구별 **연 경사면 일사량** (KMAPP 5년, month=0 1행) · 백업: `irradiance_backup`(2,688) |
| `ordinance` | **약 1,188** | ✅ | 자치법규 메타·본문 (충남 169건 본문) |
| `power_plant` | 0 | ⏳ | 발전소 허가정보 (data.go.kr 15087742) |
| `supply_status` | 0 | ⏳ | 보급현황 (data.go.kr 15086292) |
| `land_price` | 0 | ⏳ | 지가 |
| `land_use` | 0 (미사용) | ➖ | 용도지역 — VWorld API + `data/land_use` 캐시로 처리 (SQLite 테이블 대신) |
| `smp_rec` | **12** | ✅ | SMP·REC 월단가 (2025-01~12, 화면 수익성 계산에 사용) |
| `grid_capacity` | (없음) | ➖ | KEPCO 여유용량은 JSON 직접조회(`get_grid`)로 사용 — 테이블 불필요 |

**별도 저장소:**
- ChromaDB `ordinance` 컬렉션: 4,251 청크 (`db/chroma_db/`)
- KEPCO 원본 JSON: 26개 (`data/raw/kepco_dgen/`) — `get_grid()`가 직접 사용 (계통 여유)
- 이격 규제 데이터셋: `data/byeolpyo/setback.json` (충남 15개 시군구, 조문+별표)

스키마 정의: `scripts/init_db.py`

---

## 5. 재실행 가이드 (전체 재구축)

```bash
cd C:\Projects\SolarFit

# 1) 행정코드 → region (50,100행 → 229건)
python scripts/build_region.py
python scripts/init_db.py

# 2) KEPCO 계통여유 수집 (충청만, API 키 필요)
python scripts/collect_kepco_dgen.py --scope chungcheong

# 3) 일사량 정제·적재 (원본 CSV 필요)
python scripts/build_irradiance.py

# 4) (선택) 관측소 매핑 점검
python scripts/analyze_station_mapping.py

# 5) 자치법규 수집 (충남 본문)
python scripts/collect_ordinance.py \
    --keywords 태양광,신재생에너지,발전사업,영농형,분산에너지,에너지자립,이격거리,개발행위,도시계획,발전시설,보급촉진,보급지원,입지선정 \
    --scope chungnam --bodies

# 6) 조례 벡터화 (OpenAI 임베딩 호출, 약 80원)
python scripts/build_ordinance_vectors.py

# 7) UI 실행
python -m streamlit run pages/site_diagnosis.py --server.port 9001 --browser.gatherUsageStats false
```

---

## 6. 데이터 소스 정리

| 데이터 | 출처 | 갱신 주기 | 상태 |
|--------|------|-----------|------|
| 행정코드 (법정동) | code.go.kr | 비정기 | ✅ |
| 계통 여유용량 | bigdata.kepco.co.kr (API) | 수시 | ✅ 충청 JSON (`get_grid` 직접 사용) |
| 이격 규제 (조례) | open.law.go.kr 조문 + 별표 HWP | 비정기 | ✅ 충남 15개 (`data/byeolpyo/setback.json`) |
| 일사량 (연·경사면) | KMAPP `.nc` (SWDN_topo, 5년) | 비정기 | ✅ 전국 229 (`load_tilted_irradiance.py`) |
| 자치법규 (RAG) | open.law.go.kr (API) | 비정기 | ✅ 충남 169 본문 + 벡터 |
| 토지이용계획 (용도지역·농지) | VWorld api.vworld.kr (API) | 수시 | ✅ 시연 지번 캐시 (domain 파라미터 필수) |
| 발전소 허가정보 | data.go.kr 15087742 | 분기 | ⏳ |
| 보급현황 | data.go.kr 15086292 | 연간 | ⏳ |
| 지가 | 국토부 공시지가 | 연간 | ⏳ |
| SMP·REC | 전력거래소(KPX) | 일간 | ⏳ |

---

## 7. 다음 단계 (발표 2026-06-08 11:00 기준)

### P0 — 반드시
1. **발표 슬라이드 12~15장 작성** (구조도·데이터·RAG·평가·데모)
2. **데모 영상 백업 녹화** (인터넷 끊김 대비)
3. **평가 메트릭 1개 측정** (Citation Accuracy 또는 Hit Rate@5)

### P1 — 권장
4. 충북·경기 등 1~2개 도(道) 자치법규 추가 확장
5. `scripts/load_kepco_to_db.py` 작성 → `grid_capacity` 테이블 적재
6. 평가용 골드 셋 30~50건 CSV 작성
7. `scripts/eval_rag.py` 자동 평가 도구

### P2 — 시간 남으면
8. data.go.kr 발전소 허가정보 수집
9. data.go.kr 보급현황 수집
10. 추천 점수 5요소 가중치 모듈
11. 주소 검색 통합 (Daum + 카카오)
12. 답변 캐시 (`@st.cache_data`)
13. RAGAS Faithfulness 측정

> 상세 진행 상황·의사결정·이슈는 [PROGRESS.md](./PROGRESS.md) 참고.

---

## 8. 핵심 결정 사항 (확정)

- **DB:** SQLite (MVP) → PostgreSQL (실서비스)
- **벡터 DB:** ChromaDB (로컬 파일)
- **JOIN 키:** 5자리 `region_code` (시군구), 일반구는 parent로 통합
- **모델:**
  - 임베딩: OpenAI `text-embedding-3-small` (1536차원)
  - LLM: OpenAI `gpt-4o-mini` (스트리밍)
  - → 캐글·Ollama·Cloudflare Tunnel 모두 제거. API 1개로 통합.
- **RAG 검색 전략:** 시군구 60% + 광역 40% 쿼터 분배 (단순 distance 정렬 한계 보완)
- **자치법규 수집:** `target=ordin` + `search=2`(본문 검색)으로 누락 최소화
- **원본 보존 원칙:** `data/` 하위 원본 절대 수정 금지, `data/processed/`·DB만 갱신

---

## 9. 관련 문서

| 파일 | 용도 |
|------|------|
| [HANDOFF.md](./HANDOFF.md) | 프로젝트 컨텍스트·요구사항·아키텍처 (원본 기획) |
| [PROGRESS.md](./PROGRESS.md) | 진행 상황·의사결정 로그·알려진 이슈·다음 할 일 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 구조도·RAG 흐름·모델 변화 (Mermaid 다이어그램) |
| README.md (이 문서) | 폴더 구조·적재 단계별 가이드·재실행 방법 |
