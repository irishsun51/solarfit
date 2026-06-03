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

    cur.execute("SELECT COUNT(*) FROM region")
    print(f"DB: {DB_PATH}")
    print(f"region 적재: {cur.fetchone()[0]}건")

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
