# 솔라스팟 (가칭) — 프로젝트 핸드오프 문서

> 소형태양광 입지 추천 + 조례 Q&A 서비스 (RAG 기반)
> 다음 세션 재시작용 정리본

---

## 0. 프로젝트 한 줄 요약

```
지역명을 입력하면 → 일사량·계통여유·지가·규제를 종합해 추천 점수와
                  조례 요약·Q&A까지 한 화면에 제공
                  (DB 쿼리 + RAG 하이브리드)
```

- 용도: 수업/포트폴리오 (1주, 5인)
- 가능 확장: B2B 데이터·리드 중개
- 이름 후보: 태양명당 / 양지바른 / 솔라스팟 / 햇빛부동산
- 현재 목업 실행: `C:\Projects\SolarFit\solarfit.py` (Streamlit, 더미데이터)
  - 실행: `cd C:\Projects\SolarFit && python -m streamlit run solarfit.py`
  - 주의: `streamlit` 명령이 PATH에 없어 `python -m streamlit` 사용

---

## 1. 데이터 수집

### 1-1. 핵심 데이터 (필수, 1순위)

| 데이터 | 제공처 | 필요 이유 | 추출할 내용 |
|--------|--------|-----------|-------------|
| 태양광 발전소 (전기사업허가) | data.go.kr — 전국태양광발전소 전기사업허가정보 표준데이터 (15087742) | 지역별 발전소 갯수·포화도 | 시설명, 주소, 설비용량(kW), 허가일자, 위경도, 가동상태 |
| 신재생에너지 보급현황 | data.go.kr — 한국에너지공단_기초지자체별 신재생에너지 보급 현황 (15086292) | 지역별 태양광 보급량/발전량 | 광역·기초, 에너지원(태양광 필터), 발전량(MWh), 누적·신규 보급용량(kW) |
| 지자체 조례 | 자치법규정보시스템 elis.go.kr | 설치 가능 여부, 규제, 보조금 (RAG 대상) | 보조금 단가, 이격거리, 설치제한구역, 인허가 요건 |
| 행정구역 표준코드 | 행정안전부 행정표준코드관리시스템 | **모든 데이터를 같은 지역키로 묶는 기준** | 시군구 코드, 표준 명칭 |

> 핵심 발견: "지역별 업체 갯수"는 깔끔한 데이터셋이 없음.
> → MVP는 "발전소 갯수"로 요구사항 재정의 (확실한 데이터)
> → "시공업체 회사 수"가 꼭 필요하면 산업통계/AS전담업체 데이터 추가 검증 필요

### 1-2. 보조 데이터 (추천 점수 고도화, 2순위)

| 데이터 | 제공처 | 사용처 | 갱신 |
|--------|--------|--------|------|
| 일사량/발전량 | 기상청 기상자료개방포털, KIER 자원지도 | 발전 수익 기본 | 거의 불변 |
| 지가 | 국토부 공시지가/실거래가 | 초기투자비 | 연 1회 |
| 용도지역/토지이용 | 토지이음 eum.go.kr | 설치 가능 토지 판별 | 비정기 |
| 한전 계통 여유용량 | 한전 사이버지점, 전력거래소(KPX) | 개통 가능 여부 | 수시 변동 |
| SMP·REC | 전력거래소(KPX) | 수익성 계산 | 일/주별 |

### 1-3. 변동성 처리 전략

```
거의 불변 (일사량)          → 스냅샷 1회 저장
연 단위 (지가, 보급현황)    → 연간 갱신
수시 (계통, 조례)          → 비정기 갱신, 변경 시 재임베딩(조례)
고빈도 (SMP, REC)          → 시계열 테이블, 대표값 또는 일배치
```

> 1주 프로젝트는 전부 **스냅샷**으로 고정, "실서비스라면 일배치"라고 발표에 언급.

### 1-4. 정합 핵심 — 지역키 정규화

```
"당진" / "당진시" / "충남 당진시"  → region_code = "44270"
   ↑ 행정표준코드로 통일
```

- 모든 테이블의 JOIN 키는 `region_code` (시군구 코드)
- 주소만 있는 데이터(발전소 허가정보)는 주소 파싱 → 행정코드 매칭

---

## 2. 구조

### 2-1. 시스템 아키텍처

