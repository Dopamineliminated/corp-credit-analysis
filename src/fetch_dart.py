# -*- coding: utf-8 -*-
"""DART 전자공시 OpenAPI에서 대상 기업의 재무제표를 내려받아 data/raw/ 에 저장.

사용법:
    # 1) 무료 API 키 발급: https://opendart.fss.or.kr  (인증키 신청/관리)
    # 2) 키를 환경변수 또는 data/.dart_key 파일로 제공
    python src/fetch_dart.py

API 키 우선순위: 환경변수 DART_API_KEY  >  data/.dart_key 파일
"""
import io
import json
import os
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import requests

from config import COMPANIES, YEARS, REPRT_CODE, FS_DIVS, RAW, DATA

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"


def get_api_key():
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        key_file = DATA / ".dart_key"
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(
            "[중단] DART API 키가 없습니다.\n"
            "  1) https://opendart.fss.or.kr 에서 무료 인증키 발급\n"
            "  2) 환경변수 DART_API_KEY 설정  또는  data/.dart_key 파일에 키만 저장\n"
        )
    return key


def load_corp_code_map(key):
    """stock_code -> corp_code 매핑. corpCode.zip을 1회 받아 data/에 캐시."""
    cache = DATA / "corp_codes.csv"
    mapping = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines()[1:]:
            stock, corp, name = (line.split(",") + ["", "", ""])[:3]
            if stock:
                mapping[stock] = (corp, name)
        return mapping

    print("[fetch] 기업 고유번호(corp_code) 목록 다운로드 중...")
    r = requests.get(CORP_CODE_URL, params={"crtfc_key": key}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    root = ET.fromstring(xml_bytes)

    rows = ["stock_code,corp_code,corp_name"]
    for item in root.iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        name = (item.findtext("corp_name") or "").strip()
        if stock:  # 상장사만
            mapping[stock] = (corp, name)
            rows.append(f"{stock},{corp},{name}")
    cache.write_text("\n".join(rows), encoding="utf-8")
    print(f"[fetch] 상장사 {len(mapping)}건 캐시 저장 -> {cache.name}")
    return mapping


def fetch_financials(key, corp_code, year, fs_div):
    params = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": REPRT_CODE,
        "fs_div": fs_div,
    }
    r = requests.get(FS_URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    key = get_api_key()
    code_map = load_corp_code_map(key)

    for comp in COMPANIES:
        stock = comp["stock_code"]
        if stock not in code_map:
            print(f"[경고] {comp['name']}({stock}) corp_code를 찾지 못함. 건너뜀.")
            continue
        corp_code, corp_name = code_map[stock]
        comp["corp_code"] = corp_code
        for year in YEARS:
            for fs_div in FS_DIVS:
                out = RAW / f"{comp['name']}_{year}_{fs_div}.json"
                if out.exists():
                    print(f"[skip] {out.name} (이미 있음)")
                    continue
                print(f"[fetch] {comp['name']} {year}년 {fs_div} 재무제표...")
                data = fetch_financials(key, corp_code, year, fs_div)
                status = data.get("status")
                if status != "000":
                    print(f"        ! status={status} msg={data.get('message')}")
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                               encoding="utf-8")
                time.sleep(0.4)  # API 예의상 간격

    # 대상 기업 corp_code 기록(추적용)
    (DATA / "companies.json").write_text(
        json.dumps(COMPANIES, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[완료] data/raw/ 에 재무제표 JSON 저장 완료.")


if __name__ == "__main__":
    main()
