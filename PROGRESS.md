# 솔라스팟 진행 상황 (PROGRESS)

> 다음 세션에서 이 파일 1개만 읽으면 컨텍스트 확보.
> 작업 일자: ~2026-06-03
> 발표 제출: **2026-06-08 (월) 11:00**

---

## 🎯 현재 위치 한 줄 요약

> 충남 자치법규 RAG (OpenAI 임베딩 + gpt-4o-mini + 시군구·광역 쿼터 검색)가 Streamlit UI에서 동작 중. 데이터 적재·검색·답변까지 end-to-end 완성. 다음은 전국 확장 + 평가 메트릭 + 발표 자료.

---

## ✅ 완료 (현재 동작 중)

### 데이터 적재
- [x] 행정코드 → SQLite `region` 229건 (일반구 제외, 시군구만)
- [x] 일사량 ASOS 월자료 → `irradiance` 2,688건 (229 시군구 × 12개월)
  - 주소 파싱: 일반구 붙여쓰기·세종 특수처리 보강 완료
  - 미관측 시군구는 같은 시도 인근 관측소로 보강
- [x] KEPCO 분산전원 → `data/raw/kepco_dgen/*.json` 26개 (충청)
  - **⚠ `grid_capacity` 테이블 적재는 아직 미완**
- [x] 자치법규 메타·본문 → `ordinance` 1,188 메타 + 169 본문 (충남)
  - 키워드: 태양광/신재생에너지/발전사업/영농형/분산에너지/에너지자립/이격거리/개발행위/도시계획/발전시설/보급촉진/보급지원/입지선정
  - 검색 모드: `search=2` (본문 검색)
- [x] 조례 청크화 + OpenAI 임베딩 → ChromaDB `ordinance` 4,251 청크

### 코드·UI
- [x] `src/api/client.py` 공통 베이스
- [x] `src/api/kepco_dgen.py`, `law_go_kr.py` 전용 클라이언트
- [x] `src/solarfitRag.py` — 시군구 60% + 광역 40% 쿼터 검색, 스트리밍 답변
- [x] `solarfit.py` — 실 DB 연결 (region·irradiance·ordinance), Q&A 챗봇
- [x] `ini/.env.example`, `.gitignore`

### 평가
- [x] 화면에서 답변 + 출처(시군구·조례명·조항) 표시 정상

---

## ⏳ 미완료 (발표까지 해야 할 것)

### P0 (반드시)
- [ ] **발표 슬라이드 12~15장 작성** (Day 3 ~ 6/7)
- [ ] **데모 영상 백업 녹화** (Day 4 ~ 6/7)
- [ ] **평가 메트릭 1개라도 측정** (Citation Accuracy 또는 Hit Rate@5)

### P1 (있으면 좋음)
- [ ] 충북·경기 등 1~2개 도(道) 자치법규 추가 확장
  - ⚠ **재적재 시 `build_ordinance_vectors.py` 끝에 고아 폴더 자동 정리 추가할 것** (아래 이슈 참고)
- [ ] KEPCO JSON → `grid_capacity` 테이블 적재
- [ ] 평가용 골드 셋 30~50건 작성
- [ ] `scripts/eval_rag.py` 자동 평가

