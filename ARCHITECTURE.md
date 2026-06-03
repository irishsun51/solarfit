# 솔라스팟 시스템 아키텍처

> 구조도·RAG 흐름·모델 선택·데이터 스키마 정리.
> 발표 자료에 재사용 가능 (Mermaid 코드 그대로 노션·슬라이드에 붙여넣기).

---

## 1. 전체 아키텍처 (3계층)

```mermaid
graph TB
    subgraph EXT["🌐 외부 데이터 소스 (무료)"]
        E1[code.go.kr<br/>법정동코드]
        E2[기상청 ASOS<br/>일사량]
        E3[KEPCO 빅데이터 API<br/>계통 여유용량]
        E4[국가법령정보 API<br/>자치법규]
    end

    subgraph SCRIPTS["⚙ 적재 스크립트 (scripts/)"]
        S1[build_region.py]
        S2[build_irradiance.py]
        S3[collect_kepco_dgen.py]
        S4[collect_ordinance.py]
        S5[build_ordinance_vectors.py]
    end

    subgraph STORE["💾 로컬 저장소"]
        DB[(SQLite<br/>solarfit.db<br/>region, irradiance,<br/>ordinance)]
        VDB[(ChromaDB<br/>db/chroma_db/<br/>4,251 청크)]
    end

    subgraph APP["🖥 웹앱 (로컬 PC)"]
        UI[Streamlit UI<br/>solarfit.py<br/>:9001]
        RAG[RAG 모듈<br/>src/solarfitRag.py]
    end

    subgraph OPENAI["🤖 OpenAI API"]
        EMB[text-embedding-3-small]
        LLM[gpt-4o-mini]
    end

    USER([👤 사용자])

    E1 --> S1 --> DB
    E2 --> S2 --> DB
    E3 --> S3 --> DB
    E4 --> S4 --> DB
    S4 --> S5
    S5 -- 임베딩 --> EMB
    S5 --> VDB

    USER -- 브라우저 --> UI
    UI --> RAG
    RAG --> DB
    RAG --> VDB
    RAG -- 질문 임베딩 --> EMB
    RAG -- 답변 생성 --> LLM
```

---

## 2. RAG 조회 흐름 (질문 → 답변)

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 사용자
    participant UI as Streamlit UI
    participant RAG as src/solarfitRag.py
    participant SQL as SQLite
    participant CDB as ChromaDB
    participant OAI as OpenAI API

    U->>UI: 시군구 선택 + 질문 입력
    UI->>SQL: 시군구 메타·일사량 조회
    SQL-->>UI: 지표 표시
    UI->>RAG: answer_stream(question, region_code)

    RAG->>OAI: 질문 임베딩 요청<br/>(text-embedding-3-small)
    OAI-->>RAG: 1536차원 벡터

    RAG->>CDB: 시군구 청크 검색<br/>where region_code=44270
    CDB-->>RAG: 시군구 후보 5건
    RAG->>CDB: 광역 청크 검색<br/>where region_code=44000
    CDB-->>RAG: 광역 후보 5건

    RAG->>RAG: 쿼터 합치기<br/>(시군구 60% + 광역 40%)<br/>→ top-5

    RAG->>OAI: gpt-4o-mini 답변 생성<br/>(stream=True)
    OAI-->>RAG: 토큰 스트림
    RAG-->>UI: 토큰 yield
    UI-->>U: 화면 실시간 표시 + 출처
```

### 핵심 — 시군구 쿼터 분배

| 항목 | 단순 RAG | **우리 방식** |
|------|---------|-------------|
| 검색 방식 | top-5 한 번에 | 시군구·광역 따로 검색 |
| 순위 기준 | distance 단순 정렬 | 시군구 60% 강제 + 거리 정렬 |
| 결과 | 광역 위주 (시군구 누락) | 시군구 자체 조례 항상 포함 |

코드 위치: `src/solarfitRag.py` `OrdinanceRAG.search()`

---

## 3. 적재 파이프라인 (배치 흐름)

```mermaid
flowchart LR
    A1[code.go.kr<br/>법정동코드.txt] --> B1[build_region.py<br/>+ init_db.py]
    B1 --> C1[(SQLite<br/>region: 229)]

    A2[기상청 ASOS<br/>월별 일사량 CSV] --> B2[build_irradiance.py]
    B2 --> C2[(SQLite<br/>irradiance: 2,688)]

    A3[KEPCO API<br/>분산전원 정보] --> B3[collect_kepco_dgen.py]
    B3 --> C3[(JSON 파일<br/>26개 시군구)]

    A4[법령정보 API<br/>자치법규] --> B4[collect_ordinance.py<br/>--bodies]
    B4 --> C4[(SQLite ordinance<br/>+ JSON 본문)]
    C4 --> B5[build_ordinance_vectors.py<br/>+ OpenAI 임베딩]
    B5 --> C5[(ChromaDB<br/>4,251 청크)]
```

---

## 4. 모듈 의존성

```mermaid
graph LR
    subgraph SRC[src/]
        CLIENT[api/client.py<br/>APIClient 베이스]
        KEPCO[api/kepco_dgen.py]
        LAW[api/law_go_kr.py]
        RAG[solarfitRag.py<br/>OrdinanceRAG]
    end

    subgraph SCR[scripts/]
        S1[collect_kepco_dgen.py]
        S2[collect_ordinance.py]
        S3[build_ordinance_vectors.py]
    end

    subgraph APP[루트]
        APP1[solarfit.py]
    end

    CLIENT --> KEPCO
    CLIENT --> LAW
    KEPCO --> S1
    LAW --> S2
    RAG --> APP1
    S3 -.OpenAI.-> RAG
    S3 -.ChromaDB.-> RAG
