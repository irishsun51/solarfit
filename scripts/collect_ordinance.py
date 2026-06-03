"""
자치법규(조례) 수집 CLI

사용 예:
  python scripts/collect_ordinance.py --keywords 태양광,신재생에너지
  python scripts/collect_ordinance.py --keywords 태양광 --bodies         # 본문까지
  python scripts/collect_ordinance.py --keywords 태양광 --scope chungnam # 충남만

흐름:
  1) 키워드별 목록 검색 (조례명에서 부분 일치)
  2) 자치법규ID 기준 중복 제거
  3) 지자체기관명 → region_code 매핑
  4) (옵션) 본문 조회 → JSON 저장
  5) SQLite ordinance 테이블에 메타 적재
"""
import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api import LawGoKrClient  # noqa: E402

DB_PATH = ROOT / "db" / "solarfit.db"
RAW_DIR = ROOT / "data" / "raw" / "ordinance"
LIST_FILE = RAW_DIR / "_list.json"
ENV_PATH = ROOT / "ini" / ".env"

DEFAULT_KEYWORDS = [
    "태양광",
    "태양에너지",
    "신재생에너지",
    "분산에너지",
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ──────────────────────────────────────────
# 지자체기관명 → region_code
# ──────────────────────────────────────────
def build_region_lookups(con: sqlite3.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """(시군구명 → region_code), (시도명 → 광역코드(시도+'000')) 매핑."""
    sigungu_to_code: dict[str, str] = {}
    sido_to_code: dict[str, str] = {}
    cur = con.execute("SELECT region_code, sido, sigungu FROM region")
    for rc, sido, sigungu in cur.fetchall():
        sigungu_to_code[sigungu] = rc
        # 광역 코드 (예: 충청남도 → '44000')
        sido_code = rc[:2] + "000"
        sido_to_code.setdefault(sido, sido_code)
    return sigungu_to_code, sido_to_code


def map_institution(
    institution: str,
    sigungu_to_code: dict[str, str],
    sido_to_code: dict[str, str],
) -> tuple[str | None, str]:
    """지자체기관명 → (region_code, level)."""
    inst = (institution or "").strip()
    # 1) 시군구 정확 일치
    if inst in sigungu_to_code:
        return sigungu_to_code[inst], "시군구"
    # 2) 시도 정확 일치 (광역 조례)
    if inst in sido_to_code:
        return sido_to_code[inst], "광역"
    # 3) 부분 매칭 시도 (예: "당진시청" 같은 변형)
    for sg, rc in sigungu_to_code.items():
        if sg in inst:
            return rc, "시군구"
    for sd, rc in sido_to_code.items():
        if sd in inst:
            return rc, "광역"
    return None, "미매핑"


# ──────────────────────────────────────────
# 적재
# ──────────────────────────────────────────
def upsert_ordinance(
    con: sqlite3.Connection,
    item: dict,
    region_code: str | None,
    level: str,
    full_text_json: str | None = None,
) -> None:
    con.execute(
        """
        INSERT INTO ordinance
          (law_id, mst, law_name, institution, region_code, level,
           law_type, effective_date, full_text, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(law_id) DO UPDATE SET
          mst=excluded.mst,
          law_name=excluded.law_name,
          institution=excluded.institution,
          region_code=excluded.region_code,
          level=excluded.level,
          law_type=excluded.law_type,
          effective_date=excluded.effective_date,
          full_text=COALESCE(excluded.full_text, ordinance.full_text),
          fetched_at=excluded.fetched_at
        """,
        (
            item.get("자치법규ID"),
            item.get("자치법규일련번호"),
            item.get("자치법규명"),
            item.get("지자체기관명"),
            region_code,
            level,
            item.get("자치법규종류"),
            item.get("시행일자"),
            full_text_json,
            date.today().isoformat(),
        ),
    )


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="자치법규 수집")
    parser.add_argument(
        "--keywords",
        default=",".join(DEFAULT_KEYWORDS),
        help=f"쉼표 구분 검색어 (기본: {','.join(DEFAULT_KEYWORDS)})",
    )
    parser.add_argument(
        "--scope",
        choices=["all", "chungnam", "chungcheong"],
        default="all",
        help="region_code 매핑 후 적재 필터 (기본 all)",
    )
    parser.add_argument(
        "--bodies",
        action="store_true",
        help="본문까지 받아서 저장 (기본: 메타만)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OC 키 (없으면 .env의 LAW_API_KEY)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.3,
        help="요청 간 대기 (기본 0.3초)",
    )
    parser.add_argument(
        "--max-bodies",
        type=int,
        default=0,
        help="본문 최대 N건만 (0=제한 없음, 테스트용)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    load_env_file(ENV_PATH)
    api_key = args.api_key or os.environ.get("LAW_API_KEY")
    if not api_key:
        raise SystemExit("LAW_API_KEY 필요. .env에 추가하거나 --api-key 사용")

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = LawGoKrClient(api_key=api_key, rate_limit_sec=args.rate_limit)

    # 1) 검색
    print(f"검색 키워드: {keywords}")
    merged = client.search_multi(keywords)
    print(f"  └ 중복 제거 후 {len(merged)}건")

    # 목록 백업 저장
    LIST_FILE.write_text(
        json.dumps(list(merged.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  └ 목록 저장: {LIST_FILE}")

    # 2) region 매핑
    con = sqlite3.connect(DB_PATH)
    sigungu_to_code, sido_to_code = build_region_lookups(con)

    stats = {"광역": 0, "시군구": 0, "미매핑": 0}
    mapped = []
    for it in merged.values():
        rc, level = map_institution(it.get("지자체기관명", ""), sigungu_to_code, sido_to_code)
        stats[level] += 1
        if rc is not None:
            mapped.append((it, rc, level))

    print(f"매핑 결과: 광역 {stats['광역']} / 시군구 {stats['시군구']} / 미매핑 {stats['미매핑']}")

    # 3) scope 필터
    if args.scope == "chungnam":
        mapped = [(it, rc, lv) for it, rc, lv in mapped if rc.startswith("44")]
    elif args.scope == "chungcheong":
        mapped = [(it, rc, lv) for it, rc, lv in mapped if rc.startswith(("43", "44"))]
    print(f"scope={args.scope} 필터 후: {len(mapped)}건")

    # 4) DB 메타 적재 (본문 없이 먼저)
    for it, rc, lv in mapped:
        upsert_ordinance(con, it, rc, lv)
    con.commit()
    print(f"메타 적재 완료")

    # 5) 본문 (옵션)
    if args.bodies:
        bodies_target = mapped
        if args.max_bodies > 0:
            bodies_target = bodies_target[: args.max_bodies]
        print(f"본문 조회 시작: {len(bodies_target)}건")

        ok, fail = 0, 0
        for i, (it, rc, lv) in enumerate(bodies_target, 1):
            mst = it.get("자치법규일련번호")
            if not mst:
                continue
            out_path = RAW_DIR / f"{it['자치법규ID']}.json"
            if out_path.exists():
                logging.info(f"[{i}/{len(bodies_target)}] {mst} skipped")
                continue
            try:
                body = client.get_body(mst)
                out_path.write_text(
                    json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                # DB의 full_text도 갱신
                con.execute(
                    "UPDATE ordinance SET full_text=? WHERE law_id=?",
                    (json.dumps(body, ensure_ascii=False), it["자치법규ID"]),
                )
                ok += 1
                logging.info(f"[{i}/{len(bodies_target)}] {mst} ok")
            except Exception as e:
                fail += 1
                logging.error(f"[{i}/{len(bodies_target)}] {mst} fail: {e}")

        con.commit()
        print(f"본문 결과: 성공 {ok} / 실패 {fail} / 건너뜀 {len(bodies_target) - ok - fail}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
