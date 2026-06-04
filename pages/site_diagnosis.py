"""
SolarFit — 소형 태양광(99kW) 입지·수익 진단 (새 화면)
※ 기존 조례 검색(solarfit.py)은 그대로 두고 별도 개발.
※ 더미 데이터 + 실제 수익 공식(src/revenue.py). 실데이터는 추후 연결.

스타일은 아래 'S' 딕셔너리에서만 바꾸면 전체 반영됩니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.revenue import calc_revenue, man, eok  # noqa: E402

st.set_page_config(page_title="SolarFit 입지·수익 진단", page_icon="☀", layout="centered")

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


def render_site():
    s = SITE
    rev = calc_revenue(s["region_code"])

    # 헤더
    st.markdown(f"### {s['addr']}")
    st.markdown(
        f"<span style='color:{S['sub']}'>{s['zone']} · {s['jimok']} · {s['area']}㎡</span>"
        f" &nbsp; {chip('⚠ ' + s['verdict'], S['accent'])}",
        unsafe_allow_html=True,
    )
    st.write("")

    tab1, tab2 = st.tabs(["입지 진단", "수익성"])

    with tab1:
        # 종합 판정
        with st.container(border=True):
            st.markdown(f"**종합 판정**")
            st.markdown(s["judgment"])
            line = "　".join([
                f"<span style='color:{S['ok']}'>✓ 규제 충족</span>",
                f"<span style='color:{S['ok']}'>✓ 지원 있음</span>",
                f"<span style='color:{S['bad']}'>⊘ 계통 부족</span>",
                f"<span style='color:{S['accent']};font-weight:700'>연 {man(rev.annual_total)}</span>",
            ])
            st.markdown(line, unsafe_allow_html=True)

        st.markdown("#### 입지 규제")
        cards_grid(s["regs"], cols=3)

        # 지원 + 계통
        st.markdown(
            f"<div style='display:flex;gap:11px'>"
            f"<div style='flex:1;min-width:0'>"
            + info_box("지자체 지원", "ok", "주민참여형 융자",
                       "최대 90% 융자 → 자기자본 2,200만원 → 연 순익 약 2,800만원 (이자 차감 후)")
            + "</div><div style='flex:1;min-width:0'>"
            + info_box("계통 여유용량", "bad", "여유 부족",
                       "인근 부적변전소 DL 여유 12kW / 신규 99kW 필요 → 연계 대기 예상")
            + "</div></div>",
            unsafe_allow_html=True,
        )

    with tab2:
        render_revenue(s["region_code"])


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
    st.markdown("#### 충남에서 태양광 짓기 좋은 곳")
    st.caption("일조량 · 계통 여유 · 규제 난이도를 종합해 순위를 매겼어요 (99kW 기준)")
    st.markdown(
        f"<span style='color:{S['sub']}'>일조량 <b style='color:{S['value']}'>40%</b>"
        f" 　 계통 여유 <b style='color:{S['value']}'>35%</b>"
        f" 　 규제 난이도 <b style='color:{S['value']}'>25%</b></span>",
        unsafe_allow_html=True,
    )
    st.write("")

    for r in RECOMMEND:
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
        f"충남 서해안(당진·서산·태안)이 일조량이 높고 규제도 완만해 상위권입니다. "
        f"당진시는 계통 여유까지 충분해 1순위. 논산은 일조량은 좋으나 인근 변전소 포화로 "
        f"순위가 내려갔습니다. 시·군을 누르면 부지 단위 진단으로 이동합니다.</div>",
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
elif any(k in q for k in ["추천", "좋은 곳", "어디", "순위"]):
    render_recommend()
else:
    render_site()