```
┌──────────────────────────────────┐
│  사용자 브라우저                     │
└───────────────┬──────────────────┘
                │
┌───────────────┴──────────────────┐
│  내 PC = 웹서버                    │
│  Streamlit UI                    │
│  ├─ 검색·필터·랭킹    (DB 쿼리)     │
│  ├─ 지역 지표·수익     (DB 쿼리)     │
│  └─ 조례 요약·Q&A     (RAG)        │
│                                  │
│  벡터DB 파일 (db/chroma_db/) 로컬     │
│  관계형DB 파일 (sqlite) 로컬       │
└──────┬───────────────────────────┘
       │ HTTP (cloudflared tunnel URL)
┌──────┴───────────────────────────┐
│  캐글/코랩 노트북 (무료 GPU)         │
│  Ollama + EXAONE/Qwen            │
│  (LLM 추론 API)                  │
└──────────────────────────────────┘
```

- 웹서버 = 내 PC (Streamlit)
- LLM = 캐글 GPU에서 Ollama로 띄움 → Cloudflare Tunnel로 노출 → 내 PC가 HTTP 호출
- 임베딩 = 캐글에서 1회 생성 → `db/chroma_db/` 폴더 팀 공유 → 이후 검색은 로컬 CPU

### 2-2. 데이터 저장소 분배

```
[관계형 DB — SQLite (MVP) → PostgreSQL]  정형 수치, 비교/랭킹
   region, power_plant, supply_status, irradiance,
   land_price, land_use, smp_rec

[벡터 DB — ChromaDB]  비정형 텍스트, 의미검색
   ordinance (조례 청크)
```

### 2-3. 관계형 DB 스키마

```sql
-- 기준 (모든 JOIN의 허브)
region (
  region_code TEXT PK,    -- 행정표준코드 예: '44270'
  sido        TEXT,        -- 광역
  sigungu     TEXT         -- 시군구
)

-- 발전소 (전기사업허가 정보)
power_plant (
  plant_id    INTEGER PK,
  region_code TEXT FK,
  name        TEXT,
  capacity_kw REAL,
  permit_date DATE,
  status      TEXT,
  lat REAL, lng REAL,
  address     TEXT
)

-- 보급현황 (기초지자체별)
supply_status (
  region_code TEXT FK,
  energy_type TEXT,        -- '태양광' 필터
  year        INTEGER,
  gen_mwh     REAL,
  cap_cum_kw  REAL,
  cap_new_kw  REAL,
  PK (region_code, energy_type, year)
)

-- 일사량
irradiance (
  region_code TEXT FK,
  month       INTEGER,
  irradiance  REAL,
  PK (region_code, month)
)

-- 지가
land_price (
  region_code   TEXT FK,
  land_category TEXT,      -- 농지/임야/대지
  price_per_m2  REAL,
  year          INTEGER,
  PK (region_code, land_category, year)
)

-- 용도지역
land_use (
  region_code   TEXT FK,
  zone_type     TEXT,
  solar_allowed TEXT,      -- 가능/조건부/불가
  PK (region_code, zone_type)
)

-- 전국 단가 (지역 무관)
smp_rec (
  date DATE PK,
  smp  REAL,
  rec  REAL
)
```

### 2-4. 벡터 DB 구조 (ChromaDB)

```
collection = "ordinance"

각 청크 = {
  id:        "44270_001",                 # region_code_순번
  document:  "당진시 농지 태양광 설치 불가, 이격거리 100m...",  # 임베딩 대상
  embedding: [0.21, -0.04, ...],          # ko-sroberta 768차원
  metadata: {
     region_code: "44270",                # 관계형 DB와 연결고리
     sigungu:     "당진시",
     topic:       "이격거리",                # 보조금/이격거리/설치제한 등
     source:      "당진시 도시계획 조례 제32조"
  }
}
```

→ `metadata.region_code`가 관계형↔벡터 다리.

### 2-5. 조례 처리 — DB 컬럼 vs 벡터DB 분리

```
조례 원문에서 두 가지로 분리 저장:

[DB 컬럼화]  빠른 필터·랭킹용
  - 가능여부 (가능/조건부/불가)  → land_use.solar_allowed
  - 보조금 단가 (만원/kW)        → (별도 ordinance_meta 테이블 권장)
  - 이격거리 (m)
  → "여러 지역 거르기"에 사용 (RAG 불필요)

[벡터DB]  자연어 질문·해석용
  - 핵심 조항 텍스트 (보조금/이격거리/설치제한/인허가)
  - 그 외(목적·정의·부칙) 제외해 사이즈 축소
  → "왜·어떻게" 같은 깊은 질문에 RAG
```

### 2-6. 화면 구조 (단일 페이지, MVP)

