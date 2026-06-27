# -*- coding: utf-8 -*-
"""2025년 흐름 + 분기 단위 신용지표 추적 — 분기보고서(IS 누적 + BS 시점)로 분석.

  python src/quarterly.py   # (fetch_dart.py로 키 설정 후)

연결(CFS) 기준. 2024~2025년 8개 분기(분기말)로:
  · 매출 모멘텀(누적 YoY)
  · 신용지표: 부채비율·유동비율(분기말 BS)·이자보상배율·Altman Z'(연환산)
를 추적한다.
  IS(매출·영업이익·순이익·금융비용): 누적(YTD, thstrm_add_amount)
  BS(자산·부채·자본·유동자산·유동부채·이익잉여금): 분기말 시점(thstrm_amount)
"""
import json
import sqlite3
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

from config import (COMPANIES, QUARTER_YEARS, QUARTERS, RAW_Q,
                    CHARTS, OUTPUT, DB_PATH, ACCOUNT_MAP)
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
CKPT = [lbl for _, lbl in QUARTERS]                     # 1Q, 상반기, 3분기, 연간
QLABEL = {"1Q": "1Q", "상반기": "2Q", "3분기": "3Q", "연간": "4Q"}
MONTHS = {"1Q": 3, "상반기": 6, "3분기": 9, "연간": 12}

# 흐름(누적) 항목 / 시점(분기말) 항목
FLOW = ["revenue", "operating_income", "net_income", "interest_expense"]
STOCK = ["total_assets", "total_liabilities", "total_equity",
         "current_assets", "current_liabilities", "retained_earnings"]

# 크로놀로지컬 시퀀스: (연도, 체크포인트, 라벨)
SEQ = [(y, k, f"{str(y)[2:]}.{QLABEL[k]}") for y in QUARTER_YEARS for k in CKPT]


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


def _match(items, target, field_priority):
    ids = set(ACCOUNT_MAP[target]["ids"])
    names = ACCOUNT_MAP[target]["names"]

    def val(it):
        for f in field_priority:
            v = to_num(it.get(f))
            if v is not None:
                return v
        return None

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


def pick_flow(items, target):   # 누적 우선
    return _match(items, target, ["thstrm_add_amount", "thstrm_amount"])


def pick_stock(items, target):  # 분기말 시점값
    return _match(items, target, ["thstrm_amount"])


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
    data = {}  # (corp, year, ckpt) -> {field: value}
    for comp in COMPANIES:
        corp_code = code_map[comp["stock_code"]][0]
        for year in QUARTER_YEARS:
            for reprt, lbl in QUARTERS:
                payload = fetch_quarter(key, corp_code, year, reprt)
                rec = {f: None for f in FLOW + STOCK}
                if payload.get("status") == "000":
                    items = payload.get("list", [])
                    for f in FLOW:
                        rec[f] = pick_flow(items, f)
                    for f in STOCK:
                        rec[f] = pick_stock(items, f)
                else:
                    print(f"  [skip] {comp['name']} {year} {lbl} status={payload.get('status')}")
                data[(comp["name"], year, lbl)] = rec
    return data


# ── 지표 계산 ────────────────────────────────────────────────
def div(a, b):
    return a / b if (a is not None and b not in (None, 0)) else None


def debt_ratio(r):    return div(r["total_liabilities"], r["total_equity"])
def curr_ratio(r):    return div(r["current_assets"], r["current_liabilities"])
def icr(r):           return div(r["operating_income"], r["interest_expense"])  # YTD=연환산 동일


def altman_z(r, ckpt):
    ta = r["total_assets"]
    if not ta:
        return None
    f = 12.0 / MONTHS[ckpt]          # 흐름 연환산
    x1 = div((r["current_assets"] or 0) - (r["current_liabilities"] or 0), ta)
    x2 = div(r["retained_earnings"], ta)
    x3 = div((r["operating_income"] or 0) * f, ta)
    x4 = div(r["total_equity"], r["total_liabilities"])
    x5 = div((r["revenue"] or 0) * f, ta)
    if None in (x1, x2, x3, x4, x5):
        return None
    return 0.717*x1 + 0.847*x2 + 3.107*x3 + 0.420*x4 + 0.998*x5


