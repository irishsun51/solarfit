"""
국토교통부 토지이용계획정보서비스 (NSDI) API 클라이언트
공공데이터포털 데이터셋 15056930 / 국가공간정보 1611000

목적:
  지번 주소 → PNU(필지고유번호 19자리) → 토지이용계획 조회
  → 용도지역·지구 목록(배열) + 농업진흥구역(농지규제) 여부

  ⇒ site_diagnosis.py 입지 진단 탭의 '용도지역' · '농지 규제' 카드 2개를 한 번에 채움.

PNU 구성(19자리):
  법정동코드(10) + 산여부(1: 토지=1, 산=2) + 본번(4, zero-pad) + 부번(4, zero-pad)
  예) 충남 논산시 부적면 충곡리 123-4
     = 4423035026 + 1 + 0123 + 0004 = 4423035026101230004

⚠ 사용 전 확인할 것 (DATA_GO_KR_KEY 발급 후 1회):
  - BASE_URL / 오퍼레이션명이 실제 신청한 서비스와 일치하는지
  - 응답 필드명(prposAreaDstrcCodeNm 등)이 실응답과 일치하는지
  엔드포인트가 다르면 LandUseClient(api_key, base_url=...) 로 교체 가능.
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .client import APIClient

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"  # legal_dong_code 테이블 (scripts/init_db.py 적재)

# 입력 지번의 시도 약칭 → 법정동코드 파일의 정식 명칭
# (정식 명칭은 파일 기준. 매칭 실패 시 약칭 변환 없이 원문으로도 한 번 더 시도)
SIDO_ALIAS = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
    "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
    "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도",
    "충남": "충청남도", "전북": "전북특별자치도", "전남": "전라남도",
    "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도",
}

# 농지규제 판정용 키워드 (용도지역·지구명에 포함되면 농지규제 대상)
_FARMLAND_KEYWORDS = ("농업진흥", "농업보호", "농림지역")


# ════════════════════════════════════════════════════════
# 지번 주소 → PNU 변환
# ════════════════════════════════════════════════════════
@lru_cache(maxsize=4096)
def _lookup_legal_dong(name: str) -> str | None:
    """법정동 정식명 → 10자리 코드. DB(legal_dong_code) 단건 조회 + 결과 캐시.
    (파일 전체를 메모리에 올리지 않음 — 호출된 이름만 캐시)"""
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute(
            "SELECT code FROM legal_dong_code WHERE name = ?", (name,)
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def addr_to_pnu(addr: str) -> str:
    """지번 주소 → PNU 19자리.

    Args:
        addr: 예) "충남 논산시 부적면 충곡리 123-4" / "충남 ... 산45"
    Returns:
        PNU 19자리 문자열
    Raises:
        ValueError: 번지 파싱 실패 또는 법정동코드 미발견
    """
    addr = addr.strip()

    # 1) 끝의 번지 분리: (산)123-4 / 123 / 산45
    m = re.search(r"(산)?\s*(\d+)(?:-(\d+))?\s*$", addr)
    if not m:
        raise ValueError(f"번지를 찾을 수 없습니다: '{addr}'")
    is_mountain = 2 if m.group(1) else 1
    bonbun = int(m.group(2))
    bubun = int(m.group(3) or 0)
    dong_name = addr[: m.start()].strip()

    # 2) 법정동코드 조회 (정식명 우선, 시도약칭 변환 후 재시도)
    code = _lookup_legal_dong(dong_name)
    if not code:
        parts = dong_name.split()
        if parts and parts[0] in SIDO_ALIAS:
            parts[0] = SIDO_ALIAS[parts[0]]
            code = _lookup_legal_dong(" ".join(parts))
    if not code:
        raise ValueError(f"법정동코드를 찾을 수 없습니다: '{dong_name}'")

    return f"{code}{is_mountain}{bonbun:04d}{bubun:04d}"


# ════════════════════════════════════════════════════════
# 토지이용계획 API 클라이언트
# ════════════════════════════════════════════════════════
class LandUseClient(APIClient):
    """PNU → 토지이용계획(용도지역·지구 배열) 조회. (VWorld 국가중점데이터)

    VWorld 엔드포인트 특성:
      - domain 파라미터 필수 (발급 시 등록한 서비스URL)
      - pnu는 19자리(필지)로 직접 조회 — 한 필지에 지역지구 여러 개가 배열로 옴
      - 실존하지 않는 지번(더미)은 0건 반환
    """

    base_url = (
        "https://api.vworld.kr/ned/data/getLandUseAttr"
    )
    api_key_param = "key"
    return_type_param = "format"
    default_return_type = "json"
    log_label = "vworld_landuse"

    def __init__(self, api_key: str, domain: str = "http://localhost:9001", **kw):
        super().__init__(api_key, **kw)
        self.domain = domain

    def get_raw(self, pnu19: str, rows: int = 100) -> dict:
        """19자리 PNU로 토지이용계획 직접 조회. 한 필지에 여러 지역지구 → 배열.
        (더미 지번은 실존하지 않아 0건이 올 수 있음)"""
        return self.request({
            "pnu": pnu19, "numOfRows": rows, "pageNo": 1,
            "domain": self.domain,
        })

    # ── 응답 파싱 ──────────────────────────────────────
    @staticmethod
    def _extract_fields(raw: dict) -> list[dict]:
        """NSDI 응답 구조에서 지역지구 레코드 배열을 방어적으로 추출.
        (실응답 구조 확정 전이라 알려진 경로들을 차례로 시도)"""
        if not isinstance(raw, dict):
            return []
        # 자주 쓰는 NSDI 래퍼들
        for key in ("landUses", "landUseAttr", "response"):
            node = raw.get(key)
            if isinstance(node, dict):
                # response > body > items > item 표준 공공데이터 구조
                body = node.get("body", node)
                items = (
                    body.get("items", body).get("item")
                    if isinstance(body.get("items", body), dict)
                    else body.get("field") or body.get("item")
                )
                if items:
                    return items if isinstance(items, list) else [items]
                fld = node.get("field")
                if fld:
                    return fld if isinstance(fld, list) else [fld]
        # 최상위에 field가 바로 있는 경우
        fld = raw.get("field")
        if fld:
            return fld if isinstance(fld, list) else [fld]
        return []

    @classmethod
    def parse(cls, raw: dict) -> dict:
        """원시 응답 → 화면 연결용 정리 dict.

        Returns:
            {
              "zones":     ["계획관리지역", "농업진흥구역", ...],  # 전체 지역지구
              "zone_main": "계획관리지역" | None,                  # 대표 용도지역
              "farmland":  True/False,                            # 농지규제 대상 여부
              "raw_count": N,
            }
        """
        fields = cls._extract_fields(raw)
        zones: list[str] = []
        for f in fields:
            if not isinstance(f, dict):
                continue
            name = (
                f.get("prposAreaDstrcCodeNm")
                or f.get("prposAreaDstrcCdNm")
                or f.get("ldCodeNm")
                or ""
            ).strip()
            if name and name not in zones:
                zones.append(name)

        farmland = any(k in z for z in zones for k in _FARMLAND_KEYWORDS)
        # 대표 용도지역: 국토계획법 용도지역(…지역) 중 첫 번째
        zone_main = next((z for z in zones if z.endswith("지역")), zones[0] if zones else None)

        return {
            "zones": zones,
            "zone_main": zone_main,
            "farmland": farmland,
            "raw_count": len(fields),
        }
