#!/usr/bin/env python3
"""index.html 을 DOM 스텁 위에서 실제로 실행해 보는 검사 스크립트.

외부 의존성 없이 quickjs(pip install quickjs)만 있으면 돌아간다.
- 스크립트 문법 검사
- schedule.json 로드 → 날짜 기본값/필터/카드 렌더
- 체크 → 번호 핀 생성/지도 맞춤
- CSV(구글 시트 형식) 불러오기 → 174건 파싱
- 네이버 지도 키 경로

사용법: python3 tools/check_page.py [--csv ../../downloads/schedule.csv]
"""
import argparse
import json
import re
import sys

import esprima
import quickjs

PRELUDE = r"""
'use strict';
var __log = [];
var __timers = [];
function setTimeout(fn, ms){ __timers.push(fn); return __timers.length; }
function clearTimeout(id){}
function __flush(){
  var guard = 0;
  while (__timers.length && guard++ < 500) { var fn = __timers.shift(); fn(); }
}

function URLSearchParams(init){
  this.map = {};
  if (init) for (var k in init) if (Object.prototype.hasOwnProperty.call(init, k)) this.map[k] = String(init[k]);
}
URLSearchParams.prototype.get = function(k){ return Object.prototype.hasOwnProperty.call(this.map, k) ? this.map[k] : null; };
URLSearchParams.prototype.set = function(k, v){ this.map[k] = String(v); };
URLSearchParams.prototype.delete = function(k){ delete this.map[k]; };
URLSearchParams.prototype.toString = function(){
  var out = [];
  for (var k in this.map) if (Object.prototype.hasOwnProperty.call(this.map, k)) out.push(encodeURIComponent(k) + '=' + encodeURIComponent(this.map[k]));
  return out.join('&');
};
function URL(href){
  this.href = String(href);
  var hashAt = this.href.indexOf('#');
  this.hash = hashAt >= 0 ? this.href.slice(hashAt) : '';
  var withoutHash = hashAt >= 0 ? this.href.slice(0, hashAt) : this.href;
  var q = withoutHash.indexOf('?');
  this.search = q >= 0 ? withoutHash.slice(q) : '';
  this.pathname = q >= 0 ? withoutHash.slice(0, q) : withoutHash;
  var params = new URLSearchParams();
  if (this.search) {
    this.search.slice(1).split('&').forEach(function(pair){
      if (!pair) return;
      var eq = pair.indexOf('=');
      var key = eq >= 0 ? pair.slice(0, eq) : pair;
      var value = eq >= 0 ? pair.slice(eq + 1) : '';
      params.set(key, value);
    });
  }
  this.searchParams = params;
}

function ClassList(node){ this.node = node; this.set = {}; }
ClassList.prototype.add = function(name){ this.set[name] = true; };
ClassList.prototype.remove = function(name){ delete this.set[name]; };
ClassList.prototype.contains = function(name){ return !!this.set[name]; };
ClassList.prototype.toggle = function(name, force){
  var on = force === undefined ? !this.set[name] : !!force;
  if (on) this.set[name] = true; else delete this.set[name];
  return on;
};

function Element(tag){
  this.tagName = String(tag || 'div').toUpperCase();
  this.children = [];
  this.attributes = {};
  this.dataset = {};
  this.style = {};
  this.classList = new ClassList(this);
  this.className = '';
  this.textContent = '';
  this.hidden = false;
  this.disabled = false;
  this.value = '';
  this.files = null;
  this.listeners = {};
  this.parentNode = null;
}
Element.prototype.appendChild = function(node){ node.parentNode = this; this.children.push(node); return node; };
Element.prototype.append = function(){ for (var i = 0; i < arguments.length; i++) if (arguments[i] != null) this.appendChild(arguments[i]); };
Element.prototype.replaceChildren = function(){ this.children = []; this.append.apply(this, arguments); };
Element.prototype.removeChild = function(node){
  var index = this.children.indexOf(node);
  if (index >= 0) this.children.splice(index, 1);
};
Element.prototype.setAttribute = function(name, value){
  this.attributes[name] = String(value);
  if (name === 'class') this.className = String(value);
  if (name.indexOf('data-') === 0) this.dataset[name.slice(5)] = String(value);
};
Element.prototype.getAttribute = function(name){
  if (name === 'class') return this.className;
  if (name.indexOf('data-') === 0) {
    var key = name.slice(5);
    return Object.prototype.hasOwnProperty.call(this.dataset, key) ? String(this.dataset[key]) : null;
  }
  return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
};
Element.prototype.hasAttribute = function(name){ return this.getAttribute(name) != null; };
Element.prototype.removeAttribute = function(name){ delete this.attributes[name]; };
Element.prototype.addEventListener = function(type, handler){
  if (!this.listeners[type]) this.listeners[type] = [];
  this.listeners[type].push(handler);
};
Element.prototype.dispatch = function(type, event){
  var handlers = this.listeners[type] || [];
  for (var i = 0; i < handlers.length; i++) handlers[i](event || { target: this });
  var inline = this['on' + type];
  if (typeof inline === 'function') inline(event || { target: this });
};
Element.prototype.focus = function(){};
Element.prototype.queryAll = function(predicate, out){
  out = out || [];
  var children = this.children || [];
  for (var i = 0; i < children.length; i++) {
    var child = children[i];
    if (child instanceof Element && predicate(child)) out.push(child);
    if (child.queryAll) child.queryAll(predicate, out);
  }
  return out;
};
Element.prototype.querySelectorAll = function(selector){
  if (selector === 'img') return this.queryAll(function(n){ return n.tagName === 'IMG'; });
  if (selector === 'canvas') return this.queryAll(function(n){ return n.tagName === 'CANVAS'; });
  if (selector === 'button') return this.queryAll(function(n){ return n.tagName === 'BUTTON'; });
  if (selector === '[data-badge]') return this.queryAll(function(n){ return n.getAttribute('data-badge') != null; });
  return [];
};

function TextNode(text){ this.textContent = String(text); this.children = []; this.tagName = '#text'; }

var __elements = {};
function __register(id, tag){
  var node = new Element(tag || 'div');
  node.id = id;
  __elements[id] = node;
  return node;
}
var document = {
  readyState: 'complete',
  title: '방문 일정 지도',
  body: __register('__body', 'body'),
  head: __register('__head', 'head'),
  getElementById: function(id){
    if (!__elements[id]) __register(id);
    return __elements[id];
  },
  createElement: function(tag){ return new Element(tag); },
  createTextNode: function(text){ return new TextNode(text); },
  addEventListener: function(){},
  querySelectorAll: function(selector){
    var out = [];
    for (var id in __elements) {
      if (!Object.prototype.hasOwnProperty.call(__elements, id)) continue;
      var found = __elements[id].querySelectorAll ? __elements[id].querySelectorAll(selector) : [];
      for (var i = 0; i < found.length; i++) if (out.indexOf(found[i]) < 0) out.push(found[i]);
    }
    return out;
  }
};
['dateSelect','period','statusChips','counter','listHead','selectAll','clearAll','cards','map',
 'mapFallback','locateButton','fitButton','mapStatus','tabMap','tabList','listCount','settings',
 'settingsButton','settingsClose','keyInput','keySave','keyClear','engineNaver','engineOsm','engineNote',
 'dataNote','sheetUrl','sheetLoad','csvFile','refreshData','resetData','dataStatus','todayLabel',
 'mapBanner','mapBannerText','mapBannerAction','mapBannerClose','listPanel','mapPanel','mapTools'].forEach(function(id){
  __register(id);
});
// 실제 index.html 의 정적 버튼들을 스텁에도 만들어 둔다
(function(){
  var period = document.getElementById('period');
  ['', '오전', '오후'].forEach(function(value){
    var button = new Element('button');
    button.type = 'button';
    button.value = value;
    button.setAttribute('aria-pressed', value === '' ? 'true' : 'false');
    period.append(button);
  });
})();

var __storage = {};
var localStorage = {
  getItem: function(key){ return Object.prototype.hasOwnProperty.call(__storage, key) ? __storage[key] : null; },
  setItem: function(key, value){ __storage[key] = String(value); },
  removeItem: function(key){ delete __storage[key]; }
};

var __fetchLog = [];
var __csvText = null;
var __schedulePayload = null;
function fetch(url, options){
  __fetchLog.push(String(url));
  var target = String(url);
  if (target.indexOf('schedule.json') === 0) {
    if (!__schedulePayload) return Promise.reject(new Error('no schedule'));
    return Promise.resolve({ ok: true, status: 200, json: function(){ return Promise.resolve(JSON.parse(__schedulePayload)); }, text: function(){ return Promise.resolve(__schedulePayload); } });
  }
  if (target.indexOf('test://csv') === 0) {
    return Promise.resolve({ ok: true, status: 200, text: function(){ return Promise.resolve(__csvText); }, json: function(){ return Promise.reject(new Error('n/a')); } });
  }
  if (target.indexOf('geocode.arcgis.com') >= 0) {
    var decoded = decodeURIComponent(target);
    if (decoded.indexOf('당진') >= 0) {
      return Promise.resolve({ ok: true, json: function(){ return Promise.resolve({ candidates: [{ score: 99, attributes: { Addr_type: 'PointAddress' }, location: { x: 126.63, y: 36.89 } }] }); } });
    }
    return Promise.resolve({ ok: true, json: function(){ return Promise.resolve({ candidates: [] }); } });
  }
  return Promise.resolve({ ok: false, status: 404, text: function(){ return Promise.resolve('not found'); } });
}

var navigator = { geolocation: { getCurrentPosition: function(ok){ ok({ coords: { latitude: 36.0, longitude: 126.7, accuracy: 20 } }); } } };
function FileReader(){}
FileReader.prototype.readAsText = function(){};

var window = {
  innerWidth: 390,
  location: { href: 'https://hyunjoon4.github.io/visit-map/', search: '', hash: '' },
  history: { replaceState: function(a, b, url){ window.__replacedUrl = url; } },
  addEventListener: function(){},
  L: null,
  naver: null
};

// ── 테스트용 가짜 지도 엔진 ─────────────────────────────
var __markers = [];
var __fits = [];
function makeFakeLeaflet(){
  function View(){ this.zoom = 7; this.layers = []; }
  View.prototype.setView = function(center, zoom){ this.center = center; this.zoom = zoom; __fits.push({ kind: 'setView', center: center, zoom: zoom }); return this; };
  View.prototype.invalidateSize = function(){};
  View.prototype.fitBounds = function(bounds, options){ __fits.push({ kind: 'bounds', points: bounds.points, options: options }); };
  View.prototype.addLayer = function(layer){ this.layers.push(layer); };
  View.prototype.removeLayer = function(layer){ var i = this.layers.indexOf(layer); if (i >= 0) this.layers.splice(i, 1); };
  return {
    map: function(id){ var view = new View(); window.__lastView = view; return view; },
    tileLayer: function(){ return { addTo: function(view){ return this; } }; },
    divIcon: function(options){ return options; },
    marker: function(latlng, options){
      var marker = {
        latlng: latlng, options: options,
        addTo: function(view){ this.view = view; view.layers.push(this); return this; },
        bindPopup: function(html){ this.popup = html; return this; }
      };
      __markers.push(marker);
      return marker;
    },
    latLngBounds: function(points){ return { points: points }; }
  };
}

function makeFakeNaver(){
  var maps = {};
  maps.LatLng = function(lat, lng){ this.lat = lat; this.lng = lng; };
  maps.Point = function(x, y){ this.x = x; this.y = y; };
  maps.Position = { BOTTOM_LEFT: 0, RIGHT_CENTER: 3 };
  maps.LatLngBounds = function(){ this.points = []; var self = this; this.extend = function(p){ self.points.push(p); }; };
  maps.Event = { addListener: function(marker, type, fn){ marker.__click = fn; } };
  maps.Map = function(container, options){
    container.appendChild(new Element('img'));  // 타일이 그려진 것처럼
    this.options = options;
    this.map = this;
  };
  maps.Map.prototype.setCenter = function(){};
  maps.Map.prototype.setZoom = function(){};
  maps.Map.prototype.getZoom = function(){ return 12; };
  maps.Map.prototype.fitBounds = function(bounds, padding){ __fits.push({ kind: 'naver', count: bounds.points.length, padding: padding }); };
  maps.Map.prototype.refresh = function(){};
  maps.Marker = function(options){
    this.options = options;
    __markers.push(this);
  };
  maps.Marker.prototype.setMap = function(){};
  maps.InfoWindow = function(){ this.open = function(){ this.opened = true; }; this.close = function(){}; this.setContent = function(html){ this.content = html; }; };
  return { maps: maps };
}

function __setKeyHref(key){
  window.location.href = 'https://hyunjoon4.github.io/visit-map/?key=' + key;
}
function __cards(){ return document.getElementById('cards'); }
function __articles(){ return __cards().queryAll(function(n){ return n.tagName === 'ARTICLE'; }); }
function __text(node){ return node ? node.textContent : null; }
function __drain(){}
"""


