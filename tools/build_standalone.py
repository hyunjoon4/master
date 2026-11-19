#!/usr/bin/env python3
"""index.html + schedule.json -> standalone.html (데이터 내장 단일 파일).

서버나 깃허브 페이지 없이도 파일 하나만 열면 지도·목록이 뜬다. (스케줄 갱신 시 다시 생성)
"""
import json
import sys

TEMPLATE = "index.html"
DATA = "schedule.json"
OUT = "standalone.html"
MARKER = '<body data-view="map">'


def main():
    html = open(TEMPLATE, encoding="utf-8").read()
    payload = json.load(open(DATA, encoding="utf-8"))
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    block = (MARKER + '\n<script type="application/json" id="inlineSchedule">' + embedded + "</script>")
    if MARKER not in html:
        raise SystemExit("index.html에서 body 태그를 찾지 못했습니다")
    result = html.replace(MARKER, block, 1)
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write(result)
    print("%s: %d건 내장, %.0f KB" % (OUT, len(payload.get("items", [])), len(result) / 1024), file=sys.stderr)


if __name__ == "__main__":
    main()
