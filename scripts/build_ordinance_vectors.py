"""
자치법규(조례) → 청크화 → OpenAI 임베딩 → ChromaDB 적재

입력:
  data/raw/ordinance/*.json    본문 (collect_ordinance.py --bodies 결과)
  db/solarfit.db.ordinance      메타 (region_code, level 등)

출력:
  db/chroma_db/                 ChromaDB persistent (ordinance collection)

청크 단위: 조문 하나 = 1 청크
임베딩 모델: text-embedding-3-small (1536차원)
메타데이터: region_code, sigungu, sido, level, law_id, law_name, mst,
            article_num, article_title
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import chromadb
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
RAW_DIR = ROOT / "data" / "raw" / "ordinance"
CHROMA_DIR = ROOT / "db" / "chroma_db"
ENV_PATH = ROOT / "ini" / ".env"

EMBED_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "ordinance"
BATCH_SIZE = 100         # OpenAI 한 호출당 입력 수
MAX_CHARS_PER_CHUNK = 6000  # 매우 긴 조문 안전 차단


# ──────────────────────────────────────────
# 환경
# ──────────────────────────────────────────
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
# 청크 추출
# ──────────────────────────────────────────
def first(x):
    """str or list[0] 변환 (API가 같은 필드를 list/str 양쪽으로 줄 수 있음)."""
    if isinstance(x, list):
        return x[0] if x else ""
    return x or ""


def parse_body_json(path: Path) -> tuple[dict, list[dict]]:
    """LawService → (기본정보, 조 배열)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    svc = data.get("LawService") or {}
    info = svc.get("자치법규기본정보") or {}
    articles = (svc.get("조문") or {}).get("조") or []
    if isinstance(articles, dict):
        articles = [articles]
    return info, articles


def make_chunks(law_id: str, meta_row: tuple, articles: list[dict]) -> list[dict]:
    """1개 자치법규 → 청크 리스트."""
    region_code, sido, sigungu, level, institution, law_name, mst, law_type = meta_row

    chunks = []
    for idx, art in enumerate(articles, start=1):
        title = first(art.get("조제목", "")).strip()
        content = first(art.get("조내용", "")).strip()
        if not content:
            continue

        num = first(art.get("조문번호"))
        num_str = str(num) if num else str(idx)

        text = f"{institution} {law_name} {title}: {content}"[:MAX_CHARS_PER_CHUNK]

        chunks.append({
            "id": f"{law_id}_{num_str}_{idx}",  # idx로 중복 방지
            "text": text,
            "metadata": {
                "region_code": region_code or "",
                "sido": sido or "",
                "sigungu": sigungu or "",
                "institution": institution or "",
                "level": level or "",
                "law_id": law_id,
                "law_name": law_name or "",
                "law_type": law_type or "",
                "mst": mst or "",
                "article_num": num_str,
                "article_title": title,
            },
        })
    return chunks


def fetch_meta_row(con: sqlite3.Connection, law_id: str) -> tuple | None:
    """ordinance + region JOIN으로 region 정보까지 한 번에."""
    cur = con.execute(
        """
        SELECT o.region_code, r.sido, r.sigungu, o.level,
               o.institution, o.law_name, o.mst, o.law_type
          FROM ordinance o
          LEFT JOIN region r ON r.region_code = o.region_code
         WHERE o.law_id = ?
        """,
        (law_id,),
    )
    return cur.fetchone()


# ──────────────────────────────────────────
# 임베딩 배치
# ──────────────────────────────────────────
def embed_batch(openai_client: OpenAI, texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        resp = openai_client.embeddings.create(model=EMBED_MODEL, input=batch)
        embeddings.extend([d.embedding for d in resp.data])
        done = min(i + BATCH_SIZE, len(texts))
        print(f"  임베딩 {done}/{len(texts)} ({resp.usage.total_tokens} 토큰)")
    return embeddings


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
def main() -> int:
    load_env_file(ENV_PATH)
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 .env 또는 환경변수에 없습니다.")

    json_files = sorted(p for p in RAW_DIR.glob("*.json") if p.name != "_list.json")
    if not json_files:
        raise SystemExit(f"본문 JSON이 없습니다: {RAW_DIR}\n먼저 collect_ordinance.py --bodies 실행")

    print(f"본문 파일: {len(json_files)}건")

    con = sqlite3.connect(DB_PATH)

    # 청크 구성
    all_chunks: list[dict] = []
    skipped = 0
    for jp in json_files:
        law_id = jp.stem
        meta = fetch_meta_row(con, law_id)
        if not meta:
            skipped += 1
            continue
        _, articles = parse_body_json(jp)
        chunks = make_chunks(law_id, meta, articles)
        all_chunks.extend(chunks)
    con.close()

    print(f"메타 매칭 안 된 본문: {skipped}건")
    print(f"청크 총 {len(all_chunks)}건")

    if not all_chunks:
        print("청크가 없습니다. 종료.")
        return 1

    # ChromaDB 컬렉션 (기존 삭제 후 재생성)
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        chroma.delete_collection(COLLECTION_NAME)
        print(f"기존 컬렉션 '{COLLECTION_NAME}' 삭제")
    except Exception:
        pass
    collection = chroma.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 임베딩
    openai_client = OpenAI()
    print(f"임베딩 시작 (model={EMBED_MODEL}, batch={BATCH_SIZE})")
    texts = [c["text"] for c in all_chunks]
    embeddings = embed_batch(openai_client, texts)

    # 적재 (chromadb도 큰 배치 한 번에 가능하지만 안정성 위해 1,000개씩)
    print("ChromaDB 적재 중...")
    add_batch = 1000
    for i in range(0, len(all_chunks), add_batch):
        sl = slice(i, i + add_batch)
        collection.add(
            ids=[c["id"] for c in all_chunks[sl]],
            documents=texts[sl],
            embeddings=embeddings[sl],
            metadatas=[c["metadata"] for c in all_chunks[sl]],
        )
    print(f"적재 완료. collection.count() = {collection.count()}")

    # 샘플 검색 테스트
    print("\n[샘플 검색] '당진시 보조금 얼마야?'")
    q_emb = openai_client.embeddings.create(
        model=EMBED_MODEL, input=["당진시 보조금 얼마야?"]
    ).data[0].embedding
    res = collection.query(query_embeddings=[q_emb], n_results=3)
    for i, doc in enumerate(res["documents"][0]):
        md = res["metadatas"][0][i]
        print(f"  #{i+1} {md.get('institution')} / {md.get('law_name')} / 제{md.get('article_num')}조")
        print(f"      {doc[:150]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
