# 화장품 ODM 3사 재무·신용 분석 (2020–2024)

> DART 전자공시 재무제표를 **SQL과 Python**으로 분석해, 화장품 ODM 3사
> (**코스맥스·한국콜마·코스메카코리아**)의 **수익성·안정성·부실위험**을 진단한 프로젝트.
> 여신심사관·IR·전략기획의 시선으로 *"누가 성장하고, 누가 재무적으로 단단한가"* 를 데이터로 답한다.

**Tech:** Python (pandas · matplotlib) · SQL (SQLite, 윈도우 함수·CTE·RANK) · DART OpenAPI
**분석 기준:** 연결재무제표 5개년(2020–2024) · 재무비율 8종 + **Altman Z'-Score**(부실위험)

> 자매 프로젝트 [`kbeauty-export-analysis`](https://github.com/Dopamineliminated/kbeauty-export-analysis)에서
> *"ODM이 K뷰티 성장의 구조적 수혜자"* 라고 결론냈다. 이 프로젝트는 그 후속편 —
> **"그렇다면 그 ODM들은 재무적으로 진짜 튼튼한가?"** 를 개별 기업 재무제표로 검증한다.

---

## TL;DR — 핵심 결론 4가지

1. **산업 동반 회복.** 3사 모두 2022년 동반 부진(중국 봉쇄·원가 부담) 이후 **2023~24년 V자 회복**, 2024년 매출·수익성이 사상 최고 수준. 영업이익률은 3사 모두 8~12%대로 수렴.
2. **외형은 대형 2사, 효율은 소형사.** 매출은 **한국콜마(2.45조) > 코스맥스(2.17조) ≫ 코스메카(0.52조)**. 그러나 영업이익률·ROE는 **코스메카코리아가 1위**(11.5%·17.5%).
3. **성장–안정의 트레이드오프.** **코스맥스**는 외형·수익성 회복이 강하지만 **부채비율 280%·유동비율 84%·이자보상배율 2.6배**로 레버리지 의존도가 높다. 반면 **코스메카코리아**는 **부채비율 68%·이자보상배율 14배**로 재무 무결성이 압도적.
4. **부실위험(Altman Z') 진단.** 3사 모두 회색지대지만 서열이 뚜렷하다 — **코스메카(2.32, 안전 근접) > 코스맥스(1.65) > 한국콜마(1.42, 위험선 근접)**. *여신 관점의 신용리스크는 코스메카 < 코스맥스·한국콜마.*

> 숫자 산출 근거는 [`output/key_metrics.md`](output/key_metrics.md), 상세 해설은 [`report/REPORT.md`](report/REPORT.md),
> 면접 활용은 [`report/면접활용_가이드.md`](report/면접활용_가이드.md) 참조.

---

## 분석 결과

### 1) 영업이익률 — 2022 동반 저점 → 코스메카 역전
![영업이익률](output/charts/chart2_opmargin.png)

2020년엔 한국콜마(9.2%)가 선두였지만, 2023년부터 **코스메카코리아가 10%대로 역전**한다. 규모는 가장 작지만 미국 자회사(잉글우드랩) 정상화와 고부가 라인 확대로 마진 체질이 가장 빠르게 개선됐다.

### 2) 부채비율 — 코스맥스의 레버리지 부담
![부채비율](output/charts/chart3_debt.png)

코스맥스는 200~330%대를 오가며 3사 중 가장 높다. 공격적 외형 성장(설비·해외법인 투자)을 부채로 조달한 결과다. 코스메카는 108% → **68%**로 꾸준히 디레버리징하며 정반대 행보.

### 3) ROE — 회복의 질
![ROE](output/charts/chart4_roe.png)

코스맥스는 2020·2022년 **순손실(ROE 마이너스)**을 겪었으나 2024년 17.4%로 급반등. 코스메카는 변동성 없이 17.5%까지 꾸준히 상승해 **이익의 안정성**에서 앞선다.

### 4) 유동비율 — 단기 지급능력
![유동비율](output/charts/chart5_current.png)

코스메카(150%)만 100%를 넘고, **코스맥스(84%)·한국콜마(71%)는 100% 미만** — 유동부채가 유동자산을 초과하는 단기 유동성 부담이 존재한다.

### 5) Altman Z'-Score — 부실위험 종합 진단
![Altman Z](output/charts/chart6_altman.png)

장부가 기반 Altman Z'(제조업·비상장 변형)로 5개 재무축을 합산한 종합 부실위험 지표. **코스메카(2.32)가 안전지대(2.90)에 가장 근접**, 한국콜마(1.42)는 위험선(1.23)에 가장 가깝다.

---

## 기술 스택 & 방법

| 단계 | 도구 | 내용 |
|---|---|---|
| 수집 | **DART OpenAPI** | 상장사 고유번호 매핑 후 전체재무제표(연결) 5개년 수집 ([`src/fetch_dart.py`](src/fetch_dart.py)) |
| 적재 | **SQL** (SQLite) | `schema.sql`로 원천/정제 테이블 정의, 라인아이템 3,100여 건 적재 ([`src/build_db.py`](src/build_db.py)) |
| 분석 | **SQL** 쿼리 | 윈도우 함수(LAG)·CTE·CASE·RANK로 YoY·비율·순위 계산 ([`sql/queries.sql`](sql/queries.sql)) |
| 분석 | **Python** (pandas) | 재무비율 8종 + **Altman Z'-Score** 계산 ([`src/analyze.py`](src/analyze.py)) |
| 시각화 | **matplotlib** | 차트 6종 자동 생성 (`output/charts/`) |

## 프로젝트 구조

```
corp-credit-analysis/
├── data/            # SOURCES.md(출처), raw/(재무제표 JSON), corp_codes.csv
├── sql/             # schema.sql, queries.sql
├── src/             # config · fetch_dart · build_db · run_sql · analyze
├── output/          # corp.db, charts/*.png, key_metrics.md
└── report/          # REPORT.md(분석 리포트), 면접활용_가이드.md
```

## 실행 방법

```bash
pip install -r requirements.txt

# DART 무료 인증키 발급(https://opendart.fss.or.kr) 후
export DART_API_KEY=발급받은키        # 또는 data/.dart_key 파일에 키 저장

python src/fetch_dart.py   # DART에서 재무제표 수집 -> data/raw/
python src/build_db.py     # SQLite DB 적재
python src/run_sql.py      # 분석 SQL 6종 실행·출력
python src/analyze.py      # 재무비율 + Altman Z + 차트 6종 생성
```

## 데이터 출처 & 한계
- 출처: 금융감독원 전자공시(DART) OpenAPI. 상세·한계는 [`data/SOURCES.md`](data/SOURCES.md).
- 연결 기준이라 비(非)화장품 사업(한국콜마의 제약 등)이 합산되어 있다.
- 이자보상배율의 분모는 금융비용(FinanceCosts)으로 근사했다(보수적 계산).
- Altman Z'는 장부가 기반 변형으로, 절대수치보다 **3사 상대비교**로 해석한다.

> 본 분석은 공개 1차 재무데이터 기반의 학습/포트폴리오 목적이며, 투자 권유가 아니다.
