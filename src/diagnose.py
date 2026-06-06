"""주소 → 입지 진단 (항목별 분리). 새 화면(site_diagnosis)이 호출하는 단일 진입점.

화면 측은 `diagnose(주소)` 한 번 호출 후 반환 dict를 카드에 매핑만 하면 됨.
내부에서 주소→지역 변환 / 이격 딕셔너리 조회 / 지자체 지원 RAG / 용도지역 캐시 /
종합판정 LLM 을 모두 처리.

반환 구조:
    {
      "주소": str, "pnu": str, "region_code": str, "시군구": str,
      "이격":   {있음, 도로, 주거, 관광지, 부지경계, 기타, 난이도, 출처, 링크},
      "지원":   {text, sources},          # 조례 RAG (하이브리드)
      "용도지역": {zone_main, zones, farmland} | None,   # VWorld 캐시
      "종합판정": str,                     # LLM 종합
    }
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

from src.solarfitRag import OrdinanceRAG, LLM_MODEL
from src.api.land_use import LandUseClient, addr_to_pnu
from src.revenue import get_sunshine_hours

ROOT = Path(__file__).resolve().parent.parent
SETBACK_PATH = ROOT / "data" / "byeolpyo" / "setback.json"
LANDUSE_DIR = ROOT / "data" / "land_use"
KEPCO_DIR = ROOT / "data" / "raw" / "kepco_dgen"
DB_PATH = ROOT / "db" / "solarfit.db"

# 지자체 지원 카드용 고정 질문 (사용자 질문이 없으니 우리가 정함)
SUPPORT_QUERY = "태양광 발전 보조금·융자 등 지자체 지원"


@lru_cache(maxsize=1)
def _load_setback() -> dict:
    return json.loads(SETBACK_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _get_rag() -> OrdinanceRAG:
    return OrdinanceRAG()


# ──────────────────────────────────────────
# ① 주소 → region_code
# ──────────────────────────────────────────
def address_to_region(address: str) -> tuple[str, str]:
    """주소 → (pnu19, region_code5).
    region_code = pnu 앞 5자리(시군구). 일반구 등으로 region 테이블에 없으면
    주소의 '○○시/군' 토큰으로 보강 조회."""
    pnu = addr_to_pnu(address)
    rc = pnu[:5]
    con = sqlite3.connect(DB_PATH)
    try:
        if con.execute("SELECT 1 FROM region WHERE region_code=?", (rc,)).fetchone():
            return pnu, rc
        m = re.search(r"(\S+[시군])", address)
        if m:
            row = con.execute(
                "SELECT region_code FROM region WHERE sigungu=?", (m.group(1),)
            ).fetchone()
            if row:
                return pnu, row[0]
    finally:
        con.close()
    return pnu, rc


# ──────────────────────────────────────────
# ② 이격 (딕셔너리 조회 — RAG 아님)
# ──────────────────────────────────────────
def get_setback(region_code: str) -> dict:
    entry = _load_setback().get(region_code)
    if not entry:
        return {"있음": False, "메시지": "해당 시군구 이격 데이터 없음"}
    out = {"있음": True, "난이도": entry.get("난이도"),
           "출처": entry.get("출처"), "링크": entry.get("링크")}
    out.update(entry.get("이격", {}))
    return out


# ──────────────────────────────────────────
# ③ 지자체 지원 (RAG 하이브리드 검색)
# ──────────────────────────────────────────
def get_support(region_code: str) -> dict:
    rag = _get_rag()
    res = rag.answer(SUPPORT_QUERY, region_code=region_code, k=5)
    return {"text": res["answer"].strip(), "sources": res["sources"]}


# ──────────────────────────────────────────
# ④ 용도지역 (VWorld — 캐시 hit → 즉시 / miss → 실호출 + 캐시 저장)
# ──────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_landuse_client() -> LandUseClient | None:
    """VWorld 클라이언트 1회 초기화. 키 없으면 None."""
    key = os.environ.get("VWORLD_API_KEY")
    if not key:
        return None
    # ⚠ VWorld는 키 발급 시 등록한 도메인 문자열과 정확히 일치해야 함.
    # 이 키는 'localhost'로 등록됨(스킴/포트 없이) — 'http://localhost:9001'은 INCORRECT_KEY.
    return LandUseClient(api_key=key, domain="localhost")


def get_landuse(pnu: str) -> dict | None:
    """PNU → 용도지역·농지 dict.
    1) data/land_use/{pnu}.json 캐시 hit → 즉시 반환
    2) miss → VWorld API 실호출 → 파싱 → 캐시 저장 → 반환
    3) 키 없음/네트워크 실패 등 → None (diagnose는 그대로 진행)
    """
    fp = LANDUSE_DIR / f"{pnu}.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8")).get("parsed")

    client = _get_landuse_client()
    if client is None:
        return None
    try:
        raw = client.get_raw(pnu)
    except Exception as e:
        print(f"[get_landuse] VWorld fetch failed for {pnu}: {e}", file=sys.stderr)
        return None

    # 에러 응답 감지: 정상은 landUses.field[], 에러는 landUses.resultCode
    lu = raw.get("landUses") if isinstance(raw, dict) else None
    if isinstance(lu, dict) and lu.get("resultCode"):
        print(
            f"[get_landuse] VWorld error for {pnu}: "
            f"{lu['resultCode']} {lu.get('resultMsg','')}",
            file=sys.stderr,
        )
        return None  # 캐시 오염 방지: 에러 응답은 저장하지 않음

    parsed = LandUseClient.parse(raw)
    try:
        LANDUSE_DIR.mkdir(parents=True, exist_ok=True)
        fp.write_text(
            json.dumps({"pnu": pnu, "parsed": parsed, "raw": raw},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[get_landuse] cache write failed: {e}", file=sys.stderr)
    return parsed


# ──────────────────────────────────────────
# 계통 여유 (KEPCO JSON — 변전소/변압기/DL 여유용량)
# ──────────────────────────────────────────
def get_grid(region_code: str, need_kw: float = 99) -> dict:
    """시군구 계통 여유. data/raw/kepco_dgen/{region}.json 직접 조회.
    각 행 연계가능 = min(vol1 변전소, vol2 변압기, vol3 DL) 여유용량(kW).
    best_kw = 그 시군구에서 가능한 최대 단일 연계용량."""
    fp = KEPCO_DIR / f"{region_code}.json"
    if not fp.exists():
        return {"best_kw": None, "status": "확인 필요", "n": 0}
    rows = json.loads(fp.read_text(encoding="utf-8")).get("data", [])
    conn = [
        min(r["vol1"], r["vol2"], r["vol3"])
        for r in rows if all(k in r for k in ("vol1", "vol2", "vol3"))
    ]
    if not conn:
        return {"best_kw": None, "status": "확인 필요", "n": 0}
    best = max(conn)
    # 99kW 연계 기준: 여유 규모로 충분/보통 (충남은 모두 99kW엔 충분, 규모차만)
    status = "충분" if best >= 9000 else ("보통" if best >= need_kw else "부족")
    return {"best_kw": best, "status": status, "n": len(conn)}


# ──────────────────────────────────────────
# ⑤ 종합판정 (LLM)
# ──────────────────────────────────────────
def judge(sigungu: str, setback: dict, support: dict, landuse: dict | None) -> str:
    rag = _get_rag()
    parts = [f"지역: {sigungu}"]
    if setback.get("있음"):
        parts.append(
            f"이격기준(난이도 {setback.get('난이도')}): 도로 {setback.get('도로')}, "
            f"주거 {setback.get('주거')}, 부지경계 {setback.get('부지경계')}, "
            f"기타 {setback.get('기타')}"
        )
    else:
        parts.append("이격: 조례상 규정 없음/미확인")
    if landuse:
        parts.append(
            f"용도지역: {landuse.get('zone_main')} / "
            f"농지규제: {'있음' if landuse.get('farmland') else '없음'}"
        )
    parts.append(f"지자체 지원: {support['text'][:300]}")
    ctx = "\n".join(parts)

    system = (
        "너는 태양광 소형발전(99kW) 입지 진단 전문가다. 아래 정보를 종합해 "
        "2~3문장으로 판정하라. ① 가능/조건부 가능/어려움을 먼저 밝히고 "
        "② 핵심 근거(용도지역·이격·지원)를 들고 ③ 확인이 필요한 변수"
        "(이격 실측거리)는 '확인 필요'로 명시하라. 계통 여유는 별도 표기되므로 "
        "언급하지 마라. 과장 없이 사실 기반."
    )
    resp = rag._openai.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": ctx}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# ──────────────────────────────────────────
# 단일 진입점
# ──────────────────────────────────────────
def diagnose(address: str) -> dict:
    """주소 → 항목별 진단 dict. (화면은 이것만 호출)"""
    pnu, region_code = address_to_region(address)
    setback = get_setback(region_code)
    support = get_support(region_code)
    landuse = get_landuse(pnu)
    sigungu = setback.get("시군구") or _sigungu_name(region_code)
    verdict = judge(sigungu, setback, support, landuse)
    return {
        "주소": address, "pnu": pnu, "region_code": region_code, "시군구": sigungu,
        "이격": setback,
        "지원": support,
        "용도지역": landuse,
        "종합판정": verdict,
    }


# ──────────────────────────────────────────
# 시군구명 질의 → 지역 단위 진단 (지번 없이)
# ──────────────────────────────────────────
@lru_cache(maxsize=1)
def _sigungu_index() -> dict:
    """시군구명(+'시/군' 제거형) → region_code. setback.json 기준 충남 15개."""
    idx = {}
    for code, e in _load_setback().items():
        if code.startswith("_"):
            continue
        name = e.get("sigungu")
        if not name:
            continue
        idx[name] = code                                      # "당진시"
        idx[re.sub(r"(특별자치시|광역시|시|군|구)$", "", name)] = code  # "당진"
    return idx


def find_region_in_text(text: str) -> str | None:
    """질문에 충남 시군구명이 있으면 region_code 반환(가장 긴 매치 우선)."""
    hits = [(n, c) for n, c in _sigungu_index().items() if n and n in text]
    if not hits:
        return None
    hits.sort(key=lambda x: len(x[0]), reverse=True)
    return hits[0][1]


def diagnose_region(region_code: str) -> dict:
    """시군구 단위 진단(지번 없음). 용도지역·농지는 지번(PNU) 필요해 제외.
    이격·지자체지원(RAG)·계통·종합판정(LLM)만."""
    setback = get_setback(region_code)
    support = get_support(region_code)
    sigungu = _sigungu_name(region_code)
    verdict = judge(sigungu, setback, support, None)
    return {
        "주소": None, "pnu": None, "region_code": region_code, "시군구": sigungu,
        "이격": setback, "지원": support, "용도지역": None,
        "종합판정": verdict, "grid": get_grid(region_code),
    }


# ──────────────────────────────────────────
# 추천 랭킹 (배치형 — 여러 시군구 줄세우기)
# ──────────────────────────────────────────
# 규제 난이도 → 점수(낮을수록 좋음=높은 점수) / 화면 색상 status
_REG_SCORE = {"낮음": 100, "보통": 60, "높음": 25}
_REG_STATUS = {"낮음": "ok", "보통": "warn", "높음": "bad"}
_GRID_STATUS = {"충분": "ok", "보통": "warn", "부족": "bad", "확인 필요": "warn"}
# 가중치: 일조량 40 / 계통 35 / 규제 25
_W_SUN, _W_GRID, _W_REG = 0.40, 0.35, 0.25
# 정렬 키: (1차 기준, 2차=종합점수). 동점이면 종합점수(일조+계통+규제)로 가름.
# 모두 reverse=True(내림차순) 통일 — reg_strict만 -_reg로 방향 반전.
_SORT_KEYS = {
    "score":      lambda r: (r["score"], r["score"]),
    "reg_easy":   lambda r: (r["_reg"],  r["score"]),   # 규제 약한 순(낮음 먼저)
    "reg_strict": lambda r: (-r["_reg"], r["score"]),   # 규제 강한 순(높음 먼저)
    "grid":       lambda r: (r["_grid"], r["score"]),   # 계통 여유 큰 순
    "sun":        lambda r: (r["_sun"],  r["score"]),   # 일조량 큰 순
}


def recommend(sido_prefix: str = "44", sort_by: str = "score") -> list[dict]:
    """시군구 추천 랭킹. 일조량(SQLite)·계통(KEPCO)·규제(setback) 종합.
    sort_by: score(종합)/reg_easy(규제약)/reg_strict(규제강)/grid(계통)/sun(일조).
    반환 키: rank, name, region_code, score, sun, grid, grid_s, reg, reg_s."""
    data = _load_setback()
    codes = [k for k in data if not k.startswith("_") and k.startswith(sido_prefix)]
    suns = {c: get_sunshine_hours(c) for c in codes}
    smax, smin = max(suns.values()), min(suns.values())
    savg = sum(suns.values()) / len(suns)
    grids = {c: get_grid(c) for c in codes}
    gvals = [g["best_kw"] for g in grids.values() if g["best_kw"]]
    gmax, gmin = (max(gvals), min(gvals)) if gvals else (1, 0)

    rows = []
    for c in codes:
        e = data[c]
        nan = e.get("난이도", "보통")
        h = suns[c]
        g = grids[c]
        gbest = g["best_kw"]
        sun_score = 100 * (h - smin) / (smax - smin) if smax > smin else 100
        grid_score = (100 * (gbest - gmin) / (gmax - gmin)
                      if gbest and gmax > gmin else (50 if gbest else 0))
        c_sun = round(_W_SUN * sun_score)              # 일조 기여(0~40)
        c_grid = round(_W_GRID * grid_score)           # 계통 기여(0~35)
        c_reg = round(_W_REG * _REG_SCORE.get(nan, 60))  # 규제 기여(0~25)
        score = c_sun + c_grid + c_reg
        pct = round((h - savg) / savg * 100) if savg else 0
        rows.append({
            "name": e.get("sigungu", c),
            "region_code": c,
            "score": score,
            "c_sun": c_sun, "c_grid": c_grid, "c_reg": c_reg,
            "sun": f"{h:,.0f}h · {'+' if pct >= 0 else ''}{pct}%",
            "sun_s": "ok" if pct >= 0 else "warn",   # 충남평균 대비 +면 초록/−면 노랑
            "grid": f"{g['status']} ({gbest:,.0f}kW)" if gbest else "확인 필요",
            "grid_s": _GRID_STATUS.get(g["status"], "warn"),
            "reg": nan,
            "reg_s": _REG_STATUS.get(nan, "warn"),
            "_reg": _REG_SCORE.get(nan, 60),   # 규제 점수(높을수록 약함)
            "_grid": gbest or 0,
            "_sun": h,
        })
    keyfn = _SORT_KEYS.get(sort_by, _SORT_KEYS["score"])
    rows.sort(key=keyfn, reverse=True)  # 동점은 2차 기준(종합점수)로 자동 가름
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _sigungu_name(region_code: str) -> str:
    entry = _load_setback().get(region_code, {})
    if entry.get("sigungu"):
        return entry["sigungu"]
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute(
            "SELECT sigungu FROM region WHERE region_code=?", (region_code,)
        ).fetchone()
        return row[0] if row else ""
    finally:
        con.close()
