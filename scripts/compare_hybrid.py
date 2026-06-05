"""하이브리드 검색 on/off 비교 (로컬 확인용).

사용:
    python scripts/compare_hybrid.py                      # 기본 예시 3개
    python scripts/compare_hybrid.py "이격거리 기준" 44250  # 질문+시군구코드 직접
    python scripts/compare_hybrid.py "보조금 얼마야" 44270 --answer  # 답변까지 생성

시군구 코드 예: 당진시 44270 / 계룡시 44250 / 논산시 44230 / 천안시 44130
"""
import sys
from pathlib import Path

# Windows 콘솔 한글 깨짐 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.solarfitRag import OrdinanceRAG  # noqa: E402


def show(rag, q, rc, with_answer):
    print("=" * 72)
    print(f"질문: {q}   (region={rc})")
    print(f"추출 키워드: {rag._extract_keywords(q)}")
    # 재작성 끔(rewrite=False): 목록과 답변이 '같은 검색'을 쓰도록 해 [N] 번호를 일치시킴
    for mode in (False, True):
        print(f"\n  ── hybrid={mode} {'(순수 벡터)' if not mode else '(벡터+키워드 RRF)'} ──")
        if with_answer:
            # 답변이 실제 사용한 청크를 그대로 표시 → 답변의 [N]이 목록 번호와 정확히 일치
            res = rag.answer(q, region_code=rc, hybrid=mode, rewrite=False)
            chunks = res["chunks"]
        else:
            chunks = rag.search(q, region_code=rc, k=5, hybrid=mode, rewrite=False)
        for i, c in enumerate(chunks, 1):
            tag = f"score={c.score:.4f}" if mode else f"dist={c.distance:.4f}"
            print(f"   [{i}] {tag}  {OrdinanceRAG.format_source(c)}  ({c.article_title})")
        if with_answer:
            print(f"   ▶ 답변: {res['answer'].strip()}")
            print(f"   ▶ 출처: {res['sources']}")
    print()


def main():
    args = [a for a in sys.argv[1:] if a != "--answer"]
    with_answer = "--answer" in sys.argv
    rag = OrdinanceRAG()

    if len(args) >= 2:
        cases = [(args[0], args[1])]
    else:
        cases = [
            ("이격거리 기준 알려줘", "44250"),
            ("태양광 발전 보조금 지원", "44270"),
            ("개발행위허가 기준", "44250"),
        ]
    for q, rc in cases:
        show(rag, q, rc, with_answer)


if __name__ == "__main__":
    main()