```
좌측 (DB 영역)              우측 (DB + RAG)
───────────────             ──────────────────────────
🔍 검색/필터                 📍 선택 지역 상세
  광역·설비·지목              한줄평 (LLM 또는 템플릿)
  ☑ 계통여유 ☑ 가능           핵심지표 4칸 (일사/계통/지가/포화) ← DB
───────────────             수익 시뮬레이션 ← DB
🏆 추천 TOP 5                ─────────────────
  점수·강점/약점             📋 조례 요약 ← RAG ★①
  [상세] 클릭 → 우측 갱신     ─────────────────
                            💬 조례 Q&A 챗봇 ← RAG ★②
```

### 2-7. RAG 사용 시점 (화면상 딱 두 곳)

| 위치 | RAG? | 동작 |
|------|------|------|
| 추천 TOP5·점수 | ✗ | DB 쿼리 |
| 핵심 지표 4칸 | ✗ | DB 조회 |
| 수익 시뮬레이션 | ✗ | DB 값 계산 |
| 조례 요약 ★① | ✓ | 지역 선택 시 자동, 검색→LLM 요약 |
| 조례 Q&A ★② | ✓ | 사용자 질문, 검색→LLM 답변 |

### 2-8. 검색 진입 시 처리 분기

```
"광역(충청남도)" 입력      → DB만으로 15개 시군구 필터·랭킹
                            (여러 지역에 RAG 돌리면 느림)

"특정시(당진시)" 입력      → DB + 조례 RAG 동시 실행
                            (한 곳이면 RAG 1회라 부담 없음)
```

### 2-9. 추천 점수 (잠정 가중치)

```
score = 일사량 30% + 계통여유 25% + 지가(역) 20%
      + 규제(가능여부) 15% + 포화도(역) 10%
```

(차후 튜닝 — 5명 중 D 담당)

---

## 3. 모델

### 3-1. 사용 모델 — 단 2종 (학습/파인튜닝 없음)

| 구분 | 모델 | 용도 | 실행 시점 | GPU |
|------|------|------|-----------|-----|
| ① 임베딩 | `jhgan/ko-sroberta-multitask` (HF) | 조례→벡터, 검색용 | 캐글 1회 | 1회성 |
| ② LLM | `EXAONE 3.5` (1순위) / `Qwen2.5` (대안) | RAG 답변 생성 | 캐글 API (매 질문) | 매 질문 |

> 자체 모델 사용이 요건이므로 상용 API(GPT/Gemini) 사용 안 함.

### 3-2. 왜 학습/파인튜닝 안 하나

```
RAG로 지식 주입 = 검색 결과를 프롬프트에 끼워넣기 (학습 X)
조례·계통 데이터는 자주 바뀜 → 학습하면 매번 재학습 부담
→ 데이터 갱신은 벡터DB 갱신으로 흡수, 모델은 그대로
```

### 3-3. GPU 사용 지점

```
임베딩 생성   GPU 권장 (1회성)  → Colab/Kaggle에서 db/chroma_db 폴더 생성
벡터DB 검색   CPU              → 로컬에서 즉시
LLM 추론      GPU 필수          → 캐글에 띄워 API화, Tunnel로 노출
                              → 로컬은 GPU 0개로 호출만
```

### 3-4. 실행 구조 (모델 측)

```
[캐글 노트북]
  1. Ollama 설치  (curl ... ollama.com/install.sh)
  2. ollama serve &           → localhost:11434에 API 자동 제공
  3. ollama pull exaone3.5    → 모델 다운로드 (GPU에서 실행됨)
  4. cloudflared tunnel --url http://localhost:11434
     → https://xxxx.trycloudflare.com 외부 URL 발급

[내 PC 웹앱]
  LLM_URL = "https://xxxx.trycloudflare.com/api/generate"
  검색(R) → 프롬프트(A) → requests.post(LLM_URL, ...) → 답변(G) → UI
```

### 3-5. 약점·대비책

| 문제 | 대비 |
|------|------|
| 캐글 세션 타임아웃(12h) | 발표 직전 재시작, 모델 미리 로드 |
| Tunnel URL 변동 | Cloudflare 계정 연동 고정 도메인 / 또는 ngrok 무료 고정 1개 |
| 응답 지연 | 작은 모델(Qwen 3B) 폴백 옵션 |
| 발표 중 끊김 | 데모 영상 녹화본 백업 필수 |

### 3-6. 임베딩 모델 주의

