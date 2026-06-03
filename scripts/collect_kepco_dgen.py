"""
KEPCO 분산전원 연계정보 수집 CLI

사용 예:
  python scripts/collect_kepco_dgen.py --scope chungcheong
  python scripts/collect_kepco_dgen.py --scope all
  python scripts/collect_kepco_dgen.py --scope custom --regions 44270,44150,44180
  python scripts/collect_kepco_dgen.py --scope chungcheong --no-skip   # 기존 파일도 재요청

API 키:
  1) .env 파일에 KEPCO_API_KEY=... 또는
  2) 환경변수 KEPCO_API_KEY 또는
  3) --api-key 옵션으로 전달
"""
import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트 경로
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api import KepcoDgenClient  # noqa: E402

DB_PATH = ROOT / "db" / "solarfit.db"
SAVE_DIR = ROOT / "data" / "raw" / "kepco_dgen"
ENV_PATH = ROOT / "ini" / ".env"


def load_env_file(path: Path) -> None:
    """간단한 .env 로더 (python-dotenv 의존성 없이)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# scope 키워드 → sido 목록 매핑
# None = 전체 (필터 없음)
SCOPE_TO_SIDO: dict[str, list[str] | None] = {
    "all":         None,
    # 도(道) — 묶음 / 개별
    "chungcheong": ["충청북도", "충청남도"],           # 충청도 전체
    "chungbuk":    ["충청북도"],                      # 충북
    "chungnam":    ["충청남도"],                      # 충남
    "gyeongsang":  ["경상북도", "경상남도"],           # 경상도 전체
    "gyeongbuk":   ["경상북도"],                      # 경북
    "gyeongnam":   ["경상남도"],                      # 경남
    "jeolla":      ["전북특별자치도", "전라남도"],      # 전라도 전체
    "jeonbuk":     ["전북특별자치도"],                 # 전북
    "jeonnam":     ["전라남도"],                      # 전남
    "gyeonggi":    ["경기도"],                        # 경기
    "gangwon":     ["강원특별자치도"],                 # 강원
    "jeju":        ["제주특별자치도"],                 # 제주
    # 특별시·광역시
    "seoul":       ["서울특별시"],
    "busan":       ["부산광역시"],
    "daegu":       ["대구광역시"],
    "incheon":     ["인천광역시"],
    "gwangju":     ["광주광역시"],
    "daejeon":     ["대전광역시"],
    "ulsan":       ["울산광역시"],
    "sejong":      ["세종특별자치시"],
    # 사용자 지정
    "custom":      None,  # --regions 별도 처리
}


def load_regions(scope: str, custom: list[str] | None) -> list[str]:
    """SQLite region 테이블에서 대상 시군구 코드 가져오기."""
    if scope == "custom":
        if not custom:
            raise SystemExit("--scope custom 일 땐 --regions 가 필요합니다.")
        return custom

    if scope not in SCOPE_TO_SIDO:
        raise SystemExit(
            f"알 수 없는 scope: {scope}\n"
            f"사용 가능: {', '.join(SCOPE_TO_SIDO.keys())}"
        )

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    sido_list = SCOPE_TO_SIDO[scope]
    if sido_list is None:  # all
        cur.execute("SELECT region_code FROM region ORDER BY region_code")
    else:
        placeholders = ",".join("?" * len(sido_list))
        cur.execute(
            f"SELECT region_code FROM region WHERE sido IN ({placeholders}) "
            f"ORDER BY region_code",
            sido_list,
        )

    codes = [r[0] for r in cur.fetchall()]
    con.close()
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description="KEPCO 분산전원 연계정보 수집")
    parser.add_argument(
        "--scope",
        choices=list(SCOPE_TO_SIDO.keys()),
        default="chungcheong",
        help="수집 범위 (기본: chungcheong). 사용 가능: "
             + ", ".join(SCOPE_TO_SIDO.keys()),
    )
    parser.add_argument(
        "--regions",
        help="--scope custom 일 때 쉼표로 구분된 region_code 목록 (예: 44270,44150)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API 키 (없으면 .env 또는 환경변수 KEPCO_API_KEY 사용)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="이미 저장된 지역도 다시 호출",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.3,
        help="요청 간 최소 대기 시간(초) (기본 0.3)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="상세 로그"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    load_env_file(ENV_PATH)
    api_key = args.api_key or os.environ.get("KEPCO_API_KEY")
    if not api_key:
        raise SystemExit(
            "API 키 없음. .env에 KEPCO_API_KEY=... 추가하거나 --api-key 사용"
        )

    custom = args.regions.split(",") if args.regions else None
    regions = load_regions(args.scope, custom)
    print(f"대상 지역: {len(regions)}개 (scope={args.scope})")
    print(f"저장 경로: {SAVE_DIR}")

    client = KepcoDgenClient(api_key=api_key, rate_limit_sec=args.rate_limit)
    summary = client.collect_regions(
        regions, save_dir=SAVE_DIR, skip_existing=not args.no_skip
    )

    print()
    print(f"완료: 성공 {summary['ok']} / 건너뜀 {summary['skipped']} "
          f"/ 실패 {summary['failed']} / 총 {summary['total']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
