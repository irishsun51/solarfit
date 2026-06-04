"""
SMP(육지)·REC 2025 월별 → smp_rec 테이블 적재.

- SMP: data/SMP_REC/HOME_..._SMP.csv 의 '육지' 컬럼 (2025 월별)
- REC: data/SMP_REC/REC자료.jpg 에서 수기 입력 (이미지라 자동 추출 불가)
       3-3 REC 현물시장 평균 거래가격, 2025년 통합, 단위 원/REC
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
SMP_CSV = ROOT / "data" / "SMP_REC" / "HOME_전력거래_계통한계가격_가중평균SMP.csv"

# REC 2025 월별 (REC자료.jpg · 통합 · 원/REC)
REC_2025 = {
    1: 69760, 2: 72160, 3: 72145, 4: 72405, 5: 72385, 6: 71958,
    7: 71649, 8: 71859, 9: 71972, 10: 72312, 11: 72144, 12: 72294,
}


def main() -> int:
    # SMP 2025 월별 육지 (CSV 컬럼: 기간, 육지, 제주, 통합, BLMP)
    smp = {}
    for r in csv.reader(open(SMP_CSV, encoding="cp949")):
        if r and r[0].startswith("2025/"):
            smp[int(r[0].split("/")[1])] = float(r[1])

    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM smp_rec")
    for m in range(1, 13):
        con.execute(
            "INSERT INTO smp_rec(date, smp, rec) VALUES(?,?,?)",
            (f"2025-{m:02d}-01", smp[m], REC_2025[m]),
        )
    con.commit()
    n, asmp, arec = con.execute(
        "SELECT COUNT(*), ROUND(AVG(smp),2), ROUND(AVG(rec)) FROM smp_rec"
    ).fetchone()
    print(f"적재 {n}행 / 2025 연평균: SMP {asmp} 원/kWh · REC {arec:,.0f} 원/REC")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
