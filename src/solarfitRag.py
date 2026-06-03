"""
조례 RAG 모듈
- ChromaDB 벡터 검색 + 메타데이터(region_code) 필터
- OpenAI gpt-4o-mini 답변 생성 (스트리밍 지원)

사용:
    from src.solarfitRag import OrdinanceRAG
    rag = OrdinanceRAG()
    chunks = rag.search("농지 영농형 가능?", region_code="44270")
    answer = rag.answer("농지 영농형 가능?", region_code="44270")
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import chromadb
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "db" / "chroma_db"
ENV_PATH = ROOT / "ini" / ".env"
LOG_DIR = ROOT / "log"
COLLECTION_NAME = "ordinance"
EMBED_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"


def _load_env_once():
    """env가 안 로드돼 있으면 .env에서 로드."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Chunk:
    text: str
    region_code: str
    institution: str
    law_name: str
    article_num: str
    article_title: str
    distance: float


class OrdinanceRAG:
    def __init__(self):
        _load_env_once()
        self._chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._collection = self._chroma.get_collection(COLLECTION_NAME)
        self._openai = OpenAI()

    def _refresh_collection(self) -> None:
        """벡터 DB가 재적재되어 UUID가 바뀌었을 때 다시 잡기."""
        self._chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._collection = self._chroma.get_collection(COLLECTION_NAME)

    # ──────────────────────────────────────────
    # 로깅 (검색/답변 누적 → log/result_YYYYMMDD.log)
    # ──────────────────────────────────────────
    def _append_log(self, text: str) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fname = LOG_DIR / f"result_{datetime.now():%Y%m%d}.log"
        with open(fname, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def _log_search(
        self, question: str, region_code: str | None, chunks: list[Chunk]
    ) -> None:
        ts = datetime.now()
        lines = [
            "",
            f"[{ts:%Y-%m-%d %H:%M:%S}][SEARCH] 질문: {question}   "
            f"region_code={region_code}   top-{len(chunks)}",
            "=" * 70,
        ]
        for i, c in enumerate(chunks, 1):
            lines += [
                f"[{i}] distance={c.distance:.4f}",
                f"    기관 : {c.institution}",
                f"    조례 : {c.law_name}",
                f"    조항 : {c.article_num}  {c.article_title}",
                f"    본문 : {c.text[:220].strip()}",
                "",
            ]
        self._append_log("\n".join(lines))

    def _log_answer(
        self, question: str, region_code: str | None, answer: str
    ) -> None:
        ts = datetime.now()
        self._append_log(
            f"[{ts:%Y-%m-%d %H:%M:%S}][ANSWER] 질문: {question}   "
            f"region_code={region_code}\n"
            f"{'-' * 70}\n{answer.strip()}\n"
        )

    # ──────────────────────────────────────────
    # 검색
    # ──────────────────────────────────────────
    def _embed(self, text: str) -> list[float]:
        resp = self._openai.embeddings.create(model=EMBED_MODEL, input=[text])
        return resp.data[0].embedding

    def search(
        self,
        question: str,
        region_code: str | None = None,
        k: int = 5,
        include_sido: bool = True,
    ) -> list[Chunk]:
        """질문 + region 필터로 청크 검색.

        전략 (시군구가 선택된 경우):
          A) 시군구 자체 조례 top-K
          B) 같은 시도 광역 조례 top-K
          → 합쳐서 거리(distance) 오름차순으로 top-K
        시군구 조례 적어도 광역 조례에서 보강돼 답변이 풍부해짐.
        """
        q_emb = self._embed(question)

        def _query(where: dict | None, n: int) -> list[Chunk]:
            try:
                res = self._collection.query(
                    query_embeddings=[q_emb], n_results=n, where=where
                )
            except Exception as e:
                # 컬렉션이 재생성됐을 가능성 → 한 번 재시도
                if "does not exist" in str(e):
                    self._refresh_collection()
                    res = self._collection.query(
                        query_embeddings=[q_emb], n_results=n, where=where
                    )
                else:
                    raise
            chunks = []
            if not res["documents"] or not res["documents"][0]:
                return chunks
            for i, doc in enumerate(res["documents"][0]):
                md = res["metadatas"][0][i]
                dist = res["distances"][0][i]
                chunks.append(Chunk(
                    text=doc,
                    region_code=md.get("region_code", ""),
                    institution=md.get("institution", ""),
                    law_name=md.get("law_name", ""),
                    article_num=md.get("article_num", ""),
                    article_title=md.get("article_title", ""),
                    distance=dist,
                ))
            return chunks

        if not region_code:
            result = _query(None, k)
            self._log_search(question, region_code, result)
            return result

        # 쿼터: 시군구 우선 60%, 광역 40%
        own_quota = max(1, int(round(k * 0.6)))
        sido_quota = k - own_quota

        # A) 시군구 자체 (쿼터의 2배 뽑아서 안에서 정렬)
        own = sorted(
            _query({"region_code": region_code}, k),
            key=lambda c: c.distance,
        )

        # B) 같은 시도 광역 조례
        sido_chunks: list[Chunk] = []
        if include_sido:
            sido_code = region_code[:2] + "000"
            if sido_code != region_code:  # 광역 본인이면 중복 호출 방지
                sido_chunks = sorted(
                    _query(
                        {"$and": [{"region_code": sido_code}, {"level": "광역"}]},
                        k,
                    ),
                    key=lambda c: c.distance,
                )

        # 쿼터 적용: 시군구 우선 채우고 남는 자리 광역으로
        result = own[:own_quota] + sido_chunks[:sido_quota]
        # 한쪽이 부족하면 다른쪽으로 보충
        if len(result) < k:
            if len(own[:own_quota]) < own_quota:
                # 시군구 부족 → 광역으로 더 채움
                need = k - len(result)
                result += sido_chunks[sido_quota:sido_quota + need]
            elif len(sido_chunks[:sido_quota]) < sido_quota:
                # 광역 부족 → 시군구로 더 채움
                need = k - len(result)
                result += own[own_quota:own_quota + need]

        # 최종 distance 순으로 정렬해서 반환
        result.sort(key=lambda c: c.distance)
        result = result[:k]
        self._log_search(question, region_code, result)
        return result

    # ──────────────────────────────────────────
    # LLM 답변 생성
    # ──────────────────────────────────────────
    def build_prompt(self, question: str, chunks: list[Chunk]) -> list[dict]:
        if not chunks:
            ctx = "(관련 조례를 찾지 못했습니다.)"
        else:
            ctx_parts = []
            for i, c in enumerate(chunks, 1):
                ctx_parts.append(
                    f"[{i}] {c.institution} {c.law_name} 제{c.article_num}조 "
                    f"({c.article_title})\n{c.text}"
                )
            ctx = "\n\n".join(ctx_parts)

        system = (
            "당신은 한국 지자체 태양광·신재생에너지 조례 전문가입니다. "
            "사용자의 질문이 한 단어이거나 짧아도, 참고 조례 안에서 관련된 조항이 "
            "있으면 적극적으로 찾아 요약하세요. "
            "참고 조례에서 직접 확인되는 내용만 답변하고, 명시되지 않은 사항은 "
            "추측하지 말고 '조례에서 확인되지 않음'이라고 답하세요. "
            "답변은 한국어로 2~5문장 이내, 구체적인 수치(보조금·이격거리·면적 등)는 "
            "그대로 인용하세요."
        )
        user = f"[참고 조례]\n{ctx}\n\n[질문]\n{question}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def answer(
        self,
        question: str,
        region_code: str | None = None,
        k: int = 5,
    ) -> dict:
        """비스트리밍 답변. {answer, chunks, source} 반환."""
        chunks = self.search(question, region_code=region_code, k=k)
        messages = self.build_prompt(question, chunks)

        resp = self._openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
        )
        text = resp.choices[0].message.content

        sources = list({
            f"{c.institution} {c.law_name} 제{c.article_num}조"
            for c in chunks
        })

        self._log_answer(question, region_code, text)
        return {"answer": text, "chunks": chunks, "sources": sources}

    def answer_stream(
        self,
        question: str,
        region_code: str | None = None,
        k: int = 5,
    ) -> tuple[Iterator[str], list[Chunk]]:
        """스트리밍 답변. (token 제너레이터, chunks) 반환."""
        chunks = self.search(question, region_code=region_code, k=k)
        messages = self.build_prompt(question, chunks)

        stream = self._openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
            stream=True,
        )

        def gen() -> Iterator[str]:
            full: list[str] = []
            for ev in stream:
                tok = ev.choices[0].delta.content
                if tok:
                    full.append(tok)
                    yield tok
            self._log_answer(question, region_code, "".join(full))

        return gen(), chunks
