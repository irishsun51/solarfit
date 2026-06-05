"""
SolarFit — 소형 태양광(99kW) 입지·수익 진단 (새 화면)
※ 기존 조례 검색(solarfit.py)은 그대로 두고 별도 개발.
※ 더미 데이터 + 실제 수익 공식(src/revenue.py). 실데이터는 추후 연결.

스타일은 아래 'S' 딕셔너리에서만 바꾸면 전체 반영됩니다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.revenue import calc_revenue, man, eok  # noqa: E402
from src.diagnose import (  # noqa: E402
    recommend as _recommend,
    diagnose as _diagnose,
    get_grid as _get_grid,
)

st.set_page_config(page_title="SolarFit 입지·수익 진단", page_icon="☀", layout="centered")


@st.cache_data(ttl=600)
def get_recommend(sort_by="score"):
    """추천 랭킹(충남 고정) — sort_by로 정렬 기준 변경. RAG 미사용이라 가벼움."""
    return _recommend("44", sort_by=sort_by)


@st.cache_data(ttl=3600, show_spinner="진단 중 (조례 RAG + 종합 판정)…")
def diagnose_cached(address: str) -> dict:
    """주소→진단 결과 캐시(1h). 같은 주소 재호출 시 RAG·LLM 비용 0."""
    res = _diagnose(address)
    res["grid"] = _get_grid(res["region_code"])
    return res


_SORT_LABEL = {
    "score": "종합점수", "reg_easy": "규제 난이도 낮은", "reg_strict": "규제 난이도 높은",
    "grid": "계통 여유 큰", "sun": "일조량 높은",
}


def _sort_intent(q: str) -> str:
    """질문에서 정렬 기준 추출. (규제 강/약, 계통, 일조 → 아니면 종합)"""
    if "규제" in q:
        if any(k in q for k in ("강", "센", "빡", "엄격", "높", "까다")):
            return "reg_strict"
        return "reg_easy"        # 규제 + 약/낮/완화 등 (기본 약한 곳)
    if any(k in q for k in ("계통", "변전소", "여유", "접속")):
        return "grid"
    if any(k in q for k in ("일조", "일사", "햇", "발전량")):
        return "sun"
    return "score"


_JIBUN_RE = re.compile(r"(?:동|리|면|읍|가|로|길)\s*(?:산\s*)?\d+(?:-\d+)?\s*$")


def _is_jibun(q: str) -> bool:
    """지번 주소처럼 보이면 True → 단일 진단. 아니면(추천/질의) → 리스트."""
    q = q.strip()
    if _JIBUN_RE.search(q):
        return True
    return bool(re.search(r"\d+(?:-\d+)?$", q)) and any(
        t in q for t in ("시", "군", "구", "동", "리", "면", "읍"))


# ── 진단 결과 → 카드 status 매핑 ────────────────────────────
_ZONE_OK = ("계획관리", "생산관리", "자연녹지", "준공업", "일반공업", "전용공업")
_ZONE_BAD = ("농림", "보전관리", "자연환경", "농업진흥", "공원", "상수원")
_GRID_STATUS = {"충분": "ok", "보통": "warn", "부족": "bad", "확인 필요": "warn"}


def _setback_display(value: str) -> tuple[str, str]:
    """이격 값 → (표시값, status). 기준값만 있고 실측 불가라 warn 고정."""
    v = (value or "").strip()
    if not v or v == "-":
        return ("해당 없음", "ok")
    return (v, "warn")


def _zone_status(zone_main: str | None) -> str:
    if not zone_main:
        return "warn"
    if any(k in zone_main for k in _ZONE_OK):
        return "ok"
    if any(k in zone_main for k in _ZONE_BAD):
        return "bad"
    return "warn"


def _verdict_summary(text: str) -> tuple[str, str]:
    """종합판정 LLM 첫 문장에서 가능/조건부/어려움 추출."""
    t = (text or "").replace(" ", "")[:80]
    if "어려움" in t or "불가" in t:
        return ("어려움", "bad")
    if "조건부" in t:
        return ("조건부 가능", "warn")
    if "가능" in t:
        return ("가능", "ok")
    return ("판정 확인", "warn")

# ════════════════════════════════════════════════════════
# 🎨 스타일 — 여기만 바꾸면 전체 반영
# ════════════════════════════════════════════════════════
S = {
    "card_bg": "#13273a",        # 카드 배경
    "card_border": "#273e54",    # 카드 테두리
    "label": "#8fa6ba",          # 라벨(회색)
    "sub": "#6b8093",            # 보조 설명(연회색)
    "value": "#e8eef3",          # 기본 값(흰색)
    "ok": "#5bbf86",             # 충족(초록)
    "warn": "#e0a83a",           # 확인 필요(노랑)
    "bad": "#d9645a",            # 부족(빨강)
    "accent": "#c8a13a",         # 배지·강조(골드)
    "rev_bg": "#16324a",         # 연 수익 박스 배경
    "rev_border": "#2d5074",
}
STATUS = {"ok": ("✓", "ok"), "warn": ("⚠", "warn"), "bad": ("⊘", "bad")}


# ════════════════════════════════════════════════════════
# 공통 컴포넌트
# ════════════════════════════════════════════════════════
def chip(text: str, bg: str, fg: str = "#15202b") -> str:
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 11px;"
        f"border-radius:12px;font-size:0.82em;font-weight:700'>{text}</span>"
    )


def _card_html(label: str, value: str, sub: str = "", status: str | None = None) -> str:
    icon, ckey = STATUS.get(status, ("", "value"))
    vcolor = S[ckey]
    val = f"{icon} {value}".strip()
    sub_html = (
        f"<div style='color:{S['sub']};font-size:0.8em;margin-top:5px'>{sub}</div>"
        if sub else ""
    )
    return (
        f"<div style='background:{S['card_bg']};border:1px solid {S['card_border']};"
        f"border-radius:9px;padding:13px 15px;height:100%;box-sizing:border-box'>"
        f"<div style='color:{S['label']};font-size:0.85em;margin-bottom:7px'>{label}</div>"
        f"<div style='color:{vcolor};font-size:1.12em;font-weight:700'>{val}</div>"
        f"{sub_html}</div>"
    )


def cards_grid(items: list[tuple], cols: int = 3) -> None:
    """items = [(label, value, sub, status), ...] → cols열 그리드."""
    for i in range(0, len(items), cols):
        row = items[i:i + cols]
        cells = "".join(
            f"<div style='flex:1;min-width:0'>{_card_html(*it)}</div>" for it in row
        )
        cells += "".join("<div style='flex:1'></div>" for _ in range(cols - len(row)))
        st.markdown(
            f"<div style='display:flex;gap:11px;margin-bottom:11px'>{cells}</div>",
            unsafe_allow_html=True,
        )


def info_box(title: str, status: str, head: str, body: str) -> str:
    icon, ckey = STATUS[status]
    return (
        f"<div style='background:{S['card_bg']};border:1px solid {S['card_border']};"
        f"border-radius:9px;padding:14px 16px;height:100%;box-sizing:border-box'>"
        f"<div style='color:{S['label']};font-size:0.9em;margin-bottom:8px'>{title}</div>"
        f"<div style='color:{S[ckey]};font-weight:700;margin-bottom:6px'>{icon} {head}</div>"
        f"<div style='color:{S['sub']};font-size:0.85em;line-height:1.5'>{body}</div></div>"
    )


# ════════════════════════════════════════════════════════
# 더미 데이터
# ════════════════════════════════════════════════════════
SITE = {
    "region_code": "44230",
    "addr": "충남 논산시 부적면 충곡리 200",
    "zone": "계획관리지역", "jimok": "답", "area": 892,
    "verdict": "조건부 가능",
    "judgment": (
        "이격거리·용도지역은 충족하고 수익성도 양호하나, "
        "**인근 변전소 계통 여유 부족**과 **진입로 미확인**이 변수입니다. "
        "계통 연계 가능 시점을 한전에 먼저 확인하세요."
    ),
    # (label, value, sub, status)
    "regs": [
        ("도로 이격", "충족 240m", "기준 200m", "ok"),
        ("주거 이격", "충족 610m", "10호↑ 500m", "ok"),
        ("관광지 이격", "충족", "기준 200m", "ok"),
        ("진입로 조성", "확인 필요", "접도 4m 미확인", "warn"),
        ("농지 규제", "해당 없음", "우량농지 아님", "ok"),
        ("용도지역", "계획관리", "태양광 가능", "ok"),
    ],
}

RECOMMEND = [
    {"rank": 1, "name": "당진시", "score": 92, "sun": "1,620h · +12%",
     "grid": "충분 (480kW)", "grid_s": "ok", "reg": "낮음", "reg_s": "ok"},
    {"rank": 2, "name": "서산시", "score": 87, "sun": "1,600h · +11%",
     "grid": "보통 (210kW)", "grid_s": "warn", "reg": "낮음", "reg_s": "ok"},
    {"rank": 3, "name": "태안군", "score": 83, "sun": "1,610h · +11%",
     "grid": "보통 (160kW)", "grid_s": "warn", "reg": "보통", "reg_s": "warn"},
    {"rank": 4, "name": "논산시", "score": 71, "sun": "1,580h · +9%",
     "grid": "부족 (40kW)", "grid_s": "bad", "reg": "보통", "reg_s": "warn"},
]

EXAMPLES = [
    "충남 논산시 부적면 충곡리 123-4",
    "충남에서 태양광 짓기 좋은 곳 추천해줘",
    "당진에 변전소 여유 있는 부지 있어?",
    "99kW 20년 수익이 예금보다 나아?",
]


# ════════════════════════════════════════════════════════
# 화면
# ════════════════════════════════════════════════════════
def render_landing():
    st.markdown("##### 이렇게 물어보세요")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, use_container_width=True, key=f"ex{i}"):
            st.session_state.query = ex
            st.rerun()


def render_site(address: str):
    """주소 → diagnose() 실호출 → 카드 매핑. 캐시·에러 처리 포함."""
    try:
        d = diagnose_cached(address)
    except Exception as e:
        st.error(f"진단 실패: {e}")
        st.caption(
            "주소가 시/군/읍/면/리/번지까지 정확한지, "
            "ini/.env의 OPENAI_API_KEY가 유효한지 확인하세요."
        )
        return

    region_code = d["region_code"]
    sigungu = d.get("시군구") or "—"
    setback = d.get("이격") or {}
    support = d.get("지원") or {}
    landuse = d.get("용도지역") or {}
    grid = d.get("grid") or {"status": "확인 필요", "best_kw": None, "n": 0}
    zone_main = landuse.get("zone_main")
    farmland = landuse.get("farmland")
    verdict_text = d.get("종합판정") or ""
    verdict_label, verdict_status = _verdict_summary(verdict_text)
    rev = calc_revenue(region_code)

    # 헤더
    st.markdown(f"### {d['주소']}")
    meta = sigungu + (f" · {zone_main}" if zone_main else "")
    chip_bg = {"ok": S["ok"], "warn": S["accent"], "bad": S["bad"]}[verdict_status]
    chip_icon = STATUS[verdict_status][0]
    st.markdown(
        f"<span style='color:{S['sub']}'>{meta}</span>"
        f" &nbsp; {chip(f'{chip_icon} {verdict_label}', chip_bg)}",
        unsafe_allow_html=True,
    )
    st.write("")

    tab1, tab2 = st.tabs(["입지 진단", "수익성"])

    with tab1:
        # 종합 판정
        grid_st = _GRID_STATUS.get(grid["status"], "warn")
        with st.container(border=True):
            st.markdown("**종합 판정**")
            st.markdown(verdict_text or "_LLM 판정 텍스트 없음_")
            parts = []
            if support.get("text"):
                parts.append(f"<span style='color:{S['ok']}'>✓ 지원 정보 확인</span>")
            else:
                parts.append(f"<span style='color:{S['warn']}'>⚠ 지원 정보 부족</span>")
            parts.append(
                f"<span style='color:{S[grid_st]}'>{STATUS[grid_st][0]} 계통 {grid['status']}</span>"
            )
            parts.append(
                f"<span style='color:{S['accent']};font-weight:700'>연 {man(rev.annual_total)}</span>"
            )
            st.markdown("　".join(parts), unsafe_allow_html=True)

        st.markdown("#### 입지 규제")
        if setback.get("있음"):
            v_road, s_road = _setback_display(setback.get("도로"))
            v_jugeo, s_jugeo = _setback_display(setback.get("주거"))
            v_gwan, s_gwan = _setback_display(setback.get("관광지"))
            v_buji, s_buji = _setback_display(setback.get("부지경계"))
            sub_basis = f"난이도 {setback.get('난이도', '?')} · 실측 필요"
        else:
            v_road = v_jugeo = v_gwan = v_buji = "데이터 없음"
            s_road = s_jugeo = s_gwan = s_buji = "warn"
            sub_basis = "조례 미수집 시군구"

        if farmland is True:
            farmland_val, farmland_sub, farmland_st = "농지 해당", "농지전용허가 필요", "warn"
        elif farmland is False:
            farmland_val, farmland_sub, farmland_st = "해당 없음", "농지 아님", "ok"
        else:
            farmland_val, farmland_sub, farmland_st = "확인 필요", "VWorld 캐시 없음", "warn"

        cards_grid([
            ("도로 이격", v_road, sub_basis, s_road),
            ("주거 이격", v_jugeo, sub_basis, s_jugeo),
            ("관광지 이격", v_gwan, sub_basis, s_gwan),
            ("부지경계", v_buji, sub_basis, s_buji),
            ("용도지역", zone_main or "확인 필요",
             "VWorld" if zone_main else "VWorld 캐시 없음",
             _zone_status(zone_main)),
            ("농지 규제", farmland_val, farmland_sub, farmland_st),
        ], cols=3)

        if setback.get("있음") and setback.get("출처"):
            link, src = setback.get("링크"), setback["출처"]
            st.caption(
                f"📎 이격 근거: [{src}]({link})" if link else f"📎 이격 근거: {src}"
            )

        # 지원 + 계통
        support_text = (support.get("text") or "").strip()
        if support_text:
            support_status = "ok"
            support_head = "지원 정보 확인"
            body = support_text[:280] + ("…" if len(support_text) > 280 else "")
            if support.get("sources"):
                body += (
                    f"<br><br><b style='color:{S['label']}'>출처</b>: "
                    + " · ".join(support["sources"][:3])
                )
            support_body = body
        else:
            support_status = "warn"
            support_head = "지원 정보 부족"
            support_body = "해당 시군구 자치법규에서 보조금·융자 등 지원 규정을 찾지 못했습니다."

        if grid.get("best_kw"):
            grid_body = (
                f"변전소·DL 최대 {grid['best_kw']:,.0f} kW 여유 "
                f"({grid.get('n', 0)}건 중 최대) · 99kW 연계 기준"
            )
        else:
            grid_body = "KEPCO 분산전원 데이터 없음 — 한전에 직접 확인 필요."

        st.markdown(
            f"<div style='display:flex;gap:11px'>"
            f"<div style='flex:1;min-width:0'>"
            + info_box("지자체 지원 (RAG)", support_status, support_head, support_body)
            + "</div><div style='flex:1;min-width:0'>"
            + info_box("계통 여유용량", grid_st, f"여유 {grid['status']}", grid_body)
            + "</div></div>",
            unsafe_allow_html=True,
        )

    with tab2:
        render_revenue(region_code)


def render_revenue(region_code=None):
    rev = calc_revenue(region_code)
    st.markdown("#### 일조량 & 발전")
    cards_grid([
        ("연간 일조량", f"{rev.sunshine_h:,.0f} h", "전국 평균 +9%", None),
        ("연간 발전량", f"{rev.annual_kwh:,.0f} kWh", f"99kW · 이용률 {rev.util_rate*100:.0f}%", None),
    ], cols=2)

    st.markdown("#### 수익성 상세 (현금 매수 · 투자비 2.2억)")
    cards_grid([
        ("SMP 수익", man(rev.smp_revenue), f"{rev.smp_price:g}원/kWh (2025)", None),
        ("REC 수익", man(rev.rec_revenue), f"{rev.rec_count} REC × {rev.rec_price:,.0f}원", None),
        ("일사량 보정", f"+{man(rev.bonus_revenue)}", "고일사 가산", None),
    ], cols=3)

    st.markdown(
        f"<div style='background:{S['rev_bg']};border:1px solid {S['rev_border']};"
        f"padding:15px 18px;border-radius:9px;overflow:hidden;margin:4px 0 12px'>"
        f"<span style='float:left;color:{S['label']};line-height:1.9'>연 예상 수익</span>"
        f"<span style='float:right;font-size:1.45em;font-weight:800;color:{S['value']}'>"
        f"약 {man(rev.annual_total)}</span></div>",
        unsafe_allow_html=True,
    )

    cards_grid([
        ("손익분기", f"약 {rev.payback_years}년", "", None),
        ("20년 총수익", f"약 {eok(rev.total_20yr)}", "", None),
        ("예금(3%) 대비", f"+{eok(rev.vs_savings)}", "", None),
    ], cols=3)
    st.caption("※ 참고용 · 최종 인허가·연계는 지자체·한전 판단에 따름")


def render_recommend():
    sort_by = _sort_intent(st.session_state.query)
    items = get_recommend(sort_by)
    st.markdown("#### 충남에서 태양광 짓기 좋은 곳")
    if sort_by == "score":
        st.caption("일조량 · 계통 여유(KEPCO) · 규제 난이도(조례) 종합 순위 (99kW 기준)")
    else:
        st.caption(f"'{_SORT_LABEL[sort_by]}' 순으로 정렬했어요 (99kW 기준)")
    st.markdown(
        f"<span style='color:{S['sub']}'>일조량 <b style='color:{S['value']}'>40%</b>"
        f" 　 계통 여유 <b style='color:{S['value']}'>35%</b>"
        f" 　 규제 난이도 <b style='color:{S['value']}'>25%</b></span>",
        unsafe_allow_html=True,
    )
    st.write("")

    for r in items:
        head = (
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-bottom:8px'>"
            f"<span style='font-size:1.15em;font-weight:700;color:{S['value']}'>"
            f"{r['rank']}위 　 {r['name']}</span>"
            f"{chip('종합 ' + str(r['score']) + '점', '#2d5074', '#dce8f5')}</div>"
        )
        cols3 = (
            f"<div style='display:flex;gap:18px;color:{S['sub']};font-size:0.88em'>"
            f"<div>일조량<br><b style='color:{S['value']}'>{r['sun']}</b></div>"
            f"<div>계통 여유<br><b style='color:{S[r['grid_s']]}'>{r['grid']}</b></div>"
            f"<div>규제 난이도<br><b style='color:{S[r['reg_s']]}'>{r['reg']}</b></div></div>"
        )
        st.markdown(
            f"<div style='background:{S['card_bg']};border:1px solid {S['card_border']};"
            f"border-radius:9px;padding:14px 16px;margin-bottom:10px'>{head}{cols3}</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style='background:{S['card_bg']};border:1px solid {S['card_border']};"
        f"border-radius:9px;padding:14px 16px;color:{S['sub']};font-size:0.9em;line-height:1.6'>"
        f"<b style='color:{S['value']}'>해석</b><br>"
        f"{'일조량·계통·규제를 종합한 순위입니다.' if sort_by=='score' else _SORT_LABEL[sort_by]+' 곳 기준으로 정렬했습니다.'} "
        f"이 기준에서는 <b>{items[0]['name']}</b>이(가) 1위입니다. 충남은 일조량이 대체로 비슷하고 "
        f"99kW 연계엔 계통 여유도 충분해, 주로 규제 난이도와 계통 규모가 순위를 가릅니다. "
        f"시·군을 누르면 부지 단위 진단으로 이동합니다.</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════
st.markdown(
    "<style>"
    ".stTabs [data-baseweb='tab'] p {font-size:1.1rem; font-weight:600;}"
    ".stTabs [data-baseweb='tab'] {padding-top:6px; padding-bottom:6px;}"
    "</style>",
    unsafe_allow_html=True,
)
st.markdown("## ☀ SolarFit")
st.caption("소형 태양광(99kW) 입지·수익 진단")

if "query" not in st.session_state:
    st.session_state.query = ""

c1, c2 = st.columns([5, 1])
inp = c1.text_input(
    "q", value=st.session_state.query,
    placeholder="지번을 입력하거나 무엇이든 물어보세요",
    label_visibility="collapsed",
)
if c2.button("진단 →", use_container_width=True):
    st.session_state.query = inp
    st.rerun()

q = st.session_state.query.strip()
st.divider()

if not q:
    render_landing()
elif _is_jibun(q):
    render_site(q)          # 지번(예: 충곡리 200) → 단일 진단 (diagnose 호출)
else:
    render_recommend()      # Q&A·추천·그 외 모든 질의 → 리스트 유지
