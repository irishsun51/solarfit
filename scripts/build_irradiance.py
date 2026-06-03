"""
일사량 적재 — 기상청 ASOS 월자료 → irradiance 테이블

입력 (원본, 읽기만):
  Data/일사량/META_관측지점정보_*.csv     관측소 메타 (지점, 주소, 위경도)
  Data/일사량/OBS_ASOS_MNH_*.csv          월별 합계 일사량(MJ/m²)

처리:
  1) META 파싱 → 각 관측소의 시도/시군구/위경도 추출
  2) 각 관측소 → region_code 매칭
     · 주소의 시도+시군구가 region 테이블과 정확 매칭되면 그걸로
     · "ㅇㅇ시 ㅇㅇ구" 같이 일반구인 경우 parent 시로 (region 테이블 기준)
  3) OBS 파싱 → 2015~2024 기간만 → 결측(0/공백) 제외 → 관측소별
     · 월별 평균 (1~12)
     · 연합계 평균 (12개월 모두 있는 해만 사용)
  4) region_code → 관측소 할당
     · 직접 매핑된 시군구: 자기 관측소 사용
     · 미매핑 시군구: 같은 시도 관측소들 중 위경도 평균과 가장 가까운 것
       (시군구 중심좌표가 없으므로 시도 내 보강만 수행)
  5) irradiance 테이블 적재 (region_code, month, irradiance)
"""
from __future__ import annotations

import csv
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
META_CSV = ROOT / "data" / "일사량" / "META_관측지점정보_20260602163727.csv"
OBS_CSV  = ROOT / "data" / "일사량" / "OBS_ASOS_MNH_20260602161351.csv"

YEAR_FROM = 2015
YEAR_TO   = 2024


# ──────────────────────────────────────────
# 거리 계산
# ──────────────────────────────────────────
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lng2 - lng1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ──────────────────────────────────────────
# 주소 → (시도, 시군구) 파싱
# ──────────────────────────────────────────
# "수원시권선구" 같은 일반구 붙여쓰기 패턴 → parent 시로 분리
_GU_ATTACHED = re.compile(r"^([가-힣]+시)([가-힣]+구)$")


def parse_address(addr: str) -> tuple[str, str]:
    """주소 문자열에서 (sido, sigungu) 추출. 일반구·세종 특수 처리 포함.

    처리 사례:
      "강원특별자치도 고성군 토성면 봉포리"   → (강원특별자치도, 고성군)
      "경기도 수원시 권선구 고색동"           → (경기도, 수원시)        # 띄어쓰기
      "경기도 수원시권선구 고색동"            → (경기도, 수원시)        # 붙여쓰기
      "충청북도 청주시흥덕구 복대동"          → (충청북도, 청주시)
      "세종특별자치시 새롬동"                → (세종특별자치시, 세종특별자치시)
      ""                                  → ("", "")
    """
    parts = addr.split()
    if not parts:
        return "", ""

    sido = parts[0]

    # 세종 특수: 시군구 레벨이 곧 광역
    if sido == "세종특별자치시":
        return sido, "세종특별자치시"

    if len(parts) < 2:
        return sido, ""

    second = parts[1]

    # 1) 일반구 붙여쓰기 "XX시YY구" → "XX시"
    m = _GU_ATTACHED.match(second)
    if m:
        return sido, m.group(1)

    # 2) 띄어쓰기로 분리된 일반구 "XX시 YY구 ..." → "XX시"
    if (
        len(parts) >= 3
        and second.endswith("시")
        and parts[2].endswith("구")
    ):
        return sido, second

    return sido, second


# ──────────────────────────────────────────
# META 파싱
# ──────────────────────────────────────────
def parse_meta() -> list[dict]:
    stations = []
    with open(META_CSV, encoding="cp949") as f:
        # 기상청 META 파일은 첫 줄이 빈 줄, 둘째 줄이 헤더
        lines = [ln for ln in f if ln.strip()]
        rdr = csv.DictReader(lines)
        for r in rdr:
            try:
                lat = float(r["위도"])
                lng = float(r["경도"])
            except (KeyError, ValueError):
                continue
            addr = (r.get("지점주소") or "").strip()
            sido, sigungu = parse_address(addr)
            stations.append({
                "id": r["지점"].strip(),
                "name": (r.get("지점명") or "").strip(),
                "addr": addr,
                "lat": lat,
                "lng": lng,
                "addr_sido": sido,
                "addr_sigungu": sigungu,
            })
    return stations