def save_db(data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = FLOW + STOCK
    cur.executescript(
        "DROP TABLE IF EXISTS quarterly;\n"
        "CREATE TABLE quarterly (corp_name TEXT, bsns_year INTEGER, checkpoint TEXT, "
        + ", ".join(f"{c} REAL" for c in cols)
        + ", PRIMARY KEY (corp_name, bsns_year, checkpoint));")
    for (corp, year, ckpt), rec in data.items():
        cur.execute(
            "INSERT OR REPLACE INTO quarterly VALUES (?,?,?," + ",".join(["?"]*len(cols)) + ")",
            [corp, year, ckpt, *[rec[c] for c in cols]])
    conn.commit(); conn.close()


# ── 차트 ─────────────────────────────────────────────────────
def revenue_momentum_chart(data, fname):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for name in ORDER:
        ys = []
        for k in CKPT:
            r25 = data.get((name, 2025, k), {}).get("revenue")
            r24 = data.get((name, 2024, k), {}).get("revenue")
            ys.append((r25/r24-1)*100 if (r25 and r24) else None)
        xs = [i for i, v in enumerate(ys) if v is not None]
        yv = [ys[i] for i in xs]
        ax1.plot(xs, yv, marker="o", label=name, color=COLORS.get(name))
        for x, v in zip(xs, yv):
            ax1.text(x, v, f"{v:+.0f}%", ha="center", va="bottom", fontsize=9)
    ax1.axhline(0, color="gray", lw=0.8)
    ax1.set_xticks(range(len(CKPT))); ax1.set_xticklabels(CKPT)
    ax1.set_title("2025 누적매출 YoY 성장률 (분기 흐름)", fontsize=13, fontweight="bold")
    ax1.set_ylabel("전년동기대비 %"); ax1.legend(); ax1.grid(alpha=0.3)

    x = list(range(len(ORDER)))
    def opm(year):
        out = []
        for name in ORDER:
            r = data.get((name, year, "연간"), {})
            out.append((r.get("operating_income") or 0)/r["revenue"]*100 if r.get("revenue") else 0)
        return out
    b1 = ax2.bar([i-0.2 for i in x], opm(2024), width=0.4, label="2024", color="#adb5bd")
    b2 = ax2.bar([i+0.2 for i in x], opm(2025), width=0.4, label="2025", color="#37b24d")
    for bars in (b1, b2):
        for r in bars:
            ax2.text(r.get_x()+r.get_width()/2, r.get_height(), f"{r.get_height():.1f}",
                     ha="center", va="bottom", fontsize=9)
    ax2.set_xticks(x); ax2.set_xticklabels(ORDER)
    ax2.set_title("영업이익률: 2024 vs 2025 (연간)", fontsize=13, fontweight="bold")
    ax2.set_ylabel("%"); ax2.legend(); ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def _series(data, fn, scale=1.0):
    """SEQ 순서대로 기업별 지표 시계열(라벨,값) 생성."""
    out = {}
    for name in ORDER:
        pts = []
        for (y, k, lbl) in SEQ:
            r = data.get((name, y, k))
            v = fn(r) if r else None
            pts.append((lbl, None if v is None else v*scale))
        out[name] = pts
    return out


def credit_chart(data, fname):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    labels = [lbl for _, _, lbl in SEQ]
    for ax, fn, title, ylab, ref in [
            (ax1, lambda r: debt_ratio(r), "부채비율 분기 추이 (낮을수록 안정)", "%", 200),
            (ax2, lambda r: curr_ratio(r), "유동비율 분기 추이 (높을수록 안정)", "%", 100)]:
        ser = _series(data, fn, scale=100.0)
        for name in ORDER:
            xs = [i for i, (_, v) in enumerate(ser[name]) if v is not None]
            yv = [ser[name][i][1] for i in xs]
            ax.plot(xs, yv, marker="o", label=name, color=COLORS.get(name))
        ax.axhline(ref, ls="--", color="gray", lw=1)
        ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_ylabel(ylab); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def altman_quarterly_chart(data, fname):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    labels = [lbl for _, _, lbl in SEQ]
    for name in ORDER:
        pts = []
        for (y, k, lbl) in SEQ:
            r = data.get((name, y, k))
            pts.append(altman_z(r, k) if r else None)
        xs = [i for i, v in enumerate(pts) if v is not None]
        yv = [pts[i] for i in xs]
        ax.plot(xs, yv, marker="o", label=name, color=COLORS.get(name))
    ax.axhline(2.90, ls="--", color="green", lw=1); ax.text(0, 2.93, "안전 2.90", color="green", fontsize=9)
    ax.axhline(1.23, ls="--", color="red", lw=1);   ax.text(0, 1.26, "위험 1.23", color="red", fontsize=9)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title("Altman Z'-Score 분기 추이 (흐름 연환산)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Z'-Score"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


# ── 리포트(key_metrics.md) ───────────────────────────────────
def write_2025_flow_section(data):
    lines = ["\n## 2025년 흐름 (분기 누적 데이터)\n",
             "> 연결 기준 누적(YTD) 매출의 전년동기대비(YoY) 성장률. 연중 모멘텀을 본다.\n",
             "| 기업 | 1Q | 상반기 | 3분기 | 연간 |", "|---|--:|--:|--:|--:|"]
    for name in ORDER:
        cells = []
        for k in CKPT:
            r25 = data.get((name, 2025, k), {}).get("revenue")
            r24 = data.get((name, 2024, k), {}).get("revenue")
            cells.append(f"{(r25/r24-1)*100:+.1f}%" if (r25 and r24) else "-")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["\n**연간 실적 2024 → 2025**\n",
              "| 기업 | 매출(억) 24→25 | 영업이익률 24→25 |", "|---|--:|--:|"]
    for name in ORDER:
        a = data.get((name, 2024, "연간"), {}); b = data.get((name, 2025, "연간"), {})
        r24, o24 = a.get("revenue"), a.get("operating_income")
        r25, o25 = b.get("revenue"), b.get("operating_income")
        rev = f"{r24/1e8:,.0f} → {r25/1e8:,.0f}" if (r24 and r25) else "-"
        opm = f"{o24/r24*100:.1f}% → {o25/r25*100:.1f}%" if (r24 and o24 and r25 and o25) else "-"
        lines.append(f"| {name} | {rev} | {opm} |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[작성] key_metrics.md (2025 흐름)")


def write_credit_section(data):
    def fmt(v, suf="", d=1):
        return "-" if v is None else f"{v:.{d}f}{suf}"
    lines = ["\n## 분기 단위 신용지표 추적\n",
             "> 분기말 BS + 누적 IS로 산출. 부채비율·유동비율은 분기말 시점, "
             "이자보상배율·Altman Z'는 누적/연환산.\n",
             "### 부채비율 분기 추이 (%)\n",
             "| 기업 | " + " | ".join(lbl for _, _, lbl in SEQ) + " |",
             "|---|" + "--:|"*len(SEQ)]
    for name in ORDER:
        cells = []
        for (y, k, _) in SEQ:
            r = data.get((name, y, k), {})
            dr = div(r.get("total_liabilities"), r.get("total_equity"))
            cells.append(fmt(dr * 100 if dr is not None else None))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["\n### 2025년 말 신용 스냅샷\n",
              "| 기업 | 부채비율 | 유동비율 | 이자보상배율 | Altman Z' |",
              "|---|--:|--:|--:|--:|"]
    for name in ORDER:
        r = data.get((name, 2025, "연간"), {})
        dr = div(r.get("total_liabilities"), r.get("total_equity"))
        cr = div(r.get("current_assets"), r.get("current_liabilities"))
        ic = icr(r); z = altman_z(r, "연간")
        lines.append(f"| {name} | {fmt(dr and dr*100)}% | {fmt(cr and cr*100,'',0)}% | "
                     f"{fmt(ic,'배')} | {fmt(z, '', 2)} |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[작성] key_metrics.md (분기 신용지표)")


def main():
    data = collect()
    save_db(data)
    revenue_momentum_chart(data, "chart9_2025_quarterly.png")
    credit_chart(data, "chart10_credit_quarterly.png")
    altman_quarterly_chart(data, "chart11_altman_quarterly.png")
    write_2025_flow_section(data)
    write_credit_section(data)

    print("\n=== 분기 신용지표 (부채비율 % | Altman Z') ===")
    for name in ORDER:
        parts = []
        for (y, k, lbl) in SEQ:
            r = data.get((name, y, k), {})
            dr = div(r.get("total_liabilities"), r.get("total_equity"))
            z = altman_z(r, k)
            parts.append(f"{lbl} {('-' if dr is None else f'{dr*100:.0f}')}/{('-' if z is None else f'{z:.2f}')}")
        print(f"  {name}: " + " | ".join(parts))
    print("\n[완료] chart9~11 + key_metrics 분기 신용지표 -> output/")


if __name__ == "__main__":
    main()