```

---

## 5. 데이터 스키마 (SQLite)

```mermaid
erDiagram
    region ||--o{ irradiance : "1:N"
    region ||--o{ power_plant : "1:N"
    region ||--o{ supply_status : "1:N"
    region ||--o{ ordinance : "1:N"

    region {
        TEXT region_code PK "5자리"
        TEXT sido
        TEXT sigungu
    }
    irradiance {
        TEXT region_code FK
        INT month
        REAL irradiance "MJ/m²"
    }
    ordinance {
        TEXT law_id PK
        TEXT mst "법령일련번호"
        TEXT law_name
        TEXT institution
        TEXT region_code FK
        TEXT level "광역|시군구"
        TEXT law_type "조례|고시"
        DATE effective_date
        TEXT full_text "JSON 백업"
    }
    power_plant {
        INT plant_id PK
        TEXT region_code FK
        REAL capacity_kw
    }
    supply_status {
        TEXT region_code FK
        INT year
        REAL gen_mwh
    }
```

---

## 6. ChromaDB 청크 메타데이터

각 청크에 부착되는 메타:

```json
{
    "region_code": "44270",
    "sido": "충청남도",
    "sigungu": "당진시",
    "institution": "충청남도 당진시",
    "level": "시군구",
    "law_id": "2050xxx",
    "law_name": "당진시 공영주차장 신·재생에너지 발전설비 조례",
    "law_type": "조례",
    "mst": "1487xxx",
    "article_num": "000500",
    "article_title": "다른 조례와의 관계"
}
```

검색 시 메타 필터:
- `where={"region_code": "44270"}` — 당진시만
- `where={"$and": [{"region_code":"44000"}, {"level":"광역"}]}` — 충청남도 광역만

---

## 7. 모델 선택 — Before vs After

원래 계획 (HANDOFF.md) → OpenAI 키 확보 후 단순화:

### Before (캐글 자체 운영)
| 구분 | 모델 | 위치 | GPU |
|------|------|------|-----|
| 임베딩 | `ko-sroberta-multitask` (HF) | 캐글 (1회성) | T4 |
| LLM | `EXAONE 3.5` / `Qwen2.5` (Ollama) | 캐글 (매 질문) | T4 상시 |
| 연결 | Cloudflare Tunnel | - | - |

### After (현재)
| 구분 | 모델 | 위치 | GPU |
|------|------|------|-----|
| 임베딩 | **`text-embedding-3-small`** | OpenAI 서버 | 불필요 |
| LLM | **`gpt-4o-mini`** | OpenAI 서버 | 불필요 |
| 연결 | HTTPS API | - | - |

### 변화 요약
- 캐글·Ollama·Tunnel 모두 **제거**
- 응답 속도 3~5초 → **1~2초**
- 운영 복잡도 ↓ / 안정성 ↑
- 1주 데모 비용: 무료 → 약 **200원**

---

## 8. 사용 모델 상세

| 영역 | 모델 | 차원/특성 | 비용 |
|------|------|----------|------|
| 임베딩 | `text-embedding-3-small` | 1536차원, OpenAI | $0.02/1M tokens |
| LLM | `gpt-4o-mini` | 스트리밍, 128K 컨텍스트 | $0.15/$0.60 per 1M |
| 벡터 인덱스 | ChromaDB HNSW | 코사인 유사도 | 무료 (로컬) |

질문 1회당:
- 임베딩 호출 1회 (~0.001원)
- LLM 호출 1회 입력 ~2,000 + 출력 ~300 토큰 (~0.9원)
- **합 약 0.9원/질문**

---

## 9. 인프라 비교 (Before/After 인포그래픽용)

```
Before                       After
─────────                    ─────
[캐글 노트북]                  [내 PC]
  ├─ Ollama 서버 (GPU)          ├─ Streamlit
  ├─ 모델 다운 ~500MB           ├─ ChromaDB (로컬)
  └─ Cloudflare Tunnel          └─ SQLite (로컬)
       ↓ 터널 URL                   ↓ HTTPS
[내 PC]                       [OpenAI 서버]
  └─ Streamlit                  ├─ 임베딩 모델
  └─ ChromaDB                    └─ gpt-4o-mini
```

---

## 10. 발표 자료 활용 가이드

| 슬라이드 | 사용 다이어그램 |
|---------|---------------|
| 시스템 아키텍처 | §1 전체 아키텍처 |
| RAG 흐름 | §2 시퀀스 다이어그램 |
| 데이터 적재 | §3 파이프라인 |
| 데이터 스키마 | §5 ER 다이어그램 |
| 모델 선택 어필 | §7 Before/After 표 |
| 시군구 쿼터 차별화 | §2 핵심 박스 |

→ Mermaid 코드 그대로 노션·Mermaid Live Editor에 붙여 PNG export 가능.

---

## 11. 한 줄 요약 (노션·발표 표지용)

> "공공 API 4종 → SQLite + ChromaDB 이중 저장 → OpenAI 임베딩·LLM 기반 RAG. 시군구·광역 쿼터 분배로 지역 특수성 보존. 로컬 PC + 인터넷만으로 동작, 1주 비용 200원."
