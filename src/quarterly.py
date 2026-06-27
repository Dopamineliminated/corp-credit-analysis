# -*- coding: utf-8 -*-
"""2025년 흐름 추적 — 분기 누적(YTD) 재무 데이터로 모멘텀 분석.

  python src/quarterly.py   # (fetch_dart.py로 키 설정 후)

연결(CFS) 기준. 1Q→상반기→3분기→연간 누적 매출의 YoY와 영업이익률 변화를 본다.
"""
import json
import sqlite3
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

from config import (COMPANIES, QUARTER_YEARS, QUARTERS, RAW_Q, DATA,
                    CHARTS, OUTPUT, DB_PATH)
from fetch_dart import get_api_key, load_corp_code_map, FS_URL

for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    try:
        plt.rcParams["font.family"] = _f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

ORDER = [c["name"] for c in COMPANIES]
COLORS = {"코스맥스": "#d6336c", "한국콜마": "#1c7ed6", "코스메카코리아": "#f08c00"}
CKPT = [lbl for _, lbl in QUARTERS]

# 누적 추출 대상 계정
ACCT = {
    "revenue": {"ids": ["ifrs-full_Revenue"], "names": ["매출액", "수익(매출액)", "영업수익"]},
    "operating_income": {"ids": ["dart_OperatingIncomeLoss",
                                 "ifrs-full_ProfitLossFromOperatingActivities"],
                         "names": ["영업이익", "영업이익(손실)"]},
    "net_income": {"ids": ["ifrs-full_ProfitLoss"], "names": ["당기순이익", "당기순이익(손실)"]},
}


def to_num(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pick_cum(items, target):
    """누적(YTD) 금액 추출: thstrm_add_amount 우선, 없으면 thstrm_amount."""
    ids = set(ACCT[target]["ids"])
    names = ACCT[target]["names"]

    def val(it):
        return to_num(it.get("thstrm_add_amount")) or to_num(it.get("thstrm_amount"))

    for it in items:
        if (it.get("account_id") or "").strip() in ids:
            v = val(it)
            if v is not None:
                return v
    for exact in (True, False):
        for it in items:
            nm = (it.get("account_nm") or "").strip()
            for cand in names:
                if (nm == cand) if exact else (cand in nm):
                    v = val(it)
                    if v is not None:
                        return v
    return None


def fetch_quarter(key, corp_code, year, reprt):
    out = RAW_Q / f"{corp_code}_{year}_{reprt}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    r = requests.get(FS_URL, params={"crtfc_key": key, "corp_code": corp_code,
                                     "bsns_year": str(year), "reprt_code": reprt,
                                     "fs_div": "CFS"}, timeout=60).json()
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(0.4)
    return r


def collect():
    key = get_api_key()
    code_map = load_corp_code_map(key)
    rows = []  # (corp, year, ckpt, revenue, op, net)
    for comp in COMPANIES:
        corp_code = code_map[comp["stock_code"]][0]
        for year in QUARTER_YEARS:
            for reprt, lbl in QUARTERS:
                data = fetch_quarter(key, corp_code, year, reprt)
                if data.get("status") != "000":
                    print(f"  [skip] {comp['name']} {year} {lbl} status={data.get('status')}")
                    rows.append((comp["name"], year, lbl, None, None, None))
                    continue
                items = data.get("list", [])
                rows.append((comp["name"], year, lbl,
                             pick_cum(items, "revenue"),
                             pick_cum(items, "operating_income"),
                             pick_cum(items, "net_income")))
    return rows