### P2 (시간 남으면)
- [ ] data.go.kr 발전소 허가정보 (#15087742) 수집
- [ ] data.go.kr 보급현황 (#15086292) 수집
- [ ] 추천 점수 5요소 가중치 (`src/scoring.py`)
- [ ] 주소 검색 (Daum 우편번호 + 카카오 좌표)
- [ ] 답변 캐시 (`@st.cache_data`)
- [ ] RAGAS Faithfulness 측정

---

## 🧭 의사결정 로그 (왜 그렇게 했나)

### 1. 일반구는 region에서 제외 (parent 시로 통합)
- **상황:** KEPCO API에 `cityCd=110` (청주시 parent) 호출 시 4개 일반구 데이터 모두 반환됨
- **결정:** region 테이블에 parent만 유지 (43110), 일반구(43111~4) 제거
- **결과:** region 268 → 229건. KEPCO 중복 집계 방지
- **트레이드오프:** 정확도 약간 손실 (권선구 같은 일반구 단위 분석 불가)
- **위치:** `scripts/build_region.py` — `if " " in sigungu: continue`

### 2. OpenAI 키 확보로 모델 단순화
- **이전:** ko-sroberta(HF) 임베딩 + EXAONE/Qwen(Ollama on Kaggle) + Cloudflare Tunnel
- **현재:** text-embedding-3-small + gpt-4o-mini (OpenAI API 1개)
- **결과:** 캐글·Ollama·Tunnel 모두 제거. 응답 1~2초. 1주 비용 ~200원
- **위치:** `src/solarfitRag.py`

### 3. 자치법규 API 본문 검색 (`search=2`)
- **상황:** 처음엔 `search=1`(조례명만) 사용 → 당진시 5건 중 1건만 매칭
- **발견:** elis 웹은 본문(`section=bdyText`)까지 검색. 우리도 `search=2` 추가
- **결과:** 580건 → 4,251 청크로 폭증
- **위치:** `src/api/law_go_kr.py`

### 4. 시군구 60% + 광역 40% 쿼터 검색
- **문제:** 단순 distance 정렬 시 광역 조례만 top-5 차지 → 시군구 자체 조례 누락
- **결정:** 시군구·광역 각각 검색 후 쿼터로 합치기
- **결과:** 답변에 시군구 자체 조례가 항상 포함됨 (당진시 5개 자체 조례 인용)
- **위치:** `src/solarfitRag.py` `OrdinanceRAG.search()`

### 5. 조례 SQLite + ChromaDB 이중 저장
- **SQLite**: 메타·통계·드롭다운용 (COUNT·JOIN)
- **ChromaDB**: 의미 검색용 (벡터 유사도)
- **이유**: SQL은 정확 일치만, 벡터는 의미 일치. 역할 분담

### 6. 임베딩 모델 선택 (text-embedding-3-small)
- **대안 검토:** ko-sroberta(HF, 무료, 로컬 GPU 필요), BGE-M3(HF, 무료, GPU)
- **선택:** OpenAI 3-small ($0.02/1M tokens, 적재 80원 수준)
- **이유:** 비용 미미 + 코드 단순 + 한국어 품질 양호

### 7. ChromaDB 고아 폴더 — 원인과 정리 방법 (2026-06-03 검증)
- **현상:** `db/chroma_db/` 아래 `{UUID}/` 폴더가 5개 쌓임. 그중 1개(`1d1807fd`)만 살아있고 4개는 고아.
- **생성 시점:** **벡터화 재적재(`build_ordinance_vectors.py`) 때마다 1개씩.** 조회(query)로는 안 생김.
  - `delete_collection()`이 `chroma.sqlite3` 메타만 지우고 **HNSW `.bin` 폴더는 안 지움** → 재적재할 때마다 옛 폴더가 고아로 남음.
- **"잠겨서 안 지워짐"의 정체:** 오래 켜둔 Streamlit이 `@st.cache_resource`로 **옛 컬렉션 객체를 메모리에 붙들고** 있어서 그 폴더가 잠김 (= 위 "UUID 캐시" 이슈와 같은 뿌리).
  - **검증 결과:** *새로 띄운 앱은 LIVE 폴더 1개만 잡고 고아는 안 건드림.* → 앱 켜둔 채로 고아 삭제 안전.
- **살아있는 폴더 식별:** `SELECT id FROM segments WHERE scope='VECTOR'` (in `chroma.sqlite3`) → 이게 LIVE UUID. 나머지 `{UUID}/`는 전부 고아.
- **수동 정리:** LIVE 제외한 `{UUID}/` 폴더 `rm -rf`. (재적재 아님 — 폴더만 지우면 됨, OpenAI 비용 0원)
- **근본 해결 (다음 재적재 때 적용):** `build_ordinance_vectors.py` 끝에 아래 추가.
  ```python
  # 적재 완료 후 — 현재 컬렉션이 쓰는 segment 외 고아 폴더 제거
  import sqlite3, shutil
  con = sqlite3.connect(CHROMA_DIR / "chroma.sqlite3")
  live = {r[0] for r in con.execute("SELECT id FROM segments WHERE scope='VECTOR'")}
  con.close()
  for d in CHROMA_DIR.iterdir():
      if d.is_dir() and d.name not in live:
          shutil.rmtree(d, ignore_errors=True)  # 고아 정리
  ```
  → 단, **앱이 켜져 있으면 잠긴 폴더는 못 지움**(`ignore_errors=True`라 그냥 건너뜀). 앱 끈 상태에서 재적재가 가장 깔끔.

### 8. SolarFit 입지·수익 진단 화면 확정 (2026-06-04)
- **화면 구성:** ① 랜딩(지번/질문 입력) ② 입지 진단 ③ 수익성 상세 ④ 지역 추천
- **수익 공식:** `solar_formula_guide.pdf` 기준
  - 연간 발전량 = 용량(99kW) × 발전시간(1,580h) × (1−손실 0.18) ≈ 156,000 kWh
  - SMP 수익 = 발전량 × SMP단가(105원) / REC 수익 = (발전량/1000) × 가중치(1.2) × REC단가(72,000)
  - 손익분기 = 투자비(2.2억) / 연수익, 20년 총수익 = 연수익 × 20
- **토지이용계획 데이터 = 실시간 API 조회로 결정** ⭐
  - 출처: 공공데이터포털 `국토교통부_토지이용계획정보` (= 토지이음 eum.go.kr 동일 데이터)
  - **이유: 사용자가 칠 지번을 예측 불가 → 적재 불가능. 입력 즉시 API 호출 → 화면 표시.**
  - 필요: ① 공공데이터포털 키 ② 지번→PNU 변환(주소 API) ③ 연동
  - (데모 안정성 위해 시연 지번 1~2개는 미리 받아 캐싱 권장)
- **구현 가능/불가 구분 (발표 우선):**
  - ✅ 가능: 발전량·SMP/REC 수익·투자지표(데이터+공식), 조례 RAG(지자체 지원), 종합판정(LLM), 용도지역·농지(토지이용 API)
  - ❌ 불가(GIS 필요) → **"확인 필요(!)"로 표시**: 이격거리 실거리, 인근 변전소 매칭, 진입로 접도, 규제난이도 정밀점수
- **SMP/REC 데이터:** 확보 완료 (`data/SMP_REC/`)

---

## 🤝 팀 협의 필요 (결정 대기 — 2026-06-04)

**수익성 탭**은 아래 값들이 가정치라 팀 협의로 확정해야 함. 결정되면 `src/revenue.py`의 해당 인자만 수정:

| 항목 | 현재값 | 선택지 | 영향 |
|------|--------|--------|------|
| **일사량 보정** (`bonus_revenue`) | 1,014만 (임의) | 제거 / 유지 | 발전량에 일사량이 이미 반영됨 → 별도 보정은 **이중계산 소지**. 제거 시 연수익 3,454만→**2,440만** |
| **투자비** (`invest_won`) | 2.2억 | 그대로 / 현실화 | 99kW 실제 설치비는 보통 1.3~1.5억. 현실화 시 손익분기 9년→**6~7년** |
| **시스템효율 PR** (`pr`) | 0.85 | 확정? | 일사량→발전시간 환산 계수. 0.85 = 업계 표준 |
| **일조량 정밀도** | 충남 proxy | (한계) | 논산 등 관측소 없는 시군구는 인근 관측소값 공유 — 정밀치 않음 |

**입지 진단 탭**은 아직 더미. 실데이터 연결 시 협의 필요:
- 조례 RAG (지자체 지원·종합판정) — 쿼리 확장 필요
- 토지이용 API (용도지역·농지) — 실시간 조회 결정됨, 키 발급 필요
- 이격거리·변전소·진입로 — GIS 없어 **"확인 필요(!)"로 유지**

---

## ⚠ 알려진 이슈·한계

| 이슈 | 영향 | 대응 |
|------|------|------|
| 당진시 자체 조례에 이격거리 명시 없음 | 답변 "조례에서 확인되지 않음" | 데이터 자체 한계, 정상 |
| 천안·부여·금산은 일사량 관측소 X | 시도 평균 보강값 사용 | 정상 (논리 정확) |
| 충남 외 시군구는 ChromaDB 미적재 | 다른 도 선택 시 답변 못 함 | 확장 작업 필요 |
| Streamlit 재실행 후 컬렉션 UUID 캐시 문제 | "Collection does not exist" 오류 | `_refresh_collection()` 자동 재시도 추가됨 |
| ChromaDB 고아 폴더 누적 (`db/chroma_db/{UUID}/`) | 디스크만 차지(동작 무관) | 2026-06-03 고아 4개 수동 삭제 완료. **재발 원인·재적재 시 자동 정리는 아래 메모 참고** |
| 답변에 "제7조" 인용했는데 출처엔 다른 조 표시 | Citation 불일치 | 평가 메트릭으로 측정 예정 |
| KEPCO 데이터 JSON만 있고 DB 미적재 | solarfit.py에 계통여유 표시 못 함 | `scripts/load_kepco_to_db.py` 작성 필요 |

---

## 📊 데이터 현황 (2026-06-03 기준)

### SQLite (`db/solarfit.db`)
| 테이블 | 건수 |
|--------|------|
| region | 229 |
| irradiance | 2,688 |
| ordinance | 약 1,188 (메타) / 충남 169 본문 |
| grid_capacity | 0 (테이블 미생성) |
| power_plant | 0 |
| supply_status | 0 |
| land_price, land_use, smp_rec | 0 |

### ChromaDB (`db/chroma_db/`)
| 컬렉션 | 청크 | 비고 |
|--------|------|------|
| ordinance | **4,251** | 충남 시군구 + 충청남도 광역 |

### KEPCO JSON (`data/raw/kepco_dgen/`)
- 26개 파일 (충청 26 시군구)

### 누적 OpenAI 비용
- 임베딩 적재 약 80원
- 질문 테스트 약 30원
- **총 약 110원**

---

## 🎬 새 세션 시작 시 즉시 할 일 TOP 3

1. **Streamlit 재기동 확인**
   ```bash
   cd C:\Projects\SolarFit
   python -m streamlit run solarfit.py --server.port 9001 --browser.gatherUsageStats false
   ```
   → 당진시 + "보조금" 질문에 답변 + 출처 나오면 정상

2. **발표 슬라이드 작성 시작** (E 담당)
   - 구조도는 ARCHITECTURE.md 참고
   - 데모 시나리오 5개 사전 검증

3. **평가 메트릭 1개 측정** (D 담당)
   - 골드 셋 30건 작성 (CSV)
   - 정규식으로 Citation Accuracy 자동 측정

---

## 🗓 발표 일정 (D-5)

| 날짜 | 핵심 |
|------|------|
| 6/3 수 | (오늘) PROGRESS·ARCHITECTURE 정리 + 충북 확장 |
| 6/4 목 | 평가 스크립트 + 슬라이드 v1 |
| 6/5 금 | 통합 + 슬라이드 v2 + 데모 스크립트 |
| 6/6 토 | 영상 1차 + 슬라이드 v3 |
| 6/7 일 | 리허설 2회 + 영상 최종 |
| **6/8 월 10:00** | **제출** → 11:00 발표 |

---

## 📁 핵심 파일 빠른 참조

| 작업 | 파일 |
|------|------|
| 자치법규 수집 | `scripts/collect_ordinance.py` + `src/api/law_go_kr.py` |
| 벡터화 | `scripts/build_ordinance_vectors.py` |
| RAG 검색·답변 | `src/solarfitRag.py` |
| UI | `solarfit.py` |
| DB 스키마 | `scripts/init_db.py` |
| 환경변수 | `ini/.env` (LAW_API_KEY, OPENAI_API_KEY 등) |
| 구조도 | `ARCHITECTURE.md` |

---

## 💡 다음 작업자에게 한마디

- **데이터 적재 + RAG 검색은 완성됐다.** 손대지 말고 그대로 두어도 발표 가능 수준.
- **시간 부족하면 충남만으로 가도 됨.** 확장은 보너스.
- **발표 슬라이드와 데모 영상이 가장 중요.** P0부터.
- 막히면 `scripts/analyze_station_mapping.py`처럼 작은 진단 도구가 이 프로젝트 어디든 있음. 활용.
