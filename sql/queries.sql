-- 기업 재무·신용 분석 쿼리 모음
-- run_sql.py 가 줄 시작의 "-- name:" 주석을 구분자로 각 쿼리를 실행/출력한다.
-- SQLD 역량 증명: 윈도우 함수(LAG, RANK), CTE, CASE.
-- 기본 분석은 연결(CFS) 기준. 마지막 쿼리는 한국콜마 연결 vs 별도(OFS) 비교.

-- name: 1) 매출 추이와 전년대비 성장률 (YoY, 윈도우 함수) [연결]
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(revenue / 1e8, 0)                                   AS 매출_억,
    ROUND(operating_income / 1e8, 0)                          AS 영업이익_억,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (PARTITION BY corp_name ORDER BY bsns_year))
          / LAG(revenue) OVER (PARTITION BY corp_name ORDER BY bsns_year), 1) AS 매출성장률_pct
FROM financials
WHERE fs_basis = 'CFS'
ORDER BY corp_name, bsns_year;

-- name: 2) 수익성 지표 (영업이익률 · 순이익률) [연결]
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(100.0 * operating_income / revenue, 1) AS 영업이익률_pct,
    ROUND(100.0 * net_income       / revenue, 1) AS 순이익률_pct,
    ROUND(100.0 * gross_profit     / revenue, 1) AS 매출총이익률_pct
FROM financials
WHERE fs_basis = 'CFS' AND revenue IS NOT NULL
ORDER BY corp_name, bsns_year;

-- name: 3) 안정성 지표 (부채비율 · 유동비율) — 여신심사 핵심 [연결]
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(100.0 * total_liabilities / total_equity, 1)     AS 부채비율_pct,
    ROUND(100.0 * current_assets / current_liabilities, 1) AS 유동비율_pct,
    CASE
        WHEN 100.0 * total_liabilities / total_equity < 100 THEN '우수(<100%)'
        WHEN 100.0 * total_liabilities / total_equity < 200 THEN '양호(<200%)'
        ELSE '주의(>=200%)'
    END AS 부채_평가
FROM financials
WHERE fs_basis = 'CFS' AND total_equity IS NOT NULL
ORDER BY corp_name, bsns_year;

-- name: 4) 수익률 지표 (ROE · ROA · 총자산회전율) [연결]
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(100.0 * net_income / total_equity, 1) AS ROE_pct,
    ROUND(100.0 * net_income / total_assets, 1) AS ROA_pct,
    ROUND(revenue * 1.0 / total_assets, 2)      AS 총자산회전율
FROM financials
WHERE fs_basis = 'CFS' AND total_equity IS NOT NULL
ORDER BY corp_name, bsns_year;

-- name: 5) 이자보상배율 (영업이익 / 금융비용) — 채무상환능력 [연결]
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(operating_income / 1e8, 0)               AS 영업이익_억,
    ROUND(interest_expense / 1e8, 1)               AS 금융비용_억,
    ROUND(operating_income / interest_expense, 1)  AS 이자보상배율,
    CASE
        WHEN operating_income / interest_expense >= 5 THEN '안전(>=5배)'
        WHEN operating_income / interest_expense >= 1 THEN '보통(1~5배)'
        ELSE '위험(<1배)'
    END AS 평가
FROM financials
WHERE fs_basis = 'CFS' AND interest_expense IS NOT NULL AND interest_expense <> 0
ORDER BY corp_name, bsns_year;

-- name: 6) 최신연도 3사 비교 + 종합 순위 (CTE + RANK) [연결]
WITH latest AS (
    SELECT f.*
    FROM financials f
    JOIN (SELECT corp_name, MAX(bsns_year) AS y
          FROM financials WHERE fs_basis = 'CFS' GROUP BY corp_name) m
      ON f.corp_name = m.corp_name AND f.bsns_year = m.y
    WHERE f.fs_basis = 'CFS'
)
SELECT
    corp_name AS 기업,
    bsns_year AS 연도,
    ROUND(revenue / 1e8, 0)                            AS 매출_억,
    ROUND(100.0 * operating_income / revenue, 1)       AS 영업이익률_pct,
    ROUND(100.0 * total_liabilities / total_equity, 1) AS 부채비율_pct,
    ROUND(100.0 * net_income / total_equity, 1)        AS ROE_pct,
    RANK() OVER (ORDER BY 100.0 * operating_income / revenue DESC) AS 수익성순위
FROM latest
ORDER BY 수익성순위;

-- name: 7) 한국콜마 연결(CFS) vs 별도(OFS) 비교 — 자회사 왜곡 제거
SELECT
    bsns_year AS 연도,
    fs_basis  AS 기준,
    ROUND(revenue / 1e8, 0)                            AS 매출_억,
    ROUND(100.0 * operating_income / revenue, 1)       AS 영업이익률_pct,
    ROUND(100.0 * total_liabilities / total_equity, 1) AS 부채비율_pct,
    ROUND(100.0 * net_income / total_equity, 1)        AS ROE_pct
FROM financials
WHERE corp_name = '한국콜마'
ORDER BY bsns_year, 기준;
