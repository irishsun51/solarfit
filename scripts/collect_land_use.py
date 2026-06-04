"""
시연 지번 → 토지이용계획 조회 → data/land_use/{pnu}.json 캐시.

토지이용계획은 사용자가 칠 지번을 예측할 수 없어 전체 적재가 불가능하다.
→ 입력 즉시 실시간 API 호출이 원칙이되, 데모 안정성을 위해
  시연용 지번 몇 개는 미리 호출해 캐시해 둔다. (PROGRESS 의사결정 #8)

사용:
  # 키 없이 PNU 변환만 미리 확인
  python scripts/collect_land_use.py --dry-run

  # 실제 호출·캐시 (DATA_GO_KR_KEY 필요)
  python scripts/collect_land_use.py
  python scripts/collect_land_use.py --addr "충남 당진시 우강면 송산리 45"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.land_use import LandUseClient, addr_to_pnu  # noqa: E402

ENV_PATH = ROOT / "ini" / ".env"
SAVE_DIR = ROOT / "data" / "land_use"

# 시연용 지번 (더미 화면과 동일 — 우선 이걸로 테스트)
DEMO_ADDRS = [
    "충남 논산시 부적면 충곡리 200",
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


def collect_one(client: LandUseClient | None, addr: str, dry_run: bool) -> None:
    """지번 1건: PNU 변환 → (dry_run이면 출력만 / 아니면 호출·파싱·저장)."""
    try:
        pnu = addr_to_pnu(addr)
    except ValueError as e:
        print(f"  [ERR] PNU 변환 실패: {e}")
        return

    if dry_run or client is None:
        print(f"  · {addr}\n      → PNU {pnu}")
        return

    raw = client.get_raw(pnu)
    parsed = LandUseClient.parse(raw)
    out = {"addr": addr, "pnu": pnu, "parsed": parsed, "raw": raw}

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SAVE_DIR / f"{pnu}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    zones = ", ".join(parsed["zones"]) or "(없음)"
    farm = "농지규제 O" if parsed["farmland"] else "농지규제 X"
    print(f"  [OK] {addr}\n      PNU {pnu} | 용도지역: {zones} | {farm}\n      저장: {out_path.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="시연 지번 토지이용계획 캐시")
    ap.add_argument("--addr", action="append", help="조회할 지번(여러 번 가능). 없으면 DEMO_ADDRS")
    ap.add_argument("--api-key", help="공공데이터포털 키 (없으면 .env의 DATA_GO_KR_KEY)")
    ap.add_argument("--rate-limit", type=float, default=0.3, help="호출 간 대기(초)")
    ap.add_argument("--dry-run", action="store_true", help="키 없이 PNU 변환만 출력")
    args = ap.parse_args()

    load_env_file(ENV_PATH)
    addrs = args.addr or DEMO_ADDRS

    client = None
    if not args.dry_run:
        api_key = args.api_key or os.environ.get("VWORLD_API_KEY")
        if not api_key:
            raise SystemExit(
                "VWORLD_API_KEY 없음. VWorld(api.vworld.kr)에서 인증키 발급 후\n"
                "ini/.env 의 VWORLD_API_KEY 에 넣으세요. "
                "(우선 PNU만 보려면 --dry-run)"
            )
        client = LandUseClient(api_key=api_key, domain="http://localhost:9001", rate_limit_sec=args.rate_limit)

    mode = "DRY-RUN (PNU 변환만)" if args.dry_run else "실호출·캐시"
    print(f"[{mode}] 대상 {len(addrs)}건\n")
    for addr in addrs:
        collect_one(client, addr, args.dry_run)


if __name__ == "__main__":
    main()
