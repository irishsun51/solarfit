# -*- coding: utf-8 -*-
"""HWP5(한글) → 텍스트 추출. stdlib + olefile만 사용.

사용:
    from scripts.hwp_to_text import extract_text
    txt = extract_text("foo.hwp")

    # CLI: 파일(들)의 이격 관련 줄 출력
    python scripts/hwp_to_text.py "C:/.../foo.hwp" ["..." ...]
    python scripts/hwp_to_text.py --full "foo.hwp"     # 전체 텍스트
"""
from __future__ import annotations
import sys, zlib, struct
from pathlib import Path
import olefile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# HWP5 PARA_TEXT(tag 0x43) 제어문자 분류
_CTRL_8 = {1,2,3,11,12,14,15,16,17,18,21,22,23} | {4,5,6,7,8,9,19,20}  # 8 wchar 차지
_CTRL_1 = {0,13,24,25,26,27,28,29,30,31}                               # 1 wchar(제거)
_TAG_PARA_TEXT = 0x43


def _para_text(payload: bytes) -> str:
    res, n, i = [], len(payload)//2, 0
    while i < n:
        code = payload[2*i] | (payload[2*i+1] << 8)
        if code in _CTRL_8:
            i += 8
        elif code == 10:
            res.append("\n"); i += 1
        elif code in _CTRL_1:
            i += 1
        elif 0xD800 <= code <= 0xDFFF:   # 서로게이트(디코딩 잔여) 제거
            i += 1
        else:
            res.append(chr(code)); i += 1
    return "".join(res)


def _records(data: bytes):
    pos = 0
    while pos + 4 <= len(data):
        header = struct.unpack_from("<I", data, pos)[0]; pos += 4
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            size = struct.unpack_from("<I", data, pos)[0]; pos += 4
        yield tag, data[pos:pos+size]
        pos += size


def extract_text(hwp_path: str | Path) -> str:
    """HWP5 파일 → 본문 텍스트(문단 \\n 구분)."""
    ole = olefile.OleFileIO(str(hwp_path))
    try:
        fh = ole.openstream("FileHeader").read()
        compressed = bool(fh[36] & 0x01)
        paras = []
        for s in sorted(x for x in ole.listdir() if x and x[0] == "BodyText"):
            raw = ole.openstream(s).read()
            data = zlib.decompress(raw, -15) if compressed else raw
            for tag, payload in _records(data):
                if tag == _TAG_PARA_TEXT:
                    t = _para_text(payload).strip()
                    if t:
                        paras.append(t)
        return "\n".join(paras)
    finally:
        ole.close()


_KW = ("이격", "직선거리", "발전시설", "발전설비", "주거", "주택", "도로", "미터", "농지", "경계")


def main():
    args = sys.argv[1:]
    full = "--full" in args
    files = [a for a in args if a != "--full"]
    for f in files:
        print("=" * 78)
        print(f"📄 {Path(f).name}")
        try:
            txt = extract_text(f)
        except Exception as e:
            print(f"  ❌ 추출 실패: {e}")
            continue
        if full:
            print(txt)
            continue
        lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
        hit = [ln for ln in lines if any(k in ln for k in _KW)]
        for ln in hit:
            print("  " + ln[:240])


if __name__ == "__main__":
    main()