def run(page_html, schedule_json, csv_text, key, expect_naver, workdir, inline_json=None, storage=None):
    scripts = re.findall(r"<script>(.*?)</script>", page_html, re.S)
    assert len(scripts) == 1, "예상과 다른 script 블록 수: %d" % len(scripts)
    body = scripts[0]
    esprima.parseScript(body)  # 문법 검사

    ctx = quickjs.Context()
    ctx.set_time_limit(60)
    ctx.eval(PRELUDE)
    ctx.set("__schedulePayload", schedule_json)
    ctx.set("__csvText", csv_text)
    ctx.eval("window.L = makeFakeLeaflet(); window.naver = %s;" % ("makeFakeNaver()" if expect_naver else "null"))
    ctx.eval("window.L = makeFakeLeaflet();" if not expect_naver else "")
    if storage:
        ctx.set("__storageInit", json.dumps(storage))
        ctx.eval("var __init = JSON.parse(__storageInit); for (var k in __init) if (Object.prototype.hasOwnProperty.call(__init, k)) __storage[k] = __init[k];")
    if key:
        ctx.set("__keyValue", key)
        ctx.eval("__setKeyHref(__keyValue);")
    if inline_json:
        ctx.set("__inlineJson", inline_json)
        ctx.eval("document.getElementById('inlineSchedule').textContent = __inlineJson;")

    # 앱 실행
    ctx.eval(body)

    def drain(rounds=40):
        for _ in range(rounds):
            ctx.eval("__flush();")
            while True:
                r = ctx.execute_pending_job()
                if not r:
                    break

    drain()
    return ctx, drain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", default="index.html")
    parser.add_argument("--data", default="schedule.json")
    parser.add_argument("--csv", default="../../downloads/schedule.csv")
    args = parser.parse_args()

    page = open(args.page, encoding="utf-8").read()
    schedule_json = open(args.data, encoding="utf-8").read()
    csv_text = open(args.csv, encoding="utf-8").read()
    payload = json.loads(schedule_json)

    def j(ctx_, expr):
        return json.loads(ctx_.eval("JSON.stringify(%s)" % expr))

    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail and not ok else ""))

    # ── 0. 저장된 키 없음: 내장 기본 키(ncpKeyId)로 네이버 지도 시도 ──
    ctx_default, drain_default = run(page, schedule_json, csv_text, "", False, ".")
    defaultInfo = j(ctx_default, "({key: (function(){ return __storage['visitmap.naverKey'] == null ? null : __storage['visitmap.naverKey']; })(), "
                             "naverSrc: (function(){ var out = ''; document.head.queryAll(function(n){ if (n.tagName === 'SCRIPT' && String(n.src || '').indexOf('oapi.map.naver.com') >= 0) out = String(n.src); return false; }); return out; })()})")
    check("키를 저장한 적 없으면 기본 키 사용", "ncpKeyId=v2wsje7uvd" in (defaultInfo["naverSrc"] or ""), defaultInfo)
    check("기본 키 상태에서도 지도 오류 화면 없음",
          j(ctx_default, "document.getElementById('mapFallback').hidden") is True, defaultInfo)

    # ── 1. 키를 지운 상태('' 저장): OSM 폴백 경로 ────────
    ctx, drain = run(page, schedule_json, csv_text, "", False, ".", storage={"visitmap.naverKey": ""})
    result = j(ctx, "({counter: __text(document.getElementById('counter')), "
                      "cards: __articles().length, "
                      "options: document.getElementById('dateSelect').children.length, "
                      "selected: document.getElementById('dateSelect').value, "
                      "listHead: __text(document.getElementById('listHead')), "
                      "chips: document.getElementById('statusChips').children.length, "
                      "banner: __text(document.getElementById('mapBannerText')), "
                      "bannerHidden: document.getElementById('mapBanner').hidden, "
                      "status: __text(document.getElementById('mapStatus')), "
                      "engineNote: __text(document.getElementById('engineNote')), "
                      "fallbackHidden: document.getElementById('mapFallback').hidden, "
                      "slots: Object.keys(__fetchLog)})")
    info = result
    dates = sorted({item["date"] for item in payload["items"] if item.get("date")})
    today_items = [i for i in payload["items"] if i.get("date") == "2026-11-20"]
    check("OSM 폴백에서 지도 오류 화면이 뜨지 않음", info["fallbackHidden"] is True, info)
    check("일정 카드 렌더", info["cards"] == len(today_items), "%s vs %s" % (info["cards"], len(today_items)))
    check("날짜 옵션 = 전체 + 날짜수", info["options"] == len(dates) + 1, info["options"])
    check("기본 선택은 오늘(2026-11-20)", info["selected"] == "2026-11-20", info["selected"])
    check("상태 칩 생성", info["chips"] >= 3, info["chips"])
    check("키를 지우면 OSM + 키 안내 배너", info["bannerHidden"] is False and "키" in (info["banner"] or ""), info["banner"])

    # ── 2. 체크 → 번호 핀 ──────────────────────────────
    ctx.eval("""
      var cards = __articles();
      var boxes = [];
      cards.forEach(function(card){ card.queryAll(function(n){ return n.tagName === 'INPUT'; }).forEach(function(b){ boxes.push(b); }); });
      __boxes = boxes;
      boxes[0].checked = true; boxes[0].onchange();
    """)
    drain()
    selected = j(ctx, "({markers: window.__lastView.layers.length, fits: __fits.length, status: __text(document.getElementById('mapStatus')), badge: (function(){ var b = document.querySelectorAll('[data-badge]')[0]; return b.textContent + '/' + b.hidden; })()})")
    check("1건 체크 → 마커 1개", selected["markers"] == 1, selected)
    check("1건 체크 → 지도 맞춤 호출", selected["fits"] >= 1, selected)
    check("번호 배지 표시", selected["badge"] == "1/false", selected["badge"])
    check("지도 상태 문구", "1곳" in (selected["status"] or ""), selected["status"])

    # ── 3. 두 번째 항목까지 체크 → 번호 1,2 ─────────────
    ctx.eval("""
      var cards2 = __articles();
      var boxes2 = [];
      cards2.forEach(function(card){ card.queryAll(function(n){ return n.tagName === 'INPUT'; }).forEach(function(b){ boxes2.push(b); }); });
      boxes2[1].checked = true; boxes2[1].onchange();
    """)
    drain()
    two = j(ctx, "({markers: window.__lastView.layers.length, badges: (function(){ var out = []; document.querySelectorAll('[data-badge]').forEach(function(b){ if (!b.hidden) out.push(b.textContent); }); return out.join(','); })()})")
    check("2건 체크 → 마커 2개", two["markers"] == 2, two)
    check("번호 1,2 부여", two["badges"] == "1,2", two["badges"])

    # ── 4. 전체 날짜 / 오전·오후 필터 ───────────────────
    ctx.eval("""
      var period = document.getElementById('period');
      var sel = document.getElementById('dateSelect');
      sel.value = ''; sel.dispatch('change', { target: sel });
      __allCards = __articles().length;
      var afternoon = period.children[2];
      afternoon.dispatch('click');
      __afternoonCards = __articles().length;
      var counterText = __text(document.getElementById('counter'));
    """)
    filtered = j(ctx, "({all: __allCards, afternoon: __afternoonCards, counter: __text(document.getElementById('counter')), total: %d})" % len(payload["items"]))
    check("전체 날짜 선택 시 모든 일정", filtered["all"] == filtered["total"], filtered)
    check("오후 필터가 목록을 줄임", 0 < filtered["afternoon"] < filtered["all"], filtered)

    # ── 5. CSV 불러오기 ───────────────────────────────
    ctx.eval("""
      var url = document.getElementById('sheetUrl');
      url.value = 'test://csv';
      document.getElementById('sheetLoad').dispatch('click');
    """)
    drain()
    csv_state = j(ctx, "({cards: __articles().length, counter: __text(document.getElementById('counter')), status: __text(document.getElementById('dataStatus')), options: document.getElementById('dateSelect').children.length})")
    check("CSV 파싱 174건", "174건" in (csv_state["status"] or ""), csv_state)
    check("CSV 로드 후 카드 렌더", csv_state["cards"] > 0, csv_state)

    # ── 6. 네이버 키 경로 ─────────────────────────────
    ctx2, drain2 = run(page, schedule_json, csv_text, "testkey123", True, ".")
    naver_state = j(ctx2, "({markers: __markers.length, engine: __text(document.getElementById('engineNote')), status: __text(document.getElementById('mapStatus')), fallback: document.getElementById('mapFallback').hidden, banner: document.getElementById('mapBanner').hidden, replaced: window.__replacedUrl, scripts: Object.keys(__fetchLog).length})")
    check("네이버 엔진 선택됨", "네이버" in (naver_state["engine"] or ""), naver_state)
    check("네이버 지도에서 오류 화면 없음", naver_state["fallback"] is True, naver_state)
    check("키 URL 파라미터 제거", (naver_state["replaced"] or "").find("key=") < 0, naver_state["replaced"])

    # ── 7. standalone.html (데이터 내장, fetch 없이) ────
    inline = json.loads(open("standalone.html", encoding="utf-8").read().split('id="inlineSchedule">')[1].split("</script>")[0].replace("<\\/", "</"))
    inline_text = json.dumps(inline)
    standalone = open("standalone.html", encoding="utf-8").read()
    ctx3, drain3 = run(standalone, "", csv_text, "", False, ".", inline_json=inline_text)
    single = j(ctx3, "({cards: __articles().length, counter: __text(document.getElementById('counter')), status: __text(document.getElementById('dataStatus')), total: %d})" % len(inline["items"]))
    check("standalone: 내장 데이터로 렌더", single["cards"] == len([i for i in inline["items"] if i.get("date") == "2026-11-20"]), single)
    check("standalone: 내장 데이터 안내", "내장" in (single["status"] or ""), single["status"])

    failed = [name for name, ok, _ in checks if not ok]
    print()
    print("%d/%d 통과" % (len(checks) - len(failed), len(checks)))
    if failed:
        print("실패:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
