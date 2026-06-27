# -*- coding: utf-8 -*-
"""재무비율 + 신용/부실위험(Altman Z'-Score) 계산, 차트 생성, key_metrics.md 작성.

  python src/analyze.py

Altman Z'-Score (비상장/장부가 기준, 제조업)
  Z' = 0.717·X1 + 0.847·X2 + 3.107·X3 + 0.420·X4 + 0.998·X5
    X1 = 운전자본/총자산 = (유동자산-유동부채)/자산총계
    X2 = 이익잉여금/총자산
    X3 = EBIT/총자산   (EBIT ≈ 영업이익)
    X4 = 자본/총부채    (장부가 — 시가총액 불필요)
    X5 = 매출/총자산
  판정: Z'>2.90 안전 / 1.23~2.90 회색 / <1.23 부실위험
※ 원판 Z-Score의 X4(시가총액/총부채) 대신 장부가를 쓰는 비상장기업용 변형.
  주가 데이터 없이 재무제표만으로 일관 비교하기 위해 채택.
"""
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import DB_PATH, CHARTS, OUTPUT, COMPANIES

# ── 한글 폰트 ────────────────────────────────────────────────
for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    try:
        plt.rcParams["font.family"] = _f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

ORDER = [c["name"] for c in COMPANIES]
COLORS = {"코스맥스": "#d6336c", "한국콜마": "#1c7ed6", "코스메카코리아": "#f08c00"}


def load(basis="CFS"):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM financials WHERE fs_basis = ? ORDER BY corp_name, bsns_year",
        conn, params=(basis,))
    conn.close()
    return df


def load_company_all_bases(corp_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM financials WHERE corp_name = ? ORDER BY bsns_year, fs_basis",
        conn, params=(corp_name,))
    conn.close()
    return df


def add_ratios(df):
    df = df.copy()
    df["매출성장률"] = df.groupby("corp_name")["revenue"].pct_change() * 100
    df["영업이익률"] = df["operating_income"] / df["revenue"] * 100
    df["순이익률"] = df["net_income"] / df["revenue"] * 100
    df["부채비율"] = df["total_liabilities"] / df["total_equity"] * 100
    df["유동비율"] = df["current_assets"] / df["current_liabilities"] * 100
    df["ROE"] = df["net_income"] / df["total_equity"] * 100
    df["ROA"] = df["net_income"] / df["total_assets"] * 100
    df["이자보상배율"] = df["operating_income"] / df["interest_expense"]
    # Altman Z'
    X1 = (df["current_assets"] - df["current_liabilities"]) / df["total_assets"]
    X2 = df["retained_earnings"] / df["total_assets"]
    X3 = df["operating_income"] / df["total_assets"]
    X4 = df["total_equity"] / df["total_liabilities"]
    X5 = df["revenue"] / df["total_assets"]
    df["AltmanZ"] = 0.717 * X1 + 0.847 * X2 + 3.107 * X3 + 0.420 * X4 + 0.998 * X5
    return df


def _zone(z):
    if pd.isna(z):
        return "N/A"
    if z > 2.90:
        return "안전"
    if z >= 1.23:
        return "회색지대"
    return "부실위험"


