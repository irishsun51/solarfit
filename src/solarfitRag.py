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
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import chromadb
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "db" / "chroma_db"
DB_PATH = ROOT / "db" / "solarfit.db"
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
    cid: str = ""        # ChromaDB 청크 id (하이브리드 융합 시 동일 청크 식별용)
    score: float = 0.0   # RRF 융합 점수 (하이브리드 검색에서만 채워짐)


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
        self, question: str, region_code: str | None, chunks: list[Chunk],
        rewritten: str | None = None, keywords: list[str] | None = None,
    ) -> None:
        ts = datetime.now()
        head = f"[{ts:%Y-%m-%d %H:%M:%S}][SEARCH] 질문: {question}"
        if rewritten:
            head += f"   ↳재작성: {rewritten}"
        if keywords:
            head += f"   ↳키워드: {', '.join(keywords)}"
        head += f"   region_code={region_code}   top-{len(chunks)}"
        lines = ["", head, "=" * 70]
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
    # Query Rewriting — 모호한 질문만 검색용으로 명확화
    # ──────────────────────────────────────────
    # 도메인 키워드: 하나라도 있으면 "도메인 명확"으로 간주
    _DOMAIN_KW = ("태양광", "발전", "신재생", "이격", "보조금", "설치", "입지", "조례")
    # 후속/지시 질문 신호 (앞 맥락에 의존 → 재작성 필요)
    _FOLLOWUP_RE = re.compile(r"^(그럼|그러면|이건|그건|저건|아까|이 정도|그거|그 |이 |위 )")

    def _needs_rewrite(self, question: str) -> bool:
        """모호하면 True. (짧음 / 후속 신호 / 도메인 키워드 없음)"""
        q = question.strip()
        if len(q) < 12:
            return True
        if self._FOLLOWUP_RE.match(q):
            return True
        if not any(k in q for k in self._DOMAIN_KW):
            return True
        return False

    # ──────────────────────────────────────────
    # 하이브리드 검색 — 키워드 추출
    # ──────────────────────────────────────────
    # 검색에 변별력 있는 도메인 '어근' 키워드 (살리언스 높은 것부터).
    # where_document($contains)는 substring 매칭이라, 짧은 어근일수록 더 많이 잡힘.
    # (예: 조례엔 "이격거리"가 없고 "이격"만 있음 → 어근 "이격"으로 필터해야 정답이 잡힘)
    # ⚠ 코퍼스 전체가 태양광·신재생 조례라 "태양광/발전/설치/지원/신재생/보급"은
    #    비변별적(전체의 14~25%)이라 키워드 필터에서 제외 — 희소·변별력 높은 어근만 둔다.
    _KEYWORD_LEXICON = (
        "이격", "거리", "직선거리", "변전소", "영농형", "경사도",
        "개발행위", "발전시설", "관광지", "주거밀집", "보조금", "융자",
        "계통", "농지", "면적", "높이", "용량",
    )

    def _extract_keywords(self, query: str, limit: int = 2) -> list[str]:
        """질문에서 변별력 있는 도메인 어근을 최대 limit개 추출.
        substring 회수가 목적이라 더 짧은(넓은) 어근을 우선한다:
        매칭된 단어 중 다른 매칭어를 포함하는(=더 좁은) 단어는 버림.
        하나도 없으면 빈 리스트 → 키워드 경로 생략하고 순수 벡터로 폴백."""
        matched = [w for w in self._KEYWORD_LEXICON if w in query]
        picked: list[str] = []
        for w in matched:  # _KEYWORD_LEXICON 순서(살리언스) 유지
            # w 안에 더 짧은 매칭어가 들어있으면 w는 불필요하게 좁음 → 스킵
            if any(other != w and other in w for other in matched):
                continue
            if w not in picked:
                picked.append(w)
            if len(picked) >= limit:
                break
        return picked

    def _region_name(self, region_code: str | None) -> str:
        """region_code → 시군구명 (없으면 '')."""
        if not region_code:
            return ""
        try:
            con = sqlite3.connect(DB_PATH)
            row = con.execute(
                "SELECT sigungu FROM region WHERE region_code=?", (region_code,)
            ).fetchone()
            con.close()
            return row[0] if row else ""
        except Exception:
            return ""

    def rewrite_query(self, question: str, region_code: str | None = None) -> str:
        """모호한 질문을 검색용 명확한 단일 질문으로 재작성."""
        region = self._region_name(region_code)
        system = (
            "너는 한국 지자체 태양광·신재생에너지 조례 검색을 돕는다. "
            "사용자 질문을 조례 벡터 검색에 적합한 '명확한 단일 질문'으로 재작성하라. "
            f"{'지역명(' + region + ')과 ' if region else ''}'태양광 발전시설' 맥락을 "
            "자연스럽게 포함하고, 한 문장으로 간결하게 만들어라. "
            "이미 충분히 명확하면 거의 그대로 두어라. 재작성한 질문만 출력하라."
        )
        resp = self._openai.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    # ──────────────────────────────────────────
    # 검색
    # ──────────────────────────────────────────
    def _embed(self, text: str) -> list[float]:
        resp = self._openai.embeddings.create(model=EMBED_MODEL, input=[text])
        return resp.data[0].embedding

    @staticmethod
    def _rrf_fuse(lists: list[list[Chunk]], n: int, c: int = 60) -> list[Chunk]:
        """여러 순위 리스트를 Reciprocal Rank Fusion으로 융합.
        점수 = Σ 1/(c + rank). 거리/매칭 단위가 달라도 순위만 쓰므로 안전하게 병합.
        벡터 top-N에 안 뜨던 키워드 매칭 청크를 상위로 끌어올린다."""
        scores: dict[str, float] = {}
        rep: dict[str, Chunk] = {}
        for lst in lists:
            for rank, ch in enumerate(lst):
                key = ch.cid or f"{ch.law_name}|{ch.article_num}|{ch.text[:60]}"
                scores[key] = scores.get(key, 0.0) + 1.0 / (c + rank)
                rep.setdefault(key, ch)
        out: list[Chunk] = []
        for key in sorted(scores, key=lambda x: scores[x], reverse=True)[:n]:
            ch = rep[key]
            ch.score = scores[key]
            out.append(ch)
        return out

    def search(
        self,
        question: str,
        region_code: str | None = None,
        k: int = 5,
        include_sido: bool = True,
        rewrite: bool = True,
        hybrid: bool = True,
    ) -> list[Chunk]:
        """질문 + region 필터로 청크 검색.

        전략 (시군구가 선택된 경우):
          A) 시군구 자체 조례 top-K
          B) 같은 시도 광역 조례 top-K
          → 합쳐서 top-K
        시군구 조례 부족분이 광역 조례에서 보강돼 답변이 풍부해짐.

        hybrid=True: (벡터) + (키워드 필터 where_document) 결과를 RRF로 융합.
                     조문 Recall ↑. hybrid=False면 순수 벡터(기존 동작과 동일).
        """
        # 모호한 질문이면 검색용으로 재작성 (명확하면 원문 그대로)
        search_q = question
        if rewrite and self._needs_rewrite(question):
            search_q = self.rewrite_query(question, region_code)
        rewritten = search_q if search_q != question else None

        q_emb = self._embed(search_q)
        # 키워드는 '원문 질문'에서 추출 — 재작성문이 주입한 일반어(태양광/발전시설 등) 오염 방지
        keywords = self._extract_keywords(question) if hybrid else []
        # 하이브리드는 융합 품질 위해 더 깊게 회수 후 쿼터로 절단
        fetch_n = max(20, k * 4) if (hybrid and keywords) else k

        def _vquery(where: dict | None, n: int,
                    where_document: dict | None = None) -> list[Chunk]:
            """벡터 검색 (선택적으로 where_document 키워드 필터)."""
            kw = dict(query_embeddings=[q_emb], n_results=n, where=where)
            if where_document:
                kw["where_document"] = where_document
            try:
                res = self._collection.query(**kw)
            except Exception as e:
                # 컬렉션이 재생성됐을 가능성 → 한 번 재시도
                if "does not exist" in str(e):
                    self._refresh_collection()
                    res = self._collection.query(**kw)
                else:
                    raise
            chunks: list[Chunk] = []
            if not res["documents"] or not res["documents"][0]:
                return chunks
            ids = res.get("ids", [[]])
            for i, doc in enumerate(res["documents"][0]):
                md = res["metadatas"][0][i]
                chunks.append(Chunk(
                    text=doc,
                    region_code=md.get("region_code", ""),
                    institution=md.get("institution", ""),
                    law_name=md.get("law_name", ""),
                    article_num=md.get("article_num", ""),
                    article_title=md.get("article_title", ""),
                    distance=res["distances"][0][i],
                    cid=ids[0][i] if ids and ids[0] else "",
                ))
            return chunks

        def _retrieve(where: dict | None, n: int) -> list[Chunk]:
            """hybrid면 벡터+키워드 RRF 융합, 아니면 순수 벡터(거리순)."""
            vec = _vquery(where, n)
            if not (hybrid and keywords):
                return sorted(vec, key=lambda c: c.distance)
            lists = [vec]
            for kw in keywords:
                lists.append(_vquery(where, n, where_document={"$contains": kw}))
            return self._rrf_fuse(lists, n)

        # 최종 정렬 키: 하이브리드는 RRF 점수 내림차순, 아니면 거리 오름차순
        def _final_sort(items: list[Chunk]) -> None:
            if hybrid and keywords:
                items.sort(key=lambda c: c.score, reverse=True)
            else:
                items.sort(key=lambda c: c.distance)

        if not region_code:
            result = _retrieve(None, fetch_n)[:k]
            self._log_search(question, region_code, result, rewritten, keywords)
            return result

        # 쿼터: 시군구 우선 60%, 광역 40%
        own_quota = max(1, int(round(k * 0.6)))
        sido_quota = k - own_quota

        # A) 시군구 자체
        own = _retrieve({"region_code": region_code}, fetch_n)

        # B) 같은 시도 광역 조례
        sido_chunks: list[Chunk] = []
        if include_sido:
            sido_code = region_code[:2] + "000"
            if sido_code != region_code:  # 광역 본인이면 중복 호출 방지
                sido_chunks = _retrieve(
                    {"$and": [{"region_code": sido_code}, {"level": "광역"}]},
                    fetch_n,
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

        _final_sort(result)
        result = result[:k]
        self._log_search(question, region_code, result, rewritten, keywords)
        return result

    # ──────────────────────────────────────────
    # 인용 매칭 — 답변에 표기된 [N]만 출처로
    # ──────────────────────────────────────────
    @staticmethod
    def cited_chunks(answer: str, chunks: list[Chunk]) -> list[Chunk]:
        """답변 속 [N] 번호에 해당하는 청크만 반환 (1-based).
        LLM이 번호를 안 달았으면 fallback으로 전체 반환."""
        nums = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
        cited = [chunks[i - 1] for i in sorted(nums) if 1 <= i <= len(chunks)]
        return cited or chunks

    @staticmethod
    def format_article(article_num: str) -> str:
        """6자리 조번호(앞4=조, 뒤2=가지) → '제6조' / '제6조의2'. 0이면 빈 문자열."""
        s = str(article_num or "").zfill(6)
        jo, ga = int(s[:4] or 0), int(s[4:] or 0)
        if jo == 0:
            return ""
        return f"제{jo}조" + (f"의{ga}" if ga else "")

    @staticmethod
    def format_source(chunk: Chunk, with_title: bool = False) -> str:
        """출처 표기: '계룡시 도시계획 조례 제6조'.
        law_name에 지자체명이 포함돼 있어 institution은 생략(중복 방지)."""
        art = OrdinanceRAG.format_article(chunk.article_num)
        s = chunk.law_name + (f" {art}" if art else "")
        if with_title and chunk.article_title:
            s += f" ({chunk.article_title})"
        return s

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
                    f"[{i}] {self.format_source(c, with_title=True)}\n{c.text}"
                )
            ctx = "\n\n".join(ctx_parts)

        system = (
            "당신은 한국 지자체 태양광·신재생에너지 조례 전문가입니다. "
            "사용자의 질문이 한 단어이거나 짧아도, 참고 조례 안에서 관련된 조항이 "
            "있으면 적극적으로 찾아 요약하세요. "
            "참고 조례에서 직접 확인되는 내용만 답변하고, 명시되지 않은 사항은 "
            "추측하지 말고 '조례에서 확인되지 않음'이라고 답하세요. "
            "답변은 한국어로 2~5문장 이내, 구체적인 수치(보조금·이격거리·면적 등)는 "
            "그대로 인용하세요. "
            "답변 맨 끝에, 근거로 사용한 참고 조례의 번호를 [1][3]처럼 대괄호로 표기하세요. "
            "실제로 근거가 된 자료만 표기하고, 사용하지 않은 번호는 넣지 마세요. "
            "단, 조례에서 확인되지 않아 '확인되지 않음'으로 답하는 경우에는 번호를 붙이지 마세요."
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
        hybrid: bool = True,
        rewrite: bool = True,
    ) -> dict:
        """비스트리밍 답변. {answer, chunks, source} 반환.
        hybrid=False면 순수 벡터 검색, rewrite=False면 질문 재작성 끔 (재측정 비교용)."""
        chunks = self.search(question, region_code=region_code, k=k,
                             hybrid=hybrid, rewrite=rewrite)
        messages = self.build_prompt(question, chunks)

        resp = self._openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
        )
        text = resp.choices[0].message.content

        cited = self.cited_chunks(text, chunks)
        sources = list({self.format_source(c) for c in cited})

        self._log_answer(question, region_code, text)
        return {"answer": text, "chunks": chunks, "cited": cited, "sources": sources}

    def answer_stream(
        self,
        question: str,
        region_code: str | None = None,
        k: int = 5,
        hybrid: bool = True,
        rewrite: bool = True,
    ) -> tuple[Iterator[str], list[Chunk]]:
        """스트리밍 답변. (token 제너레이터, chunks) 반환.
        hybrid=False면 순수 벡터 검색, rewrite=False면 질문 재작성 끔 (재측정 비교용)."""
        chunks = self.search(question, region_code=region_code, k=k,
                             hybrid=hybrid, rewrite=rewrite)
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