def save_db(rows):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS quarterly;
        CREATE TABLE quarterly (
            corp_name TEXT, bsns_year INTEGER, checkpoint TEXT,
            revenue_cum REAL, operating_income_cum REAL, net_income_cum REAL,
            PRIMARY KEY (corp_name, bsns_year, checkpoint)
        );""")
    cur.executemany("INSERT OR REPLACE INTO quarterly VALUES (?,?,?,?,?,?)", rows)
    conn.commit(); conn.close()


def chart(rows, fname):
    # rows -> dict[(corp,year,ckpt)] = (rev, op, net)
    d = {(c, y, k): (rev, op, net) for (c, y, k, rev, op, net) in rows}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # (좌) 2025 누적매출 YoY% by checkpoint
    for name in ORDER:
        ys = []
        for k in CKPT:
            r25 = d.get((name, 2025, k), (None,))[0]
            r24 = d.get((name, 2024, k), (None,))[0]
            ys.append((r25 / r24 - 1) * 100 if (r25 and r24) else None)
        xs = [i for i, v in enumerate(ys) if v is not None]
        yv = [v for v in ys if v is not None]
        ax1.plot(xs, yv, marker="o", label=name, color=COLORS.get(name))
        for x, v in zip(xs, yv):
            ax1.text(x, v, f"{v:+.0f}%", ha="center", va="bottom", fontsize=9)
    ax1.axhline(0, color="gray", lw=0.8)
    ax1.set_xticks(range(len(CKPT))); ax1.set_xticklabels(CKPT)
    ax1.set_title("2025 누적매출 YoY 성장률 (분기 흐름)", fontsize=13, fontweight="bold")
    ax1.set_ylabel("전년동기대비 %"); ax1.legend(); ax1.grid(alpha=0.3)

    # (우) 영업이익률(연간) 2024 vs 2025
    x = list(range(len(ORDER)))
    def opm(year):
        out = []
        for name in ORDER:
            rev, op, _ = d.get((name, year, "연간"), (None, None, None))
            out.append(op / rev * 100 if (rev and op) else 0)
        return out
    b1 = ax2.bar([i - 0.2 for i in x], opm(2024), width=0.4, label="2024", color="#adb5bd")
    b2 = ax2.bar([i + 0.2 for i in x], opm(2025), width=0.4, label="2025", color="#37b24d")
    for bars in (b1, b2):
        for r in bars:
            ax2.text(r.get_x() + r.get_width() / 2, r.get_height(),
                     f"{r.get_height():.1f}", ha="center", va="bottom", fontsize=9)
    ax2.set_xticks(x); ax2.set_xticklabels(ORDER)
    ax2.set_title("영업이익률: 2024 vs 2025 (연간)", fontsize=13, fontweight="bold")
    ax2.set_ylabel("%"); ax2.legend(); ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)
    return d


def write_section(d):
    lines = ["\n## 2025년 흐름 (분기 누적 데이터)\n",
             "> 연결 기준 누적(YTD) 매출의 전년동기대비(YoY) 성장률. 연중 모멘텀을 본다.\n",
             "| 기업 | 1Q | 상반기 | 3분기 | 연간 |",
             "|---|--:|--:|--:|--:|"]
    for name in ORDER:
        cells = []
        for k in CKPT:
            r25 = d.get((name, 2025, k), (None,))[0]
            r24 = d.get((name, 2024, k), (None,))[0]
            cells.append(f"{(r25/r24-1)*100:+.1f}%" if (r25 and r24) else "-")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    # 연간 매출/영업이익률 2024→2025
    lines += ["\n**연간 실적 2024 → 2025**\n",
              "| 기업 | 매출(억) 24→25 | 영업이익률 24→25 |", "|---|--:|--:|"]
    for name in ORDER:
        r24, o24, _ = d.get((name, 2024, "연간"), (None, None, None))
        r25, o25, _ = d.get((name, 2025, "연간"), (None, None, None))
        rev = f"{r24/1e8:,.0f} → {r25/1e8:,.0f}" if (r24 and r25) else "-"
        opm = (f"{o24/r24*100:.1f}% → {o25/r25*100:.1f}%"
               if (r24 and o24 and r25 and o25) else "-")
        lines.append(f"| {name} | {rev} | {opm} |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[작성] output/key_metrics.md (2025 분기 흐름 추가)")


def main():
    rows = collect()
    save_db(rows)
    d = chart(rows, "chart9_2025_quarterly.png")
    write_section(d)
    print("\n=== 2025 누적매출 YoY ===")
    for name in ORDER:
        cells = []
        for k in CKPT:
            r25 = d.get((name, 2025, k), (None,))[0]
            r24 = d.get((name, 2024, k), (None,))[0]
            cells.append(f"{k} {(r25/r24-1)*100:+.1f}%" if (r25 and r24) else f"{k} -")
        print(f"  {name}: " + " | ".join(cells))
    print("\n[완료] chart9 + key_metrics 2025 흐름 -> output/")


if __name__ == "__main__":
    main()