# ── 차트들 ───────────────────────────────────────────────────
def line_by_company(df, col, title, ylabel, fname, pct=True):
    fig, ax = plt.subplots(figsize=(8, 5))
    for name in ORDER:
        sub = df[df["corp_name"] == name]
        ax.plot(sub["bsns_year"], sub[col], marker="o", label=name,
                color=COLORS.get(name))
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("연도"); ax.set_ylabel(ylabel)
    ax.set_xticks(sorted(df["bsns_year"].unique()))
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def bar_latest(df, col, title, ylabel, fname):
    latest = df.sort_values("bsns_year").groupby("corp_name").tail(1)
    latest = latest.set_index("corp_name").reindex(ORDER)
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(latest.index, latest[col], color=[COLORS.get(n) for n in latest.index])
    for b, v in zip(bars, latest[col]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}",
                ha="center", va="bottom", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel(ylabel); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def altman_chart(df, fname):
    latest = df.sort_values("bsns_year").groupby("corp_name").tail(1)
    latest = latest.set_index("corp_name").reindex(ORDER)
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(latest.index, latest["AltmanZ"],
                  color=[COLORS.get(n) for n in latest.index])
    ax.axhline(2.90, ls="--", color="green", lw=1)
    ax.axhline(1.23, ls="--", color="red", lw=1)
    ax.text(ax.get_xlim()[1], 2.95, "안전 2.90", ha="right", color="green", fontsize=9)
    ax.text(ax.get_xlim()[1], 1.28, "위험 1.23", ha="right", color="red", fontsize=9)
    for b, v in zip(bars, latest["AltmanZ"]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}",
                ha="center", va="bottom", fontsize=11)
    yr = int(latest['bsns_year'].iloc[0])
    ax.set_title(f"Altman Z'-Score 부실위험 진단 ({yr})", fontsize=14, fontweight="bold")
    ax.set_ylabel("Z'-Score"); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def kolmar_cfs_ofs_chart(fname):
    """한국콜마 연결(CFS) vs 별도(OFS) — 매출·영업이익률 추이 비교."""
    df = add_ratios(load_company_all_bases("한국콜마"))
    cfs = df[df["fs_basis"] == "CFS"].sort_values("bsns_year")
    ofs = df[df["fs_basis"] == "OFS"].sort_values("bsns_year")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    # (좌) 매출
    ax1.bar([y - 0.2 for y in cfs["bsns_year"]], cfs["revenue"] / 1e8,
            width=0.4, label="연결(CFS)", color="#1c7ed6")
    ax1.bar([y + 0.2 for y in ofs["bsns_year"]], ofs["revenue"] / 1e8,
            width=0.4, label="별도(OFS)", color="#a5d8ff")
    ax1.set_title("한국콜마 매출: 연결 vs 별도", fontsize=13, fontweight="bold")
    ax1.set_xlabel("연도"); ax1.set_ylabel("매출(억원)")
    ax1.set_xticks(sorted(cfs["bsns_year"])); ax1.legend(); ax1.grid(alpha=0.3, axis="y")
    # (우) 영업이익률
    ax2.plot(cfs["bsns_year"], cfs["영업이익률"], marker="o", label="연결(CFS)", color="#1c7ed6")
    ax2.plot(ofs["bsns_year"], ofs["영업이익률"], marker="s", ls="--", label="별도(OFS)", color="#e8590c")
    ax2.set_title("한국콜마 영업이익률: 연결 vs 별도", fontsize=13, fontweight="bold")
    ax2.set_xlabel("연도"); ax2.set_ylabel("%")
    ax2.set_xticks(sorted(cfs["bsns_year"])); ax2.legend(); ax2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)
    return cfs, ofs


def write_kolmar_section(cfs, ofs):
    """key_metrics.md 에 한국콜마 연결 vs 별도 비교 표를 덧붙인다."""
    lines = ["\n## 한국콜마: 연결(CFS) vs 별도(OFS)\n",
             "> 연결은 HK이노엔(제약) 등 종속회사 포함, 별도는 한국콜마 본체(화장품 ODM 중심).\n",
             "| 연도 | 매출(억)·연결 | 매출(억)·별도 | 별도/연결 | 영업이익률·연결 | 영업이익률·별도 | 부채비율·연결 | 부채비율·별도 |",
             "|---|--:|--:|--:|--:|--:|--:|--:|"]
    c = cfs.set_index("bsns_year"); o = ofs.set_index("bsns_year")
    for yr in sorted(c.index):
        if yr not in o.index:
            continue
        share = o.loc[yr, "revenue"] / c.loc[yr, "revenue"] * 100
        lines.append(
            f"| {yr} | {c.loc[yr,'revenue']/1e8:,.0f} | {o.loc[yr,'revenue']/1e8:,.0f} | "
            f"{share:.0f}% | {c.loc[yr,'영업이익률']:.1f}% | {o.loc[yr,'영업이익률']:.1f}% | "
            f"{c.loc[yr,'부채비율']:.1f}% | {o.loc[yr,'부채비율']:.1f}% |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[작성] output/key_metrics.md (한국콜마 별도 비교 추가)")


def cfs_ofs_compare_all(fname):
    """3사 공통: 연결 vs 별도 — 본체(별도) 수익성·자본효율 비교 (최신연도)."""
    cfs = add_ratios(load("CFS"))
    ofs = add_ratios(load("OFS"))
    yr = int(cfs["bsns_year"].max())
    c = cfs[cfs["bsns_year"] == yr].set_index("corp_name").reindex(ORDER)
    o = ofs[ofs["bsns_year"] == yr].set_index("corp_name").reindex(ORDER)

    x = list(range(len(ORDER)))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for ax, col, title in [(ax1, "영업이익률", "영업이익률"), (ax2, "ROE", "ROE")]:
        b1 = ax.bar([i - 0.2 for i in x], c[col], width=0.4, label="연결(CFS)", color="#868e96")
        b2 = ax.bar([i + 0.2 for i in x], o[col], width=0.4, label="별도(OFS)", color="#fab005")
        for bars in (b1, b2):
            for rect in bars:
                ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(),
                        f"{rect.get_height():.1f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x); ax.set_xticklabels(ORDER)
        ax.set_title(f"{title}: 연결 vs 별도 ({yr})", fontsize=13, fontweight="bold")
        ax.set_ylabel("%"); ax.legend(); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)
    return c, o, yr


