"""
SQLite DB 초기화 + region 테이블 적재
HANDOFF.md 2-3 스키마 기준
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "solarfit.db"
REGION_CSV = ROOT / "data" / "processed" / "region.csv"
LAWD_TXT = ROOT / "data" / "행정코드" / "법정동코드 전체자료" / "법정동코드 전체자료.txt"

SCHEMA = """
CREATE TABLE IF NOT EXISTS region (
    region_code TEXT PRIMARY KEY,
    sido        TEXT NOT NULL,
    sigungu     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS power_plant (
    plant_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    region_code TEXT,
    name        TEXT,
    capacity_kw REAL,
    permit_date DATE,
    status      TEXT,
    lat         REAL,
    lng         REAL,
    address     TEXT,
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);
CREATE INDEX IF NOT EXISTS idx_plant_region ON power_plant(region_code);

CREATE TABLE IF NOT EXISTS supply_status (
    region_code TEXT,
    energy_type TEXT,
    year        INTEGER,
    gen_mwh     REAL,
    cap_cum_kw  REAL,
    cap_new_kw  REAL,
    PRIMARY KEY (region_code, energy_type, year),
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);

CREATE TABLE IF NOT EXISTS irradiance (
    region_code TEXT,
    month       INTEGER,
    irradiance  REAL,
    PRIMARY KEY (region_code, month),
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);

CREATE TABLE IF NOT EXISTS land_price (
    region_code   TEXT,
    land_category TEXT,
    price_per_m2  REAL,
    year          INTEGER,
    PRIMARY KEY (region_code, land_category, year),
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);

CREATE TABLE IF NOT EXISTS land_use (
    region_code   TEXT,
    zone_type     TEXT,
    solar_allowed TEXT,
    PRIMARY KEY (region_code, zone_type),
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);

-- 법정동코드 전체자료 (지번주소 → PNU 변환용 룩업; region과 독립)
CREATE TABLE IF NOT EXISTS legal_dong_code (
    code TEXT PRIMARY KEY,   -- 법정동코드 10자리
    name TEXT NOT NULL       -- 법정동 정식명 (예: 충청남도 논산시 부적면 충곡리)
);
CREATE INDEX IF NOT EXISTS idx_legal_dong_name ON legal_dong_code(name);

CREATE TABLE IF NOT EXISTS smp_rec (
    date DATE PRIMARY KEY,
    smp  REAL,
    rec  REAL
);

-- 자치법규(조례) 메타 + 본문 보관
-- 벡터 검색용 청크는 ChromaDB(chroma_db/)에 별도 저장
CREATE TABLE IF NOT EXISTS ordinance (
    law_id         TEXT PRIMARY KEY,   -- 자치법규ID (법령정보 API)
    mst            TEXT,                -- 자치법규일련번호 (본문 조회용 키)
    law_name       TEXT,                -- 자치법규명
    institution    TEXT,                -- 지자체기관명 (예: "당진시", "충청남도")
    region_code    TEXT,                -- 우리 region_code 매핑 (광역은 시도코드+'000')
    level          TEXT,                -- '광역' | '시군구'
    law_type       TEXT,                -- '조례' | '고시' | '규칙'
    effective_date DATE,                -- 시행일자
    full_text      TEXT,                -- 본문 원문(JSON 문자열로 저장)
    fetched_at     DATE,
    FOREIGN KEY (region_code) REFERENCES region(region_code)
);
CREATE INDEX IF NOT EXISTS idx_ord_region ON ordinance(region_code);
CREATE INDEX IF NOT EXISTS idx_ord_inst   ON ordinance(institution);
CREATE INDEX IF NOT EXISTS idx_ord_level  ON ordinance(level);
"""


def load_legal_dong(cur) -> int:
    """법정동코드 전체자료(txt, CP949) → legal_dong_code. '존재'(폐지X)만."""
    cur.execute("DELETE FROM legal_dong_code")
    rows = []
    with open(LAWD_TXT, encoding="cp949") as f:
        next(f, None)  # 헤더(법정동코드\t법정동명\t폐지여부)
        for line in f:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < 3:
                continue
            code, name, status = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if status == "존재" and len(code) == 10:
                rows.append((code, name))
    cur.executemany(
        "INSERT OR REPLACE INTO legal_dong_code (code, name) VALUES (?, ?)", rows
    )
    return len(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.executescript(SCHEMA)

    cur.execute("DELETE FROM region")
    with open(REGION_CSV, encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        rows = [(r["region_code"], r["sido"], r["sigungu"]) for r in rdr]
    cur.executemany(
        "INSERT INTO region (region_code, sido, sigungu) VALUES (?, ?, ?)", rows
    )
    con.commit()

    n_dong = load_legal_dong(cur)
    con.commit()

    cur.execute("SELECT COUNT(*) FROM region")
    print(f"DB: {DB_PATH}")
    print(f"region 적재: {cur.fetchone()[0]}건")
    print(f"legal_dong_code 적재: {n_dong}건")

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    print("\n생성된 테이블:")
    for (t,) in cur.fetchall():
        print(f"  - {t}")

    cur.execute(
        "SELECT region_code, sido, sigungu FROM region WHERE sigungu='당진시'"
    )
    print(f"\n샘플 조회 (당진시): {cur.fetchone()}")

    con.close()


if __name__ == "__main__":
    main()
