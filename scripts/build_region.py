"""
법정동코드 원본 → 시군구 region 테이블 정규화
원본은 읽기만, 결과는 data/processed/region.csv에 저장.

필터 규칙:
  - status == "존재"
  - 코드 끝 5자리 == "00000"  (시도 또는 시군구 레벨)
  - 시도 단독 행 (끝 8자리 == "00000000") 제외, 단 세종 예외
  - 일반구(sigungu에 공백 포함, 예: "천안시 동남구") 제외
    → KEPCO 등 외부 API가 parent 시 코드로 호출 시 일반구 데이터까지
      반환하므로 일반구를 region 키로 두면 중복 집계 발생
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "행정코드" / "법정동코드 전체자료" / "법정동코드 전체자료.txt"
OUTPUT = ROOT / "data" / "processed" / "region.csv"

SEJONG = "3611000000"


def main():
    rows = []
    with open(INPUT, encoding="cp949") as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < 3:
                continue
            code, name, status = parts[0].strip(), parts[1].strip(), parts[2].strip()

            if status != "존재":
                continue
            if not code.endswith("00000"):
                continue
            if code.endswith("00000000") and code != SEJONG:
                continue

            if code == SEJONG:
                sido, sigungu = "세종특별자치시", "세종특별자치시"
            else:
                np = name.split()
                sido = np[0]
                sigungu = " ".join(np[1:]) if len(np) > 1 else ""

            # 일반구 제외 (예: "천안시 동남구") — parent 시 키로 통합
            if " " in sigungu:
                continue

            rows.append((code[:5], sido, sigungu))

    rows = sorted(set(rows))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region_code", "sido", "sigungu"])
        w.writerows(rows)

    print(f"저장 완료: {OUTPUT}")
    print(f"총 {len(rows)}건\n")
    print("시도별 분포:")
    for sido, cnt in sorted(Counter(r[1] for r in rows).items(), key=lambda x: -x[1]):
        print(f"  {sido:10s}  {cnt:3d}건")


if __name__ == "__main__":
    main()
