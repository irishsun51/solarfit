"""
관측소 ↔ 시군구 매핑 현황 분석
- 시군구 안에 관측소 0개 / 1개 / 2개 이상
- 미매핑 시군구는 어떤 관측소로 대체되는지
- 10년(2015~2024) 데이터 있는 관측소만 카운트
"""
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# build_irradiance의 parse_address를 그대로 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_irradiance import parse_address  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
META_CSV = ROOT / "data" / "일사량" / "META_관측지점정보_20260602163727.csv"
OBS_CSV = ROOT / "data" / "일사량" / "OBS_ASOS_MNH_20260602161351.csv"
YEAR_FROM, YEAR_TO = 2015, 2024


def stations_with_obs() -> set[str]:
    """2015~2024 기간에 유효 데이터가 1건이라도 있는 관측소 ID 집합."""
    valid = set()
    with open(OBS_CSV, encoding="cp949") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                val = float((r.get("합계 일사량(MJ/m2)") or "0").strip() or 0)
                year = int((r["일시"] or "").split("-")[0])
            except (ValueError, KeyError):
                continue
            if val > 0 and YEAR_FROM <= year <= YEAR_TO:
                valid.add(r["지점"].strip())
    return valid


def parse_meta():
    stations = []
    with open(META_CSV, encoding="cp949") as f:
        lines = [ln for ln in f if ln.strip()]
        rdr = csv.DictReader(lines)
        for r in rdr:
            addr = (r.get("지점주소") or "").strip()
            sido, sigungu = parse_address(addr)
            stations.append({
                "id": r["지점"].strip(),
                "name": (r.get("지점명") or "").strip(),
                "addr_sido": sido,
                "addr_sigungu": sigungu,
                "addr": addr,
            })
    return stations


def main():
    con = sqlite3.connect(DB_PATH)
    regions = con.execute(
        "SELECT region_code, sido, sigungu FROM region ORDER BY sido, sigungu"
    ).fetchall()
    con.close()
    region_lookup = {(s, g): rc for rc, s, g in regions}
    sigungu_to_codes = defaultdict(list)
    for (sido, sigungu), code in region_lookup.items():
        sigungu_to_codes[sigungu].append((sido, code))

    valid_ids = stations_with_obs()
    stations = parse_meta()

    # 관측소 → region_code 매핑 (10년 데이터 있는 것만)
    region_to_stations: dict[str, list[dict]] = defaultdict(list)
    unmapped_stations = []  # 주소 매칭 실패한 관측소
    no_obs_stations = []    # 메타엔 있지만 10년 OBS 없음

    for s in stations:
        if s["id"] not in valid_ids:
            no_obs_stations.append(s)
            continue

        # 1) (시도, 시군구) 정확 매칭
        code = region_lookup.get((s["addr_sido"], s["addr_sigungu"]))
        # 2) sigungu만으로 유일하면
        if not code:
            cands = sigungu_to_codes.get(s["addr_sigungu"], [])
            if len(cands) == 1:
                code = cands[0][1]
        if code:
            region_to_stations[code].append(s)
        else:
            unmapped_stations.append(s)

    # 카테고리 분류
    zero, one, multi = [], [], []
    for rc, sido, sigungu in regions:
        n = len(region_to_stations.get(rc, []))
        if n == 0:
            zero.append((rc, sido, sigungu))
        elif n == 1:
            one.append((rc, sido, sigungu, region_to_stations[rc][0]))
        else:
            multi.append((rc, sido, sigungu, region_to_stations[rc]))

    # 출력
    print("=" * 70)
    print(f"전체 시군구: {len(regions)}건")
    print(f"10년 OBS 보유 관측소: {len(valid_ids)}건 / META 전체 {len(stations)}건")
    print(f"주소 매핑 실패 관측소: {len(unmapped_stations)}건")
    print("=" * 70)

    print(f"\n📊 시군구별 관측소 분포")
    print(f"  ① 관측소 2개 이상   {len(multi):>4d}건")
    print(f"  ② 관측소 정확히 1개 {len(one):>4d}건")
    print(f"  ③ 관측소 없음       {len(zero):>4d}건   ← 다른 관측소로 대체됨")
    print(f"  ────────────────────────")
    print(f"  합계                {len(regions):>4d}건")

    if multi:
        print(f"\n🔵 관측소 2개 이상인 시군구 ({len(multi)}건)")
        for rc, sido, sigungu, ss in multi:
            names = ", ".join(f"{x['name']}({x['id']})" for x in ss)
            print(f"  {rc}  {sido} {sigungu}  → {names}")

    print(f"\n🟢 관측소 정확히 1개인 시군구 ({len(one)}건)")
    by_sido = defaultdict(list)
    for rc, sido, sigungu, s in one:
        by_sido[sido].append((rc, sigungu, s))
    for sido in sorted(by_sido):
        print(f"  [{sido}] {len(by_sido[sido])}건")
        for rc, sigungu, s in by_sido[sido]:
            print(f"    {rc}  {sigungu:12s} → {s['name']}({s['id']})")

    print(f"\n🔴 관측소 없는 시군구 ({len(zero)}건) ← 시도 평균/근처 관측소 대체")
    by_sido = defaultdict(list)
    for rc, sido, sigungu in zero:
        by_sido[sido].append((rc, sigungu))
    for sido in sorted(by_sido):
        print(f"  [{sido}] {len(by_sido[sido])}건: "
              + ", ".join(f"{sg}({rc})" for rc, sg in by_sido[sido]))

    if unmapped_stations:
        print(f"\n⚠ 주소 매핑 실패한 관측소 ({len(unmapped_stations)}건)")
        for s in unmapped_stations:
            print(f"  {s['id']:>4s}  {s['name']:8s}  주소: {s['addr']}")

    if no_obs_stations:
        print(f"\n(참고) 메타엔 있지만 10년 데이터 없는 관측소: {len(no_obs_stations)}건")


if __name__ == "__main__":
    main()
