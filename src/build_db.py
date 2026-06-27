# -*- coding: utf-8 -*-
"""data/raw/*.json (DART 재무제표)을 SQLite(output/corp.db)에 적재.

  python src/build_db.py
"""
import json
import sqlite3

from config import (COMPANIES, YEARS, FS_DIVS, DB_PATH, RAW, ROOT,
                    ACCOUNT_MAP, ACCOUNT_ORDER)


def to_number(s):
    """'1,234,567' / '-1,234' / '' -> float | None"""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def pick_account(items, target):
    """라인아이템 목록에서 target 계정의 당기금액을 추출.
    1순위: account_id 일치, 2순위: account_nm 부분일치."""
    ids = set(ACCOUNT_MAP[target]["ids"])
    names = ACCOUNT_MAP[target]["names"]
    # 1순위 account_id
    for it in items:
        if (it.get("account_id") or "").strip() in ids:
            v = to_number(it.get("thstrm_amount"))
            if v is not None:
                return v
    # 2순위 account_nm 부분일치(정확명 우선)
    for exact in (True, False):
        for it in items:
            nm = (it.get("account_nm") or "").strip()
            for cand in names:
                if (nm == cand) if exact else (cand in nm):
                    v = to_number(it.get("thstrm_amount"))
                    if v is not None:
                        return v
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))

    # company 테이블
    comp_meta = {}
    companies_json = RAW.parent / "companies.json"
    if companies_json.exists():
        comp_meta = {c["name"]: c for c in json.loads(companies_json.read_text(encoding="utf-8"))}
    for c in COMPANIES:
        meta = comp_meta.get(c["name"], c)
        cur.execute("INSERT OR REPLACE INTO company VALUES (?,?,?)",
                    (meta.get("corp_code"), c["name"], c["stock_code"]))

    n_raw = n_fin = 0
    for comp in COMPANIES:
        for year in YEARS:
            for basis in FS_DIVS:
                path = RAW / f"{comp['name']}_{year}_{basis}.json"
                if not path.exists():
                    print(f"[경고] {path.name} 없음 — fetch_dart.py 먼저 실행")
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("status") != "000":
                    print(f"[경고] {comp['name']} {year} {basis} "
                          f"status={payload.get('status')} — 건너뜀")
                    continue
                # 요청 시 fs_div로 기준을 지정했으므로 응답 전체가 해당 기준이다.
                items = payload.get("list", [])

                # 원천 라인아이템 적재
                for it in items:
                    cur.execute(
                        "INSERT OR REPLACE INTO fs_raw VALUES (?,?,?,?,?,?,?)",
                        (comp["name"], year, basis, it.get("sj_div"),
                         it.get("account_id"), it.get("account_nm"),
                         to_number(it.get("thstrm_amount"))))
                    n_raw += 1

                # 정제 재무계정 추출
                vals = [pick_account(items, t) for t in ACCOUNT_ORDER]
                cur.execute(
                    "INSERT OR REPLACE INTO financials "
                    "(corp_name, bsns_year, fs_basis, " + ", ".join(ACCOUNT_ORDER) + ") "
                    "VALUES (?,?,?," + ",".join(["?"] * len(ACCOUNT_ORDER)) + ")",
                    [comp["name"], year, basis, *vals])
                n_fin += 1
                print(f"[적재] {comp['name']} {year} {basis}  매출={_fmt(vals[0])}  "
                      f"영업이익={_fmt(vals[3])}  자산={_fmt(vals[5])}")

    conn.commit()
    conn.close()
    print(f"\n[완료] fs_raw {n_raw}행, financials {n_fin}행 -> {DB_PATH.name}")


def _fmt(v):
    if v is None:
        return "N/A"
    return f"{v/1e8:,.0f}억"


if __name__ == "__main__":
    main()