# ──────────────────────────────────────────
# 관측소 → region_code 매핑 (직접)
# ──────────────────────────────────────────
def map_stations_to_region(
    stations: list[dict], region_lookup: dict[tuple[str, str], str]
) -> None:
    """각 관측소에 region_code 채워넣기 (in-place). 매칭 안 되면 None."""
    sigungu_to_codes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for (sido, sigungu), code in region_lookup.items():
        sigungu_to_codes[sigungu].append((sido, code))

    for s in stations:
        s["region_code"] = None

        # 1) (시도, 시군구) 정확 일치
        code = region_lookup.get((s["addr_sido"], s["addr_sigungu"]))
        if code:
            s["region_code"] = code
            continue

        # 2) 시도명이 region 쪽과 약간 다를 수 있음 (강원특별자치도 vs 강원도 등) → sigungu만으로 시도
        candidates = sigungu_to_codes.get(s["addr_sigungu"], [])
        if len(candidates) == 1:
            s["region_code"] = candidates[0][1]


# ──────────────────────────────────────────
# OBS 파싱 → 평균 산출
# ──────────────────────────────────────────
def parse_obs() -> tuple[dict[str, dict[int, float]], dict[str, float]]:
    """관측소별 월평균(1~12) 과 연합계 평균 반환."""
    monthly: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    yearly_sum: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    yearly_cnt: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    with open(OBS_CSV, encoding="cp949") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            sid = (r.get("지점") or "").strip()
            ymd = (r.get("일시") or "").strip()  # "YYYY-MM"
            try:
                val = float((r.get("합계 일사량(MJ/m2)") or "").strip() or 0)
                year_s, month_s = ymd.split("-")
                year = int(year_s)
                month = int(month_s)
            except (ValueError, KeyError):
                continue

            if val <= 0:
                continue  # 결측/0 제외
            if not (YEAR_FROM <= year <= YEAR_TO):
                continue

            monthly[sid][month].append(val)
            yearly_sum[sid][year] += val
            yearly_cnt[sid][year] += 1

    avg_monthly: dict[str, dict[int, float]] = {}
    for sid, by_month in monthly.items():
        avg_monthly[sid] = {m: sum(vs) / len(vs) for m, vs in by_month.items()}

    avg_annual: dict[str, float] = {}
    for sid in yearly_sum:
        complete = [s for y, s in yearly_sum[sid].items() if yearly_cnt[sid][y] == 12]
        if complete:
            avg_annual[sid] = sum(complete) / len(complete)

    return avg_monthly, avg_annual


