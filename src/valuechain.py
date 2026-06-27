# -*- coding: utf-8 -*-
"""K-뷰티 밸류체인 분석 — 원료(후방) → ODM(제조) → 브랜드(전방).

  python src/valuechain.py   # (fetch_dart.py로 키 설정 후)

가치사슬 계층별로 수익성·자본효율·신용을 비교해 "누가 돈을 버는가"를 본다.
연결(CFS) 사업보고서 기준, 2024년 단면 + 2020→2024 매출 CAGR.
"""
import json
import sqlite3
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

from config import REPRT_CODE, DATA, CHARTS, OUTPUT, DB_PATH, ACCOUNT_ORDER
from build_db import pick_account, to_number
from fetch_dart import get_api_key, load_corp_code_map, FS_URL

for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    try:
        plt.rcParams["font.family"] = _f
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

RAW_VC = DATA / "raw_vc"
RAW_VC.mkdir(parents=True, exist_ok=True)

# 밸류체인 계층 (이름, 종목코드)
LAYERS = {
    "원료": [("선진뷰티사이언스", "086710"), ("대봉엘에스", "078140")],
    "ODM": [("코스맥스", "192820"), ("한국콜마", "161890"), ("코스메카코리아", "241710")],
    "브랜드": [("아모레퍼시픽", "090430"), ("LG생활건강", "051900"),
             ("클리오", "237880"), ("마녀공장", "439090")],
}
LAYER_COLOR = {"원료": "#2f9e44", "ODM": "#1c7ed6", "브랜드": "#e8590c"}
YEARS_VC = [2020, 2024]


def fetch_annual(key, corp_code, year):
    out = RAW_VC / f"{corp_code}_{year}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    r = requests.get(FS_URL, params={"crtfc_key": key, "corp_code": corp_code,
                                     "bsns_year": str(year), "reprt_code": REPRT_CODE,
                                     "fs_div": "CFS"}, timeout=60).json()
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(0.4)
    return r


def extract(payload):
    if payload.get("status") != "000":
        return None
    items = payload.get("list", [])
    return {t: pick_account(items, t) for t in ACCOUNT_ORDER}


def altman_z(f):
    ta = f.get("total_assets")
    if not ta:
        return None
    def d(a, b):
        return a / b if (a is not None and b not in (None, 0)) else None
    x1 = d((f.get("current_assets") or 0) - (f.get("current_liabilities") or 0), ta)
    x2 = d(f.get("retained_earnings"), ta)
    x3 = d(f.get("operating_income"), ta)
    x4 = d(f.get("total_equity"), f.get("total_liabilities"))
    x5 = d(f.get("revenue"), ta)
    if None in (x1, x2, x3, x4, x5):
        return None
    return 0.717*x1 + 0.847*x2 + 3.107*x3 + 0.420*x4 + 0.998*x5


def collect():
    key = get_api_key()
    code_map = load_corp_code_map(key)
    rows = []  # dict per company
    for layer, members in LAYERS.items():
        for name, stock in members:
            corp_code = code_map.get(stock, (None,))[0]
            if not corp_code:
                print(f"  [skip] {name}({stock}) corp_code 없음")
                continue
            fin = {y: extract(fetch_annual(key, corp_code, y)) for y in YEARS_VC}
            f24 = fin.get(2024)
            if not f24:
                print(f"  [skip] {name} 2024 데이터 없음")
                continue
            rev24, rev20 = f24.get("revenue"), (fin.get(2020) or {}).get("revenue")
            def pct(a, b):
                return a / b * 100 if (a is not None and b) else None
            cagr = ((rev24 / rev20) ** (1 / 4) - 1) * 100 if (rev24 and rev20) else None
            rows.append({
                "layer": layer, "name": name,
                "revenue": rev24,
                "opm": pct(f24.get("operating_income"), rev24),
                "roe": pct(f24.get("net_income"), f24.get("total_equity")),
                "debt": pct(f24.get("total_liabilities"), f24.get("total_equity")),
                "altman": altman_z(f24),
                "cagr": cagr,
            })
            opm = rows[-1]["opm"]
            opm_s = f"{opm:.1f}%" if opm is not None else "N/A"
            print(f"[수집] {layer:4s} {name}  매출 {rev24/1e8:,.0f}억  영업이익률 {opm_s}")
    return rows