- **팀 전원 동일 모델/버전 사용** (안 그러면 차원 안 맞아 검색 깨짐)
- `requirements.txt`에 모델명 박아두기
- db/chroma_db 폴더는 임베딩 담당이 1회 생성 → Git/Drive로 공유

---

## 4. 환경/스택 요약

| 항목 | 선택 | 비고 |
|------|------|------|
| 언어 | Python 3.14 (현재 환경) | |
| UI | Streamlit 1.58 | 이미 설치됨 |
| 관계형 DB | SQLite (MVP) → PostgreSQL | 파일 1개로 시작 |
| 벡터 DB | ChromaDB | 로컬 파일/폴더 |
| 임베딩 | ko-sroberta-multitask | HF 무료 |
| LLM | EXAONE 3.5 (Ollama on Kaggle) | 무료, 한국어 강함 |
| GPU | Kaggle (주 30시간) 또는 Colab | 무료 T4 |
| LLM Tunnel | Cloudflare Tunnel (또는 ngrok) | 캐글 ↔ 로컬 연결 |
| 크롤링 | requests + BeautifulSoup | 조례용 |
| 협업 | Git/GitHub | |

---

## 5. 5인 역할 분담

| 팀원 | 역할 | 핵심 작업 |
|------|------|-----------|
| A | 팀장·데이터엔지니어 | data.go.kr/elis 수집, 행정코드 정규화, 일정관리 |
| B | DB·백엔드 | 스키마·SQLite 구축, 검색/추천 쿼리 |
| C | RAG 엔지니어 | 조례 추출·임베딩, 캐글 LLM API, Tunnel |
| D | 추천 알고리즘 | 가중치 설계, 점수 계산, 튜닝 |
| E | 프론트·통합 | Streamlit UI, API 연동, 발표자료 |

> 의존성: A가 Day1에 샘플 데이터(1~2개 지자체) 먼저 풀어야 B·C·D 병렬 가능.

---

## 6. 1주 일정

| Day | 목표 | 산출물 |
|-----|------|--------|
| 1 | 킥오프·스키마·환경·샘플데이터 | repo, DB 스키마, 1~2지자체 더미 |
| 2 | 데이터 수집 (업체/계통/조례) | 원시 CSV/JSON |
| 3 | DB 적재·조례 핵심조항 추출·임베딩 | sqlite DB, db/chroma_db 폴더 |
| 4 | 백엔드 API·캐글 LLM API화 | 동작하는 검색/RAG |
| 5 | UI 통합·추천 튜닝 | 통합 앱 |
| 6 | 통합테스트·버그수정·데모시나리오 | 안정화 |
| 7 | 발표자료·리허설·문서 | 최종 |

---

## 7. 현재까지 완료 / 다음 단계

### 완료
- [x] 요구사항·아키텍처 확정
- [x] 데이터 소스 검증 (data.go.kr 실제 항목 확인)
- [x] 모델·GPU 전략 확정
- [x] DB 스키마 설계
- [x] 화면 와이어프레임 4종
- [x] Streamlit UI 목업 (`C:\Projects\SolarFit\solarfit.py`, 더미 데이터)

### 다음 세션 우선순위
1. **데이터 수집 시작** — data.go.kr 회원가입, API 키, 행정코드 다운로드
2. **조례 1~2건 샘플 추출** — 당진시 등으로 elis 크롤링 실험
3. **캐글 LLM API 노트북 작성** — Ollama + EXAONE + cloudflared
4. **임베딩 노트북 작성** — ko-sroberta → db/chroma_db 생성
5. **solarfit.py 더미 → 실데이터 연결** — 한 지역(당진시)부터 end-to-end
6. **프로젝트명 확정** — 후보: 태양명당 / 양지바른 / 솔라스팟

### 미정 항목
- 프로젝트 최종 이름
- 한줄평 생성 방식 (LLM vs 템플릿)
- "시공업체 수" 요구사항을 살릴지, "발전소 수"로 갈지

---

## 8. 핵심 원칙 (잊지 말 것)

```
1. 학습/파인튜닝 NO — RAG로 지식 주입, 모델은 기성품 추론만
2. 시군구 코드(region_code)로 모든 데이터 연결
3. 조례는 DB컬럼(수치/플래그) + 벡터DB(원문) 이중 저장
   → 많이 거르기는 DB, 깊이 묻기는 RAG
4. GPU 1개로 팀 5명 작업 가능 — 임베딩은 1회 산출물 공유, LLM은 API화
5. 데이터·정합이 진짜 일 (모델은 거저)
6. MVP는 1~2개 지자체로 end-to-end 먼저, 전국 확장은 그 다음
```
