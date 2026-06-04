"""
국가법령정보 공동활용 — 자치법규(조례) API 클라이언트
https://open.law.go.kr

엔드포인트:
  목록: https://www.law.go.kr/DRF/lawSearch.do
  본문: https://www.law.go.kr/DRF/lawService.do

요청 파라미터 (자치법규):
  OC      인증키 (OPEN_LAW_API)
  target  'ordin' (자치법규)
  query   검색어 (조례명 부분 일치)
  type    JSON / XML / HTML
  display 한 페이지 결과 수 (기본 20)
  page    페이지 번호
  MST     자치법규일련번호 (본문 조회용)

응답 (검색):
  OrdinSearch.law = [
    {
      자치법규ID, 자치법규명, 자치법규일련번호, 지자체기관명,
      자치법규종류 (조례/고시/규칙),
      시행일자, 공포일자, 자치법규상세링크
    }, ...
  ]
"""
from __future__ import annotations

from typing import Iterable

from .client import APIClient


class LawGoKrClient(APIClient):
    """자치법규 검색/본문 조회."""

    base_url = "https://www.law.go.kr/DRF/lawSearch.do"
    body_url = "https://www.law.go.kr/DRF/lawService.do"
    api_key_param = "OC"
    return_type_param = "type"
    default_return_type = "JSON"
    log_label = "law_go_kr"

    # ──────────────────────────────────────────
    # 검색 (목록)
    # ──────────────────────────────────────────
    def search(
        self,
        query: str,
        display: int = 100,
        page: int = 1,
        search_mode: int = 2,
    ) -> dict:
        """자치법규 검색.

        search_mode:
          1 = 조례명에서만 검색 (elis '법규명' 탭)
          2 = 본문(body)에서 검색 (elis '법규본문' 탭) ← 기본
        """
        return self.request({
            "target": "ordin",
            "query": query,
            "display": display,
            "page": page,
            "search": search_mode,
        })

    def search_all_pages(
        self, query: str, display: int = 100, max_pages: int = 20, search_mode: int = 2
    ) -> list[dict]:
        """검색 결과 페이지 끝까지. 모든 law 항목 합쳐서 리스트로 반환."""
        all_items = []
        for page in range(1, max_pages + 1):
            data = self.search(query, display=display, page=page, search_mode=search_mode)
            wrap = data.get("OrdinSearch", {})
            items = wrap.get("law", [])
            if isinstance(items, dict):  # 결과 1건이면 list 아닌 dict로 옴
                items = [items]
            all_items.extend(items)

            try:
                total = int(wrap.get("totalCnt", "0"))
            except (ValueError, TypeError):
                total = 0
            if page * display >= total:
                break
        return all_items

    # ──────────────────────────────────────────
    # 본문 조회
    # ──────────────────────────────────────────
    def get_body(self, mst: str) -> dict:
        """자치법규 본문 조회. base_url을 잠시 lawService.do로 바꿔 호출."""
        original = self.base_url
        self.base_url = self.body_url
        try:
            return self.request({
                "target": "ordin",
                "MST": mst,
            })
        finally:
            self.base_url = original

    # ──────────────────────────────────────────
    # 다중 키워드 통합 검색
    # ──────────────────────────────────────────
    def search_multi(self, keywords: Iterable[str]) -> dict[str, dict]:
        """여러 키워드로 검색해 자치법규ID 기준 dedupe."""
        merged: dict[str, dict] = {}
        for kw in keywords:
            items = self.search_all_pages(kw)
            for it in items:
                law_id = it.get("자치법규ID")
                if law_id and law_id not in merged:
                    merged[law_id] = it
        return merged
