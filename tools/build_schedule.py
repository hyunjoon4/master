#!/usr/bin/env python3
"""영업 스케줄 CSV(구글 시트 내보내기) -> schedule.json 변환 + 주소 좌표 캐시.

사용법:
    python3 tools/build_schedule.py [CSV경로] [-o schedule.json]

- 기본 CSV 경로: ../../downloads/schedule.csv (워크스페이스 기준 downloads/schedule.csv)
- 좌표는 geocode-cache.json 에 쌓이고, 새 주소만 ArcGIS Geocode API로 조회한다.
"""
import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

YEAR = 2026
KST = timezone(timedelta(hours=9))
SPREADSHEET_ID = "1MaoyT00LPV5iQmlJYvMn8X8ynyYe4GZu50xVP5u5ArQ"
SPREADSHEET_TITLE = "디앤씨 영업부 박현준 차장 스케줄 및 이력등록"

DATE_PATTERNS = [
    re.compile(r"^(?:\d{4}\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일$"),
    re.compile(r"^(?:\d{4}\s*[.\-/]\s*)?(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\.?$"),
]
SKIP_WORDS = ("소화 불가", "소화불가", "불가")


def parse_date(text):
    """'11월 20일' / '11월20일' / '2026. 11. 12' -> '2026-11-20' (연도 없으면 YEAR)."""
    for pattern in DATE_PATTERNS:
        match = pattern.match(text)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return "%04d-%02d-%02d" % (YEAR, month, day)
    return ""


def clean(value):
    return " ".join((value or "").split())


def build_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = [clean(cell) for cell in next(reader)]
        expected = ["날짜", "DB구분", "미팅 시간", "업장명", "지역",
                    "업장번호 및 대표번호", "업장 주소", "특이사항", "진행상황", "이력등록"]
        if header[:10] != expected:
            raise SystemExit("예상과 다른 헤더입니다: %r" % (header,))
        items = []
        skipped = {"empty": 0, "unavailable": 0}
        for index, raw in enumerate(reader, start=2):
            cells = [clean(cell) for cell in raw] + [""] * (10 - len(raw))
            date_text, db, time_text, name, area = cells[:5]
            phone, address, memo, status, history = cells[5:10]
            if not name and not address:
                skipped["empty"] += 1
                continue
            if any(word in name or word in area or word in date_text for word in SKIP_WORDS):
                skipped["unavailable"] += 1
                continue
            date = parse_date(date_text)
            items.append({
                "id": "r%03d" % (len(items) + 1),
                "row": index,
                "date": date,
                "dateLabel": date_text,
                "time": time_text,
                "db": db,
                "name": name,
                "area": area,
                "phone": phone,
                "address": address,
                "memo": memo,
                "status": status,
                "history": history,
            })
    return items, skipped


GEOCODE_URL = ("https://geocode.arcgis.com/arcgis/rest/services/World/"
               "GeocodeServer/findAddressCandidates")
GOOD_TYPES = {"PointAddress", "Subaddress", "StreetAddress", "StreetAddressExt",
              "StreetName", "PostalExt"}


def geocode(query, strict=True):
    params = urllib.parse.urlencode({
        "SingleLine": query, "f": "json", "maxLocations": "3",
        "sourceCountry": "KOR", "outFields": "Addr_type", "forStorage": "false",
    })
    request = urllib.request.Request(GEOCODE_URL + "?" + params,
                                     headers={"User-Agent": "visit-map/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    for candidate in data.get("candidates") or []:
        score = float(candidate.get("score") or 0)
        kind = (candidate.get("attributes") or {}).get("Addr_type", "")
        location = candidate.get("location") or {}
        if strict:
            if score >= 85 and kind in GOOD_TYPES and "x" in location and "y" in location:
                return {"lat": round(location["y"], 6), "lng": round(location["x"], 6),
                        "score": round(score, 2), "type": kind, "matched": candidate.get("address", "")}
        else:
            if score >= 60 and "x" in location and "y" in location:
                return {"lat": round(location["y"], 6), "lng": round(location["x"], 6),
                        "score": round(score, 2), "type": kind, "matched": candidate.get("address", ""),
                        "approx": True}
    return None


def resolve(items, cache_path):
    try:
        with open(cache_path, encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, ValueError):
        cache = {}
    pending = []
    for item in items:
        address = item["address"]
        if address and address not in cache:
            cache[address] = None  # 조회 예정 표시
            pending.append(address)
    pending = sorted(set(pending))
    if pending:
        print("지오코딩 %d건..." % len(pending), file=sys.stderr)

        def work(address):
            try:
                return address, geocode(address, strict=True)
            except Exception as error:  # noqa: BLE001 - 네트워크 오류는 미해결로 남긴다
                print("  실패 %s: %s" % (address, error), file=sys.stderr)
                return address, None

        done = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            for address, point in pool.map(work, pending):
                cache[address] = point
                done += 1
                if done % 25 == 0:
                    print("  %d/%d" % (done, len(pending)), file=sys.stderr)
                    with open(cache_path, "w", encoding="utf-8") as handle:
                        json.dump(cache, handle, ensure_ascii=False, indent=1, sort_keys=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, indent=1, sort_keys=True)
    # 두 번째 시도: 지번(예: '태평2동 422-7')을 떼고 도로/동 단위로 다시 찾는다.
    missing = sorted({item["address"] for item in items
                      if item["address"] and not cache.get(item["address"])})
    if missing:
        print("느슨한 재조회 %d건..." % len(missing), file=sys.stderr)

        def relaxed(address):
            variants = [re.sub(r"\s+\d+(-\d+)?$", "", address),
                        re.sub(r"\s+\d+(-\d+)?\s*$", "", address)]
            for query in variants:
                if query == address or not query:
                    continue
                try:
                    point = geocode(query, strict=False)
                except Exception:  # noqa: BLE001
                    point = None
                if point:
                    point["approx"] = True
                    point["query"] = query
                    return point
            return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            for address, point in zip(missing, pool.map(relaxed, missing)):
                cache[address] = point
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, indent=1, sort_keys=True)
    for item in items:
        point = cache.get(item["address"]) or {}
        if point.get("lat") is not None:
            item["lat"] = point["lat"]
            item["lng"] = point["lng"]
            if point.get("approx"):
                item["geoApprox"] = True
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="downloads/schedule.csv")
    parser.add_argument("-o", "--out", default="schedule.json")
    parser.add_argument("--cache", default="geocode-cache.json")
    parser.add_argument("--no-geocode", action="store_true")
    args = parser.parse_args()

    items, skipped = build_rows(args.csv)
    if not args.no_geocode:
        items = resolve(items, args.cache)
    with_coords = sum(1 for item in items if item.get("lat") is not None)
    payload = {
        "meta": {
            "source": SPREADSHEET_TITLE,
            "spreadsheetId": SPREADSHEET_ID,
            "csv": args.csv.split("/")[-1],
            "generatedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "count": len(items),
            "withCoordinates": with_coords,
            "skipped": skipped,
        },
        "items": items,
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print("%s: %d건 (좌표 %d건, 빈 행 %d, 불가 행 %d)"
          % (args.out, len(items), with_coords, skipped["empty"], skipped["unavailable"]),
          file=sys.stderr)


if __name__ == "__main__":
    main()