# ──────────────────────────────────────────
# 미매핑 시군구 보강 (시도 내 가장 가까운 관측소)
# ──────────────────────────────────────────
def assign_missing_regions(
    regions: list[tuple[str, str, str]],
    stations: list[dict],
    avg_monthly: dict[str, dict[int, float]],
) -> dict[str, str]:
    """region_code → station_id 결정.

    1) region에 자체 매핑된 관측소가 있으면 그걸 사용
    2) 없으면 같은 시도의 관측소들 중 가장 가까운 것 (관측소 위경도 기준)
       시군구 중심좌표가 없으므로, 같은 시도 관측소들의 평균 위경도와 비교
    3) 그래도 없으면 None
    """
    region_to_sid: dict[str, str] = {}

    # 1) 직접 매핑된 region들
    region_station_map: dict[str, dict] = {}
    for s in stations:
        rc = s.get("region_code")
        if rc and s["id"] in avg_monthly:
            # 같은 region에 2개 이상 관측소면 첫 번째 유지 (드문 케이스)
            region_station_map.setdefault(rc, s)
    for rc, s in region_station_map.items():
        region_to_sid[rc] = s["id"]

    # 2) 시도별 그룹 (보강용)
    # region_lookup: (sido, sigungu) → code
    sido_to_stations: dict[str, list[dict]] = defaultdict(list)
    for s in stations:
        if s["id"] in avg_monthly:
            sido_to_stations[s["addr_sido"]].append(s)

    # 시도 명칭 정규화 매핑 (region.sido ↔ 주소 sido)
    def normalize_sido(name: str) -> str:
        # "강원특별자치도" ↔ "강원도" 같은 변동 흡수
        return (name.replace("특별자치도", "도")
                    .replace("특별자치시", "시")
                    .replace("특별시", "")
                    .replace("광역시", ""))

    sido_normalized_map: dict[str, list[dict]] = defaultdict(list)
    for sido, ss in sido_to_stations.items():
        sido_normalized_map[normalize_sido(sido)].extend(ss)

    # 3) 미매핑 region들 → 같은 시도 관측소들 중 평균 위경도와 가장 가까운 것
    missing_count = 0
    for rc, sido, sigungu in regions:
        if rc in region_to_sid:
            continue
        # 같은 시도(정규화) 관측소
        candidates = sido_normalized_map.get(normalize_sido(sido), [])
        if not candidates:
            missing_count += 1
            continue
        # 시도 내 관측소들의 평균 좌표 (proxy for region center)
        avg_lat = sum(c["lat"] for c in candidates) / len(candidates)
        avg_lng = sum(c["lng"] for c in candidates) / len(candidates)
        # 그 평균에 가장 가까운 관측소를 그 region에 할당
        # (정확한 region 중심좌표가 없으므로 차선책)
        # 더 나은 방법: 시도 안에서 무작위 분산보다 가운데에 가까운 관측소 → 평균값에 가까움
        best = min(candidates, key=lambda c: haversine_km(c["lat"], c["lng"], avg_lat, avg_lng))
        region_to_sid[rc] = best["id"]

    if missing_count:
        print(f"⚠ 매핑 실패한 시군구: {missing_count}개 (해당 시도에 관측소 없음)")

    return region_to_sid


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
def main() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT region_code, sido, sigungu FROM region ORDER BY region_code")
    regions = cur.fetchall()
    region_lookup = {(sido, sigungu): rc for rc, sido, sigungu in regions}
    print(f"region: {len(regions)}건")

    stations = parse_meta()
    print(f"관측소: {len(stations)}건")

    map_stations_to_region(stations, region_lookup)
    mapped = sum(1 for s in stations if s.get("region_code"))
    print(f"  └ region에 직접 매핑: {mapped}건")

    avg_monthly, avg_annual = parse_obs()
    print(f"OBS 처리: 월평균 산출 관측소 {len(avg_monthly)}건 / 연합계 산출 {len(avg_annual)}건 "
          f"(기간 {YEAR_FROM}~{YEAR_TO})")

    region_to_sid = assign_missing_regions(regions, stations, avg_monthly)
    print(f"region → 관측소 할당: {len(region_to_sid)}/{len(regions)}건")

    # 적재
    cur.execute("DELETE FROM irradiance")
    inserted = 0
    for rc, sid in region_to_sid.items():
        for month, val in avg_monthly.get(sid, {}).items():
            cur.execute(
                "INSERT INTO irradiance (region_code, month, irradiance) "
                "VALUES (?, ?, ?)",
                (rc, month, round(val, 2)),
            )
            inserted += 1
    con.commit()
    print(f"irradiance 적재: {inserted}건")

    # 샘플 출력
    print("\n[당진시 44270 월별 일사량]")
    cur.execute(
        "SELECT month, irradiance FROM irradiance WHERE region_code='44270' ORDER BY month"
    )
    for m, v in cur.fetchall():
        print(f"  {m:>2d}월: {v:>7.1f} MJ/m²")

    cur.execute(
        "SELECT SUM(irradiance) FROM irradiance WHERE region_code='44270'"
    )
    annual = cur.fetchone()[0]
    print(f"  연합계 ≈ {annual:.0f} MJ/m²")

    con.close()


if __name__ == "__main__":
    main()
