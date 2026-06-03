"""
한국전력공사 — 분산전원 연계정보 API
https://bigdata.kepco.co.kr/cmsmain.do?scode=S01&pcode=000493&pstate=dgen

요청 파라미터:
  metroCd     시도코드 (2자리) — 예: 44 (충남)
  cityCd      시군구코드 (3자리) — 예: 270 (당진시)
  addrLidong  동/면 (선택)
  addrLi      리 (선택)
  addrJibun   상세번지 (선택)
  substCd     변전소코드 (선택)
  apiKey      40자리 인증키 (필수)
  returnType  json | xml (선택, 기본 json)

응답:
  data: 변전소·변압기·DL별 누적연계용량 + 여유용량(vol1/vol2/vol3) 리스트
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .client import APIClient


class KepcoDgenClient(APIClient):
    """KEPCO 분산전원 연계정보."""

    base_url = "https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do"
    api_key_param = "apiKey"
    return_type_param = "returnType"
    default_return_type = "json"

    def fetch_by_region(self, region_code: str) -> dict:
        """시군구 코드(5자리)로 조회. 우리 region_code 그대로 사용 가능."""
        if len(region_code) != 5 or not region_code.isdigit():
            raise ValueError(f"region_code는 5자리 숫자 문자열이어야 함: {region_code}")

        params = {
            "metroCd": region_code[:2],
            "cityCd": region_code[2:5],
        }
        return self.request(params)

    def fetch_by_address(
        self,
        metro_cd: str,
        city_cd: Optional[str] = None,
        addr_lidong: Optional[str] = None,
        addr_li: Optional[str] = None,
        addr_jibun: Optional[str] = None,
        subst_cd: Optional[str] = None,
    ) -> dict:
        """주소 컴포넌트 직접 지정."""
        params = {"metroCd": metro_cd}
        for k, v in (
            ("cityCd", city_cd),
            ("addrLidong", addr_lidong),
            ("addrLi", addr_li),
            ("addrJibun", addr_jibun),
            ("substCd", subst_cd),
        ):
            if v:
                params[k] = v
        return self.request(params)

    def collect_regions(
        self, region_codes: list[str], save_dir: Path, skip_existing: bool = True
    ) -> dict:
        """region_code 리스트를 순회하며 개별 JSON 저장."""
        param_list = [
            {
                "region_code": rc,  # key_field (파일명용, 호출엔 안 들어감)
                "metroCd": rc[:2],
                "cityCd": rc[2:5],
            }
            for rc in region_codes
        ]
        return self.fetch_many(
            param_list,
            save_dir=save_dir,
            key_field="region_code",
            skip_existing=skip_existing,
        )