def save_db(rows):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS valuechain;
        CREATE TABLE valuechain (
            layer TEXT, name TEXT, revenue REAL, opm REAL, roe REAL,
            debt REAL, altman REAL, cagr REAL, PRIMARY KEY (name));""")
    for r in rows:
        cur.execute("INSERT OR REPLACE INTO valuechain VALUES (?,?,?,?,?,?,?,?)",
                    [r["layer"], r["name"], r["revenue"], r["opm"], r["roe"],
                     r["debt"], r["altman"], r["cagr"]])
    conn.commit(); conn.close()


def chart(rows, fname):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # (좌) 영업이익률 vs ROE 산점도, 계층별 색
    for layer in LAYERS:
        pts = [r for r in rows if r["layer"] == layer and r["opm"] is not None and r["roe"] is not None]
        ax1.scatter([r["opm"] for r in pts], [r["roe"] for r in pts],
                    s=160, color=LAYER_COLOR[layer], label=layer, alpha=0.8, edgecolors="white")
        for r in pts:
            ax1.annotate(r["name"], (r["opm"], r["roe"]),
                         xytext=(5, 5), textcoords="offset points", fontsize=9)
    ax1.set_xlabel("영업이익률 (%)"); ax1.set_ylabel("ROE (%)")
    ax1.set_title("수익성 × 자본효율 (2024)", fontsize=13, fontweight="bold")
    ax1.axhline(0, color="gray", lw=0.6); ax1.grid(alpha=0.3); ax1.legend(title="계층")

    # (우) 계층 평균 영업이익률·매출 CAGR
    layers = list(LAYERS.keys())
    def avg(layer, key):
        vals = [r[key] for r in rows if r["layer"] == layer and r[key] is not None]
        return sum(vals) / len(vals) if vals else 0
    x = range(len(layers))
    b1 = ax2.bar([i - 0.2 for i in x], [avg(l, "opm") for l in layers], width=0.4,
                 label="영업이익률(평균)", color="#495057")
    b2 = ax2.bar([i + 0.2 for i in x], [avg(l, "cagr") for l in layers], width=0.4,
                 label="매출 CAGR 20→24(평균)", color="#f59f00")
    for bars in (b1, b2):
        for r in bars:
            ax2.text(r.get_x() + r.get_width() / 2, r.get_height(), f"{r.get_height():.1f}",
                     ha="center", va="bottom", fontsize=9)
    ax2.set_xticks(list(x)); ax2.set_xticklabels(layers)
    ax2.set_title("계층별 평균: 수익성·성장성 (%)", fontsize=13, fontweight="bold")
    ax2.set_ylabel("%"); ax2.legend(); ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(CHARTS / fname, dpi=120); plt.close(fig)


def write_section(rows):
    def f(v, suf="", d=1):
        return "-" if v is None else f"{v:.{d}f}{suf}"
    lines = ["\n## K-뷰티 밸류체인 비교 (2024, 연결)\n",
             "> 원료(후방) → ODM(제조) → 브랜드(전방) 계층별 수익성·자본효율·신용 비교.\n",
             "| 계층 | 기업 | 매출(억) | 영업이익률 | ROE | 부채비율 | Altman Z' | 매출CAGR 20→24 |",
             "|---|---|--:|--:|--:|--:|--:|--:|"]
    for layer in LAYERS:
        for r in [x for x in rows if x["layer"] == layer]:
            lines.append(f"| {layer} | {r['name']} | {r['revenue']/1e8:,.0f} | "
                         f"{f(r['opm'],'%')} | {f(r['roe'],'%')} | {f(r['debt'],'%')} | "
                         f"{f(r['altman'],'',2)} | {f(r['cagr'],'%')} |")
    # 계층 평균
    lines += ["\n**계층 평균**\n",
              "| 계층 | 영업이익률 | ROE | 부채비율 | Altman Z' | 매출CAGR |",
              "|---|--:|--:|--:|--:|--:|"]
    for layer in LAYERS:
        def avg(key):
            vals = [r[key] for r in rows if r["layer"] == layer and r[key] is not None]
            return sum(vals) / len(vals) if vals else None
        lines.append(f"| {layer} | {f(avg('opm'),'%')} | {f(avg('roe'),'%')} | "
                     f"{f(avg('debt'),'%')} | {f(avg('altman'),'',2)} | {f(avg('cagr'),'%')} |")
    with open(OUTPUT / "key_metrics.md", "a", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    print("[작성] key_metrics.md (밸류체인 비교)")


def main():
    rows = collect()
    save_db(rows)
    chart(rows, "chart12_valuechain.png")
    write_section(rows)
    print("\n=== 계층 평균 영업이익률 / ROE ===")
    for layer in LAYERS:
        o = [r["opm"] for r in rows if r["layer"] == layer and r["opm"] is not None]
        e = [r["roe"] for r in rows if r["layer"] == layer and r["roe"] is not None]
        print(f"  {layer}: 영업이익률 {sum(o)/len(o):.1f}% | ROE {sum(e)/len(e):.1f}%")
    print("\n[완료] chart12 + key_metrics 밸류체인 -> output/")


if __name__ == "__main__":
    main()
