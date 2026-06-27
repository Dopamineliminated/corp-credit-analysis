-- 기업 재무·신용 분석 DB 스키마
-- DART 전체재무제표(연결)를 적재한다.

DROP TABLE IF EXISTS company;
DROP TABLE IF EXISTS fs_raw;
DROP TABLE IF EXISTS financials;

-- 분석 대상 기업
CREATE TABLE company (
    corp_code   TEXT PRIMARY KEY,   -- DART 고유번호(8자리)
    corp_name   TEXT NOT NULL,
    stock_code  TEXT                 -- 종목코드(6자리)
);

-- 원천 재무제표 라인아이템 (투명성 확보용 전체 덤프)
CREATE TABLE fs_raw (
    corp_name   TEXT NOT NULL,
    bsns_year   INTEGER NOT NULL,
    fs_basis    TEXT NOT NULL,       -- CFS(연결)/OFS(별도)
    sj_div      TEXT,                -- BS/IS/CIS/CF/SCE
    account_id  TEXT,                -- IFRS 표준 태그
    account_nm  TEXT,                -- 계정명
    amount      REAL,                -- 당기 금액(원)
    PRIMARY KEY (corp_name, bsns_year, fs_basis, sj_div, account_id, account_nm)
);

-- 분석용으로 정제한 핵심 재무계정 (기업·연도·기준 단위, 단위: 원)
CREATE TABLE financials (
    corp_name           TEXT NOT NULL,
    bsns_year           INTEGER NOT NULL,
    fs_basis            TEXT NOT NULL,   -- CFS(연결)/OFS(별도)
    revenue             REAL,   -- 매출액
    cogs                REAL,   -- 매출원가
    gross_profit        REAL,   -- 매출총이익
    operating_income    REAL,   -- 영업이익(EBIT 근사)
    net_income          REAL,   -- 당기순이익
    total_assets        REAL,   -- 자산총계
    total_liabilities   REAL,   -- 부채총계
    total_equity        REAL,   -- 자본총계
    current_assets      REAL,   -- 유동자산
    current_liabilities REAL,   -- 유동부채
    retained_earnings   REAL,   -- 이익잉여금
    interest_expense    REAL,   -- 이자비용
    PRIMARY KEY (corp_name, bsns_year, fs_basis)
);
