"""
태양광 수익 계산 (solar_formula_guide.pdf 공식 기준)
99kW 소형 태양광 발전소 기준.

단가(SMP/REC)는 db/solarfit.db 의 smp_rec 테이블 연평균을 읽어 사용.
(인자로 직접 넘기면 그 값을 우선 적용)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"


@dataclass
class RevenueResult:
    capacity_kw: float
    sunshine_h: float
    annual_kwh: float
    util_rate: float
    smp_price: float           # 적용 SMP 단가(원/kWh)
    rec_price: float           # 적용 REC 단가(원/REC)
    smp_revenue: int
    rec_count: int
    rec_revenue: int
    annual_total: int
    payback_years: float
    total_20yr: int
    vs_savings: int


def get_smp_rec_prices(db_path: Path = DB_PATH) -> tuple[float, float]:
    """smp_rec 테이블 연평균 (SMP 원/kWh, REC 원/REC). 없으면 목업 기본값."""
    try:
        con = sqlite3.connect(db_path)
        row = con.execute("SELECT AVG(smp), AVG(rec) FROM smp_rec").fetchone()
        con.close()
        if row and row[0] is not None:
            return round(row[0], 2), round(row[1])
    except Exception:
        pass
    return 105.0, 72000.0  # fallback (DB 없을 때)


def get_sunshine_hours(region_code: str | None, pr: float = 0.85,
                       db_path: Path = DB_PATH) -> float:
    """irradiance 테이블 → 연 발전시간(h).
    연 일사량(MJ/m²) ÷ 3.6 = kWh/m²(표준 발전시간), × PR(시스템효율)."""
    if not region_code:
        return 1580.0
    try:
        con = sqlite3.connect(db_path)
        mj = con.execute(
            "SELECT SUM(irradiance) FROM irradiance WHERE region_code=?",
            (region_code,),
        ).fetchone()[0]
        con.close()
        if mj:
            return round(mj / 3.6 * pr)
    except Exception:
        pass
    return 1580.0


@lru_cache(maxsize=1)
def national_avg_hours(pr: float = 0.85, db_path_str: str = str(DB_PATH)) -> float:
    """전국 시군구 평균 연 발전시간(h). 일조량 비교 기준(전국 평균 대비 %)."""
    try:
        con = sqlite3.connect(db_path_str)
        rows = con.execute(
            "SELECT region_code, SUM(irradiance) FROM irradiance GROUP BY region_code"
        ).fetchall()
        con.close()
        hs = [s / 3.6 * pr for _, s in rows if s]
        if hs:
            return sum(hs) / len(hs)
    except Exception:
        pass
    return 1207.0


def calc_revenue(
    region_code: str | None = None,   # 주면 irradiance에서 발전시간 산출
    capacity_kw: float = 99,
    sunshine_h: float | None = None,  # None이면 region_code 기반 DB값
    pr: float = 0.85,                 # 시스템효율
    smp_price: float | None = None,   # None이면 DB 연평균
    rec_price: float | None = None,   # None이면 DB 연평균
    rec_weight: float = 1.2,
    invest_won: float = 2.2e8,
    save_rate: float = 0.03,
    years: int = 20,
) -> RevenueResult:
    # 발전시간: 인자 없으면 region_code 기반 DB(일사량)에서
    if sunshine_h is None:
        sunshine_h = get_sunshine_hours(region_code, pr)

    # 단가: 인자 없으면 DB(smp_rec)에서
    if smp_price is None or rec_price is None:
        db_smp, db_rec = get_smp_rec_prices()
        smp_price = db_smp if smp_price is None else smp_price
        rec_price = db_rec if rec_price is None else rec_price

    # 1) 연간 발전량 = 용량 × 발전시간
    annual_kwh = capacity_kw * sunshine_h
    util_rate = sunshine_h / (365 * 24)

    # 2) SMP 수익
    smp_revenue = round(annual_kwh * smp_price)

    # 3) REC 수익 = (발전량/1000) × 가중치 × 단가
    rec_count = round((annual_kwh / 1000) * rec_weight)
    rec_revenue = round(rec_count * rec_price)

    # 4) 연 예상 수익 (SMP + REC)
    annual_total = round(smp_revenue + rec_revenue)

    # 5) 투자 지표
    payback_years = round(invest_won / annual_total, 1)
    total_20yr = annual_total * years
    save_interest = invest_won * save_rate * years
    vs_savings = round((total_20yr - invest_won) - save_interest)

    return RevenueResult(
        capacity_kw=capacity_kw,
        sunshine_h=sunshine_h,
        annual_kwh=round(annual_kwh),
        util_rate=util_rate,
        smp_price=smp_price,
        rec_price=rec_price,
        smp_revenue=smp_revenue,
        rec_count=rec_count,
        rec_revenue=rec_revenue,
        annual_total=annual_total,
        payback_years=payback_years,
        total_20yr=total_20yr,
        vs_savings=vs_savings,
    )


def eok(won: float) -> str:
    return f"{won/1e8:.1f}억"


def man(won: float) -> str:
    return f"{round(won/1e4):,}만원"