def write_cfs_ofs_all_section(c, o, yr):
    """key_metrics.md 에 3사 연결 vs 별도(최신연도) 요약표를 덧붙인다."""
    lines = [f"\n## 3사 연결(CFS) vs 별도(OFS) — {yr}\n",
             "> 별도(본체) 기준은 종속·해외법인을 제외한 본업의 모습. 3사 모두 본체 수익성이 연결보다 높다.\n",
             "| 기업 | 별도/연결 매출 | 영업이익률(연결→별도) | ROE(연결→별도) | 부채비율(연결→별도) |",
             "|---|--:|--:|--:|--:|"]
    for name in ORDER:
        share = o.loc[name, "revenue"] / c.loc[name, "revenue"] * 100
        lines.append(
            f"| {name} | {share:.0f}% | "
            f"{c.loc[name,'영업이익률']:.1f}% → **{o.loc[name,'영업이익률']:.1f}%** | "
            f"{c.loc[name,'ROE']:.1f}% → **{o.loc[name,'ROE']:.1f}%** | "
            f"{c.loc[name,'부채비율']:.1f}% → {o.loc[name,'부채비율']:.1f}% |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[작성] output/key_metrics.md (3사 연결 vs 별도 추가)")


def write_key_metrics(df):
    latest_year = int(df["bsns_year"].max())
    lines = ["# 핵심 지표 (Key Metrics)\n",
             f"> 자동 생성 파일 — 분석 대상: {', '.join(ORDER)} · 최신 사업연도 {latest_year}\n",
             f"> 모든 수치는 DART 연결재무제표 기준.\n",
             "\n## 최신연도 스냅샷\n",
             "| 기업 | 매출(억) | 영업이익률 | 부채비율 | 유동비율 | ROE | 이자보상배율 | Altman Z' | 진단 |",
             "|---|--:|--:|--:|--:|--:|--:|--:|:--:|"]
    latest = df[df["bsns_year"] == latest_year].set_index("corp_name").reindex(ORDER)
    for name, r in latest.iterrows():
        lines.append(
            f"| {name} | {r.revenue/1e8:,.0f} | {r.영업이익률:.1f}% | "
            f"{r.부채비율:.1f}% | {r.유동비율:.0f}% | {r.ROE:.1f}% | "
            f"{r.이자보상배율:,.1f}배 | {r.AltmanZ:.2f} | {_zone(r.AltmanZ)} |")

    lines.append(f"\n## 5개년 추이 (영업이익률 %)\n")
    pivot = df.pivot(index="bsns_year", columns="corp_name", values="영업이익률")[ORDER]
    lines.append("| 연도 | " + " | ".join(ORDER) + " |")
    lines.append("|---|" + "--:|" * len(ORDER))
    for yr, row in pivot.iterrows():
        lines.append(f"| {yr} | " + " | ".join(f"{v:.1f}%" if pd.notna(v) else "-" for v in row) + " |")

    (OUTPUT / "key_metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[작성] output/key_metrics.md")


def main():
    df = add_ratios(load())

    line_by_company(df, "revenue", "매출액 추이 (3사)", "매출(원)", "chart1_revenue.png")
    line_by_company(df, "영업이익률", "영업이익률 추이 (3사)", "%", "chart2_opmargin.png")
    line_by_company(df, "부채비율", "부채비율 추이 (3사) — 낮을수록 안정", "%", "chart3_debt.png")
    line_by_company(df, "ROE", "ROE 추이 (3사)", "%", "chart4_roe.png")
    bar_latest(df, "유동비율", "유동비율 비교 (최신연도)", "%", "chart5_current.png")
    altman_chart(df, "chart6_altman.png")
    write_key_metrics(df)

    # 한국콜마 연결 vs 별도(OFS) 심층 비교
    cfs, ofs = kolmar_cfs_ofs_chart("chart7_kolmar_cfs_ofs.png")
    write_kolmar_section(cfs, ofs)

    # 3사 공통 연결 vs 별도 비교
    c, o, yr = cfs_ofs_compare_all("chart8_cfs_ofs_compare.png")
    write_cfs_ofs_all_section(c, o, yr)

    # 콘솔 요약
    pd.set_option("display.unicode.east_asian_width", True)
    cols = ["corp_name", "bsns_year", "영업이익률", "부채비율", "ROE", "이자보상배율", "AltmanZ"]
    print("\n=== 재무비율 요약 ===")
    print(df[cols].round(2).to_string(index=False))
    print("\n[완료] 차트 6종 + key_metrics.md 생성 -> output/")


if __name__ == "__main__":
    main()
