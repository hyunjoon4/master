# 방문 일정 지도 (visit-map)

디앤씨 영업부 방문 일정을 **네이버 지도**로 보고, 전화·길찾기까지 한 화면에서 처리하는 모바일 우선 웹앱입니다.
설치 없이 링크만 열면 됩니다. (데이터 출처: 구글 스프레드시트 `디앤씨 영업부 박현준 차장 스케줄 및 이력등록`, 시트1)

## 쓰는 방법

1. 받은 주소(예: `https://hyunjoon4.github.io/visit-map/`)를 휴대폰·PC 브라우저에서 연다.
   - 서버 없이 쓰려면 `standalone.html` 파일 하나만 열어도 됩니다. (일정 데이터가 파일 안에 들어 있음)
2. 날짜를 고르고, 업체를 체크하면 지도에 **1, 2, 3…** 번호 핀이 찍히고 화면이 자동으로 맞춰진다.
3. 카드에서 바로 **📞 전화**, **🧭 네이버 지도**(장소), **🚗 자동차 길찾기**로 넘어간다.

## 화면 구성

| 위치 | 기능 |
| --- | --- |
| 상단 | 오늘 날짜, 설정 버튼, 지도 상태 안내 배너 |
| 날짜 선택 | 기본값은 오늘(오늘 일정이 없으면 가장 가까운 예정일), `전체 날짜`도 선택 가능 |
| 오전/오후 | 전체 · 오전 · 오후 전환 |
| 진행상황 칩 | 대기 / 관리 / 계약완료 / 거절 … 여러 개를 동시에 고를 수 있음 |
| 목록 | 체크박스, 번호 배지, 주소(네이버 지도), 전화, 특이사항(더보기), 이력 |
| 지도 | 번호 핀 + 말풍선(장소·길찾기 링크), `◎` 내 위치, `⤢` 선택한 곳 모두 보기 |
| 설정 | 네이버 지도 키, 지도 종류(네이버/오픈스트리트맵), 일정 데이터(시트 CSV 주소·CSV 파일·새로고침) |

모바일에서는 아래쪽 **지도 / 목록** 탭으로 화면을 전환합니다. PC에서는 목록과 지도가 나란히 보입니다.

## 네이버 지도 키 넣기 (한 번만)

지도 화면 자체를 네이버 지도로 띄우려면 네이버 클라우드 플랫폼 키(`ncpKeyId`)가 필요합니다.
키가 없어도 오픈스트리트맵 지도로 계속 쓸 수 있고, 주소·전화·길찾기 버튼은 키와 상관없이 네이버 지도로 열립니다.

1. <https://console.ncloud.com> → **Application Services → Maps → Application 등록**
2. API 선택에서 **Dynamic Map** 체크
3. **Web 서비스 URL** 에 이 앱의 주소를 넣는다 — `https://hyunjoon4.github.io/visit-map/`
   (로컬 파일로 열 때는 `file://` 경로를 넣거나 키 없이 오픈스트리트맵으로 쓰면 됩니다.)
4. 발급된 **Client ID** 를 앱의 **⚙ 설정 → 네이버 지도 키** 에 붙여 넣고 저장, 또는 주소 끝에 `?key=발급받은ID` 로 한 번 열면 자동 저장됩니다.

## 일정 갱신

원본은 구글 시트입니다. 시트를 고친 뒤 아래처럼 내보내고 `schedule.json` 을 다시 만들면 됩니다.

```bash
# 1) 최신 시트 CSV 내려받기 (워크스페이스 기준)
gog --readonly sheets export 1MaoyT00LPV5iQmlJYvMn8X8ynyYe4GZu50xVP5u5ArQ --format csv --out downloads/schedule.csv

# 2) schedule.json + standalone.html 다시 만들기 (주소 → 좌표는 캐시 사용)
python3 tools/build_schedule.py ../../downloads/schedule.csv -o schedule.json --cache geocode-cache.json
python3 tools/build_standalone.py
```

- `geocode-cache.json` 에 주소별 좌표가 쌓입니다. 새 주소만 ArcGIS Geocode API로 조회합니다.
- 좌표를 못 찾은 주소는 앱이 켜질 때 한 번 더 시도하고, 그래도 안 되면 "주소 확인 필요" 로 알려 줍니다.
- 시트 주소를 공개(링크 있는 모든 사용자 보기)해 두면 앱 안에서 시트 CSV 주소를 넣어 실시간에 가깝게 읽을 수도 있습니다.
  (⚙ 설정 → 일정 데이터 → `https://docs.google.com/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=시트1`)

## 파일

| 파일 | 설명 |
| --- | --- |
| `index.html` | 앱 본체 (지도·목록·필터·설정). 데이터는 `schedule.json` 에서 읽음 |
| `schedule.json` | 시트를 변환한 일정 + 미리 계산한 좌표(`lat`, `lng`) |
| `standalone.html` | 데이터까지 한 파일에 넣은 버전 (서버 없이 열기용) |
| `geocode-cache.json` | 주소 → 좌표 캐시 (앱에서는 안 읽음, 빌드용) |
| `tools/build_schedule.py` | CSV → `schedule.json` |
| `tools/build_standalone.py` | `index.html` + `schedule.json` → `standalone.html` |
| `tools/check_page.py` | 페이지를 실제로 실행해 보는 자체 검사 (quickjs + esprima) |

## 주의

- 이 저장소와 깃허브 페이지를 **공개(public)** 로 두면 업체명·전화번호·주소·통화 메모가 링크를 아는 사람에게 보입니다.
  `index.html` 에 검색 차단(`noindex, nofollow`)을 넣어 두었지만, 완전한 보호는 아닙니다.
  필요하면 ① 깃허브 Pro에서 비공개 저장소 + Pages, ② 일정에서 전화번호·메모를 빼고 쓰기, ③ 링크를 본인만 보관하는 방법 중에서 고르세요.

## 배포 (저장소가 아직 없을 때)

```bash
gh repo create visit-map --public --source=. --remote=origin --push
gh api -X POST repos/hyunjoon4/visit-map/pages -f 'source[branch]=main' -f 'source[path]=/'
```
