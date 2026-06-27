# -*- coding: utf-8 -*-
"""프로젝트 공통 설정: 분석 대상 기업 · 연도 · 재무계정 매핑."""
from pathlib import Path

# 프로젝트 루트 (이 파일 기준 상위 폴더)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
OUTPUT = ROOT / "output"
CHARTS = OUTPUT / "charts"
DB_PATH = OUTPUT / "corp.db"

for _p in (DATA, RAW, OUTPUT, CHARTS):
    _p.mkdir(parents=True, exist_ok=True)

# ── 분석 대상: 화장품 ODM 3사 ────────────────────────────────
# kbeauty-export-analysis에서 "ODM이 K뷰티 성장의 구조적 수혜자"라고 결론냈다.
# 그 후속으로 "그럼 그 ODM들은 재무적으로 누가 더 튼튼한가?"를 파고든다.
COMPANIES = [
    {"name": "코스맥스",       "stock_code": "192820"},
    {"name": "한국콜마",       "stock_code": "161890"},
    {"name": "코스메카코리아", "stock_code": "241710"},
]

# 분석 연도 (사업보고서 기준)
YEARS = [2020, 2021, 2022, 2023, 2024]

# DART 보고서 코드: 11011=사업보고서(연간), 11012=반기, 11013=1분기, 11014=3분기
REPRT_CODE = "11011"
# 재무제표 구분: CFS=연결, OFS=별도
# 기본 분석은 연결(CFS) 기준. 별도(OFS)는 한국콜마의 자회사(제약 등) 왜곡을
# 제거한 "순수 본체" 비교를 위해 함께 수집한다.
FS_DIV = "CFS"
FS_DIVS = ["CFS", "OFS"]

# ── 재무계정 추출 매핑 ───────────────────────────────────────
# DART 전체재무제표 API의 account_id(IFRS 표준태그)를 1순위로,
# account_nm(계정명) 부분일치를 2순위(폴백)로 매칭한다.
ACCOUNT_MAP = {
    "revenue":             {"ids": ["ifrs-full_Revenue", "ifrs_Revenue"],
                            "names": ["매출액", "수익(매출액)", "영업수익"]},
    "cogs":                {"ids": ["ifrs-full_CostOfSales"],
                            "names": ["매출원가"]},
    "gross_profit":        {"ids": ["ifrs-full_GrossProfit"],
                            "names": ["매출총이익"]},
    "operating_income":    {"ids": ["dart_OperatingIncomeLoss",
                                    "ifrs-full_ProfitLossFromOperatingActivities"],
                            "names": ["영업이익", "영업이익(손실)"]},
    "net_income":          {"ids": ["ifrs-full_ProfitLoss"],
                            "names": ["당기순이익", "당기순이익(손실)", "연결당기순이익"]},
    "total_assets":        {"ids": ["ifrs-full_Assets"],
                            "names": ["자산총계"]},
    "total_liabilities":   {"ids": ["ifrs-full_Liabilities"],
                            "names": ["부채총계"]},
    "total_equity":        {"ids": ["ifrs-full_Equity"],
                            "names": ["자본총계"]},
    "current_assets":      {"ids": ["ifrs-full_CurrentAssets"],
                            "names": ["유동자산"]},
    "current_liabilities": {"ids": ["ifrs-full_CurrentLiabilities"],
                            "names": ["유동부채"]},
    "retained_earnings":   {"ids": ["ifrs-full_RetainedEarnings"],
                            "names": ["이익잉여금", "이익잉여금(결손금)"]},
    # 이자비용: 표준태그가 회사마다 달라 금융비용(FinanceCosts)으로 근사한다.
    # (금융원가는 이자비용+외화환산손실 등을 포함 → 이자보상배율은 다소 보수적으로 계산됨)
    "interest_expense":    {"ids": ["ifrs-full_FinanceCosts", "ifrs-full_InterestExpense"],
                            "names": ["금융원가", "금융비용", "이자비용"]},
}

# 추출 순서(컬럼 순서 고정용)
ACCOUNT_ORDER = list(ACCOUNT_MAP.keys())
