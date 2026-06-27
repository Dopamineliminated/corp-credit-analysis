# -*- coding: utf-8 -*-
"""sql/queries.sql 의 분석 쿼리들을 순서대로 실행해 콘솔에 출력.

  python src/run_sql.py
"""
import re
import sqlite3

from config import DB_PATH, ROOT


def split_named_queries(sql_text):
    """'-- name: ...' 주석 기준으로 (제목, 쿼리) 목록 생성."""
    parts = re.split(r"(?m)^--\s*name:\s*(.+)$", sql_text)
    # parts[0]은 머리말, 이후 (title, body) 반복
    pairs = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip().rstrip(";").strip()
        if body:
            pairs.append((title, body))
    return pairs


def print_table(cols, rows):
    widths = [len(str(c)) for c in cols]
    for r in rows:
        for j, v in enumerate(r):
            widths[j] = max(widths[j], len(_s(v)))
    line = " | ".join(str(c).ljust(widths[j]) for j, c in enumerate(cols))
    print(line)
    print("-" * len(line))
    for r in rows:
        print(" | ".join(_s(v).ljust(widths[j]) for j, v in enumerate(r)))


def _s(v):
    if v is None:
        return "-"
    return str(v)


def main():
    queries = split_named_queries((ROOT / "sql" / "queries.sql").read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for title, body in queries:
        print("\n" + "=" * 70)
        print(f"■ {title}")
        print("=" * 70)
        try:
            cur.execute(body)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            print_table(cols, rows)
        except Exception as e:
            print(f"[쿼리 오류] {e}")
    conn.close()


if __name__ == "__main__":
    main()
