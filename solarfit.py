"""
솔라스팟 - 소형태양광 입지 추천 서비스 (실 DB + RAG 연결판)

실행:
    cd C:\\Projects\\SolarFit
    python -m streamlit run solarfit.py

전제:
    - db/solarfit.db (region, irradiance 등 적재 완료)
    - db/chroma_db/ (ordinance 컬렉션 적재 완료)
    - ini/.env에 OPENAI_API_KEY 설정
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "db" / "solarfit.db"
ENV_PATH = ROOT / "ini" / ".env"


# ──────────────────────────────────────────
# 환경 / 캐시 자원
# ──────────────────────────────────────────
def load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


@st.cache_resource
def get_rag():
    """ChromaDB + OpenAI 클라이언트 1회 초기화."""
    from src.solarfitRag import OrdinanceRAG
    return OrdinanceRAG()


@st.cache_data(ttl=600)
def list_regions_with_ordinance() -> list[dict]:
    """조례 데이터가 있는 시군구 목록 (드롭다운용)."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT DISTINCT r.region_code, r.sido, r.sigungu,
               COUNT(o.law_id) AS n_ord
          FROM region r
          LEFT JOIN ordinance o
                 ON o.region_code = r.region_code AND o.level='시군구'
         GROUP BY r.region_code
         HAVING n_ord > 0
         ORDER BY r.sido, r.sigungu
        """
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=600)
def get_region_metrics(region_code: str) -> dict:
    """시군구 핵심 지표 (지표 일부는 데이터 없으면 None)."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    region = con.execute(
        "SELECT * FROM region WHERE region_code=?", (region_code,)
    ).fetchone()
    if not region:
        con.close()
        return {}

    # 연 합계 일사량
    irr = con.execute(
        "SELECT SUM(irradiance) AS annual FROM irradiance WHERE region_code=?",
        (region_code,),
    ).fetchone()

    # 시군구 자체 조례 수
    own_ord = con.execute(
        "SELECT COUNT(*) AS c FROM ordinance WHERE region_code=? AND level='시군구'",
        (region_code,),
    ).fetchone()

    # 광역 조례 수 (시도 단위)
    sido_code = region_code[:2] + "000"
    sido_ord = con.execute(
        "SELECT COUNT(*) AS c FROM ordinance WHERE region_code=? AND level='광역'",
        (sido_code,),
    ).fetchone()

    con.close()
    return {
        "region_code": region["region_code"],
        "sido": region["sido"],
        "sigungu": region["sigungu"],
        "annual_irradiance": irr["annual"] if irr and irr["annual"] else None,
        "own_ordinance_n": own_ord["c"],
        "sido_ordinance_n": sido_ord["c"],
    }


def estimate_score(m: dict) -> int:
    """간이 추천 점수 (지표 누락분은 기본값)."""
    irr = m.get("annual_irradiance") or 0
    irr_score = min(100, max(0, (irr - 4000) / 15))  # 4,000~5,500 → 0~100
    return int(irr_score * 0.5 + 50)  # 단순 정규화 (나머지 지표 도입 전 placeholder)


# ──────────────────────────────────────────
# 페이지 설정 + 사이드바
# ──────────────────────────────────────────
st.set_page_config(page_title="솔라스팟", page_icon="☀", layout="wide")

if "selected" not in st.session_state:
    st.session_state.selected = None
if "chat" not in st.session_state:
    st.session_state.chat = {}  # region_code → [(role, text, sources)]

st.markdown(
    "## ☀ 솔라스팟  <small style='color:gray'>지역으로 찾는 소형태양광 입지</small>",
    unsafe_allow_html=True,
)
st.caption("실 DB(SQLite) + 자치법규 RAG(ChromaDB + OpenAI). MVP — 충남 위주 데이터.")

regions = list_regions_with_ordinance()
if not regions:
    st.error("조례 적재된 시군구가 없습니다. scripts/collect_ordinance.py + build_ordinance_vectors.py를 먼저 실행하세요.")
    st.stop()

left, right = st.columns([1, 1.4], gap="large")


