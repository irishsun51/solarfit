"""
공통 API 클라이언트
- 새 외부 API 추가 시: 이 클래스를 상속해서 BASE_URL + 파라미터 매핑만 정의하면 됨
- 기능: GET/POST, 자동 재시도, rate limit(요청 간 sleep), JSON/XML 응답 파싱, 원본 저장
"""
from __future__ import annotations

import datetime
import json
import logging
import time
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

log = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "log"


class APIClient:
    """모든 외부 API의 베이스 클래스.

    Attributes:
        base_url: API 엔드포인트
        api_key: 인증키
        api_key_param: 쿼리스트링에서 API 키 파라미터명 (예: 'apiKey', 'serviceKey')
        timeout: 요청 타임아웃(초)
        rate_limit_sec: 연속 호출 사이 최소 대기 시간(초)
        max_retries: 5xx/타임아웃 시 재시도 횟수
        return_type_param: 응답 포맷 지정 파라미터명 (선택)
        default_return_type: 'json' 또는 'xml'
    """

    base_url: str = ""
    api_key_param: str = "apiKey"
    return_type_param: Optional[str] = "returnType"
    default_return_type: str = "json"
    log_label: str = "api"        # 로그 파일명 식별자 (하위 클래스에서 오버라이드)
    log_body_limit: int = 4000    # 응답 본문 최대 기록 길이(0이면 무제한)

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 30,
        rate_limit_sec: float = 0.3,
        max_retries: int = 3,
    ):
        if base_url:
            self.base_url = base_url
        if not self.base_url:
            raise ValueError("base_url이 필요합니다.")
        if not api_key:
            raise ValueError("api_key가 필요합니다.")

        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit_sec = rate_limit_sec
        self.max_retries = max_retries
        self._last_request_ts = 0.0
        self.session = requests.Session()

    # ──────────────────────────────────────────
    # 핵심 요청
    # ──────────────────────────────────────────
    def request(self, params: Optional[dict] = None, method: str = "GET") -> dict:
        """단일 호출. JSON dict 반환 (XML이면 텍스트로 dict에 감쌈)."""
        params = dict(params or {})
        params[self.api_key_param] = self.api_key
        if self.return_type_param and self.return_type_param not in params:
            params[self.return_type_param] = self.default_return_type

        self._respect_rate_limit()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(
                    method, self.base_url, params=params, timeout=self.timeout
                )
                self._last_request_ts = time.time()

                if resp.status_code >= 500:
                    raise requests.HTTPError(
                        f"서버 오류 {resp.status_code}", response=resp
                    )
                resp.raise_for_status()

                self._write_log(method, params, resp.status_code, resp.text)

                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype or resp.text.lstrip().startswith("{"):
                    return resp.json()
                return {"_raw_xml": resp.text}

            except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
                if attempt == self.max_retries:
                    log.error(f"요청 실패 (최종): {e} params={params}")
                    raise
                wait = 2**attempt
                log.warning(f"요청 실패 ({attempt}/{self.max_retries}): {e} → {wait}s 후 재시도")
                time.sleep(wait)

        raise RuntimeError("재시도 로직 오류")

    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.rate_limit_sec:
            time.sleep(self.rate_limit_sec - elapsed)

    def _write_log(self, method: str, params: dict, status: int, body: str) -> None:
        """API 요청/응답을 log/API_<label>_<YYYYMMDD>.log 에 보기 좋게 append.
        - API 키는 '***'로 마스킹
        - JSON 응답은 들여쓰기(pretty)
        - 본문은 log_body_limit 초과 시 잘림(0이면 무제한)
        - 로깅 실패는 본 호출에 영향 주지 않음
        """
        try:
            now = datetime.datetime.now()
            path = LOG_DIR / f"API_{self.log_label}_{now:%Y%m%d}.log"
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            masked = {
                k: ("***" if k == self.api_key_param else v)
                for k, v in params.items()
            }
            param_lines = "\n".join(f"    {k:<11}: {v}" for k, v in masked.items())

            # 응답 본문: JSON이면 pretty, 아니면 원문
            pretty = body
            try:
                pretty = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
            except (ValueError, TypeError):
                pass
            if self.log_body_limit and len(pretty) > self.log_body_limit:
                omitted = len(pretty) - self.log_body_limit
                pretty = pretty[: self.log_body_limit] + f"\n    ... (+{omitted}자 생략)"

            with open(path, "a", encoding="utf-8") as f:
                f.write("=" * 78 + "\n")
                f.write(f"[{now:%Y-%m-%d %H:%M:%S}]  REQUEST\n")
                f.write(f"  {method} {self.base_url}\n")
                f.write(f"  params:\n{param_lines}\n")
                f.write("-" * 78 + "\n")
                f.write(f"  RESPONSE  (status {status}, {len(body):,} bytes)\n")
                f.write(pretty + "\n")
                f.write("=" * 78 + "\n\n")
        except Exception as e:  # noqa: BLE001 — 로깅 실패가 호출을 막지 않게
            log.debug(f"_write_log 실패: {e}")

    # ──────────────────────────────────────────
    # 배치: 여러 파라미터 조합을 순회하며 저장
    # ──────────────────────────────────────────
    def fetch_many(
        self,
        param_list: Iterable[dict],
        save_dir: Path,
        key_field: str,
        skip_existing: bool = True,
    ) -> dict[str, Any]:
        """여러 파라미터 조합 호출 → {key}.json 으로 개별 저장.

        Args:
            param_list: 호출별 파라미터 dict 리스트
            save_dir: 저장 폴더
            key_field: 파일명에 쓸 파라미터 키 (예: 'region_code')
                       호출 자체엔 들어가지 않으므로 params에서 제거됨.
            skip_existing: 이미 파일 있으면 건너뛰기 (--resume 기본)

        Returns:
            요약 dict: {ok, skipped, failed, total}
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        summary = {"ok": 0, "skipped": 0, "failed": 0, "total": 0}
        param_list = list(param_list)
        summary["total"] = len(param_list)

        for i, params in enumerate(param_list, 1):
            params = dict(params)
            key = str(params.pop(key_field))
            out_path = save_dir / f"{key}.json"

            if skip_existing and out_path.exists():
                summary["skipped"] += 1
                log.info(f"[{i}/{summary['total']}] {key} skipped (already exists)")
                continue

            try:
                data = self.request(params)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                summary["ok"] += 1
                log.info(f"[{i}/{summary['total']}] {key} ok")
            except Exception as e:
                summary["failed"] += 1
                log.error(f"[{i}/{summary['total']}] {key} failed: {e}")

        return summary
