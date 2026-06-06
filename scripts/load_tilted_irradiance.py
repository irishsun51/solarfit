"""전국 경사면 일사량(5yr KMAPP) CSV → irradiance 테이블 적재.

- CSV: solar_sigungu_all_5yr_summary.csv (시군구별 연 일사량 MJ/m², 경사면)
- 매핑: 옛 2자리 시도코드 → 신 시도명, 일반구(시 구) → parent 시 grid_count 가중병합, 세종 특수
- 저장: 기존 매칭 region 행 DELETE → 연단위 1행(month=0, irradiance=연 MJ) INSERT
        (get_sunshine_hours 등이 SUM(irradiance)×0.85/3.6 로 쓰므로 '연 MJ'를 그대로 저장)
- 기본은 DRY-RUN. 실제 반영은 --commit (이때 irradiance_backup 자동 생성)

사용:
    python scripts/load_tilted_irradiance.py            # 매칭 리포트만
    python scripts/load_tilted_irradiance.py --commit   # 백업 + 적재
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
DEFAULT_CSV = Path(
    r"C:\Projects\solarSpot_backup_20260603\Data\raw\solar\solar_sigungu_all_5yr_summary.csv"
)

# 옛 2자리 시도코드 → region 테이블의 신 시도명
SIDO = {
    "11": "서울특별시", "21": "부산광역시", "22": "대구광역시", "23": "인천광역시",
    "24": "광주광역시", "25": "대전광역시", "26": "울산광역시", "29": "세종특별자치시",
    "31": "경기도", "32": "강원특별자치도", "33": "충청북도", "34": "충청남도",
    "35": "전북특별자치도", "36": "전라남도", "37": "경상북도", "38": "경상남도",
    "39": "제주특별자치도",
}


def build_mapping(csv_path: Path, reg: list[tuple]):
    reg_by = {(sido, sig): code for code, sido, sig in reg}
    name_counts = Counter(sig for _, _, sig in reg)
    name_to_code = {sig: code for code, _, sig in reg}
    sejong = [code for code, sido, _ in reg if sido == "세종특별자치시"]
    sejong_code = sejong[0] if sejong else None

    agg: dict[str, list[tuple[float, float]]] = defaultdict(list)
    unmatched_csv = []

    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sido = SIDO.get(r["sido_code"])
            name = r["sigungu"].strip()
            mj = float(r["annual_irradiance_mj_m2_avg"])
            w = float(r["grid_count"] or 0)
            code = None
            if sido == "세종특별자치시":
                code = sejong_code
            else:
                parent = name.split(" ")[0] if " " in name else name  # 일반구 → parent 시
                code = reg_by.get((sido, parent)) or reg_by.get((sido, name))
                # 이름이 region에서 유일하면 시도 불일치(예: 군위군 대구↔경북)도 흡수
                if not code and " " not in name and name_counts.get(name, 0) == 1:
                    code = name_to_code.get(name)
            if not code:
                unmatched_csv.append(f"{sido}/{name}")
                continue
            agg[code].append((mj, w))

    result = {}
    for code, lst in agg.items():
        tw = sum(w for _, w in lst)
        result[code] = round(sum(v * w for v, w in lst) / tw, 2) if tw else round(
            sum(v for v, _ in lst) / len(lst), 2
        )
    return result, unmatched_csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--commit", action="store_true", help="실제 DB 반영(+백업)")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    reg = con.execute("SELECT region_code, sido, sigungu FROM region").fetchall()
    result, unmatched_csv = build_mapping(Path(args.csv), reg)

    all_codes = {code for code, _, _ in reg}
    matched = set(result)
    unmatched_region = sorted(all_codes - matched)
    name = {code: f"{sido} {sig}" for code, sido, sig in reg}

    print(f"region 총 {len(all_codes)}  /  CSV 매칭 region {len(matched)}")
    print(f"미매칭 region {len(unmatched_region)}: "
          + ", ".join(f"{c}({name[c]})" for c in unmatched_region[:20]))
    print(f"CSV 미매칭 {len(unmatched_csv)}: " + ", ".join(unmatched_csv[:20]))
    # 샘플 (발전시간 환산 = MJ/3.6*0.85)
    print("\n샘플 (region_code  연MJ  →  발전시간h):")
    for c in ["44130", "44230", "11680", "26440", "41111"]:
        if c in result:
            print(f"  {c} {name.get(c,''):14} {result[c]:8.1f}  →  {round(result[c]/3.6*0.85)}h")

    if not args.commit:
        print("\n[DRY-RUN] DB 미반영. 실제 적재는 --commit")
        con.close()
        return

    con.execute("DROP TABLE IF EXISTS irradiance_backup")
    con.execute("CREATE TABLE irradiance_backup AS SELECT * FROM irradiance")
    bk = con.execute("SELECT COUNT(*) FROM irradiance_backup").fetchone()[0]
    for code, mj in result.items():
        con.execute("DELETE FROM irradiance WHERE region_code=?", (code,))
        con.execute(
            "INSERT INTO irradiance (region_code, month, irradiance) VALUES (?, 0, ?)",
            (code, mj),
        )
    con.commit()
    cnt = con.execute("SELECT COUNT(*) FROM irradiance").fetchone()[0]
    con.close()
    print(f"\n[COMMIT] irradiance_backup 생성({bk}행). irradiance 적재 완료 → 현재 {cnt}행")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