# ──────────────────────────────────────────
# 좌측: 시군구 검색 / TOP5
# ──────────────────────────────────────────
with left:
    st.subheader("🔍 시군구 선택")

    sido_options = sorted({r["sido"] for r in regions})
    sido = st.selectbox("광역", sido_options, index=sido_options.index("충청남도") if "충청남도" in sido_options else 0)
    candidates = [r for r in regions if r["sido"] == sido]

    sigungu_labels = [f"{r['sigungu']} ({r['n_ord']} 조례)" for r in candidates]
    sel_idx = st.selectbox(
        "시군구",
        range(len(candidates)),
        format_func=lambda i: sigungu_labels[i],
        index=0,
    )
    selected = candidates[sel_idx]
    st.session_state.selected = selected["region_code"]

    st.divider()
    st.subheader("🏆 추천 TOP 5  <small>(현 시도 내)</small>", anchor=False)
    st.markdown("<small style='color:gray'>* 점수는 일사량 기반 임시 정규화 (다른 지표 추가 예정)</small>", unsafe_allow_html=True)

    scored = []
    for r in candidates:
        m = get_region_metrics(r["region_code"])
        score = estimate_score(m)
        scored.append((score, r, m))
    scored.sort(key=lambda x: -x[0])

    for score, r, m in scored[:5]:
        is_sel = r["region_code"] == st.session_state.selected
        bar = "▰" * (score // 10) + "▱" * (10 - score // 10)
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{r['sigungu']}** · {score}점")
            top[1].markdown(f"<small>조례 {r['n_ord']}건</small>", unsafe_allow_html=True)
            irr = m.get("annual_irradiance")
            irr_txt = f"{irr:,.0f} MJ/m²" if irr else "—"
            st.markdown(
                f"<small>{bar}　연 일사량: {irr_txt}</small>",
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────
# 우측: 상세 + RAG Q&A
# ──────────────────────────────────────────
with right:
    if not st.session_state.selected:
        st.info("좌측에서 시군구를 선택하세요.")
        st.stop()

    m = get_region_metrics(st.session_state.selected)
    sido_ = m["sido"]
    sigungu_ = m["sigungu"]
    region_code = m["region_code"]

    st.subheader(f"📍 {sido_} {sigungu_}")

    score = estimate_score(m)
    st.info(f"임시 추천 점수: **{score}점**  (일사량 기반 단순 정규화)")

    st.markdown("**◤ 핵심 지표 ◢**")
    cols = st.columns(4)
    irr = m.get("annual_irradiance")
    cols[0].metric("연 일사량", f"{irr:,.0f} MJ/m²" if irr else "—")
    cols[1].metric("자체 조례", f"{m['own_ordinance_n']}건")
    cols[2].metric("광역 조례", f"{m['sido_ordinance_n']}건")
    cols[3].metric("region_code", region_code)

    st.markdown("**◤ 100kW 기준 수익 시뮬레이션 ◢**")
    if irr:
        # 매우 간이: 일사량(MJ/m²) × 면적 환산 + 효율 18% + SMP 가정 142원
        annual_kwh = int(irr / 3.6 * 0.18 * 100)
        revenue_万 = round(annual_kwh * 142 / 10000)
        with st.container(border=True):
            st.markdown(
                f"연 발전량 약 **{annual_kwh:,} kWh** × SMP 142원 "
                f"≈ 연 수익 약 **{revenue_万:,}만원**  <small>(REC 별도)</small>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("일사량 데이터 없음")

    st.divider()
    st.markdown(f"**💬 조례 Q&A**　:gray[지역: {sigungu_}]")
    st.markdown(
        ":gray[💡 추천 질문: 농지 설치 가능? / 보조금 단가 / 이격거리 / 인허가 절차 / 영농형 가능?]"
    )

    # 채팅 이력
    history = st.session_state.chat.get(region_code, [])
    for role, text, sources in history:
        with st.chat_message(role):
            st.write(text)
            if sources:
                st.caption("📎 " + " · ".join(sources))

    if prompt := st.chat_input(f"{sigungu_} 조례에 대해 질문하세요..."):
        history.append(("user", prompt, None))
        with st.chat_message("user"):
            st.write(prompt)

        try:
            rag = get_rag()
            with st.chat_message("assistant"):
                token_gen, chunks = rag.answer_stream(prompt, region_code=region_code, k=5)
                full = st.write_stream(token_gen)
                cited = rag.cited_chunks(full, chunks)   # 답변에 표기된 [N]만 출처로
                sources = list({rag.format_source(c) for c in cited})[:3]
                if sources:
                    st.caption("📎 " + " · ".join(sources) + "　|　⚠ 답변은 참고용, 원문 확인 필요")

            history.append(("assistant", full, sources))
            st.session_state.chat[region_code] = history
        except Exception as e:
            st.error(f"RAG 호출 실패: {e}")
