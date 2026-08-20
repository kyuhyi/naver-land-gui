#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
naver_land.py — 네이버 부동산 매물 조회기 (엔진)

GUI(app.py)가 이 파일의 NaverLand 클래스와 헬퍼 함수를 그대로 씁니다.
터미널에서 단독 실행도 가능합니다.


═══════════════════════════════════════════════════════════════
■ 원리 — 왜 requests 로는 안 되고 이렇게 해야 하는가
═══════════════════════════════════════════════════════════════

네이버 부동산의 매물 목록은 화면 주소(URL)로 오지 않습니다.
페이지가 열린 뒤 자바스크립트가 별도의 API를 POST 로 호출해서 받아옵니다.

    POST https://fin.land.naver.com/front-api/v1/complex/article/list
    body: {"complexNumber": 8742, "tradeTypes": ["A1"], "size": 30, ...}

이 API 는 Authorization 토큰을 쓰지 않습니다. 대신 세 가지를 봅니다.

    1) 국내 IP 인가       — 해외·데이터센터 IP 는 응답을 아예 주지 않습니다
    2) 쿠키가 있는가      — NAC / NACT
    3) 진짜 브라우저인가  — 헤더뿐 아니라 TLS 접속 지문까지 봅니다

그래서 이 스크립트는 흉내내기를 포기합니다.
대신 진짜 크롬을 띄우고, 그 페이지 안에서 fetch() 를 실행시킵니다.

    파이썬 ──(CDP)──▶ 진짜 크롬 ──(fetch)──▶ 네이버 API


═══════════════════════════════════════════════════════════════
■ 준비물
═══════════════════════════════════════════════════════════════

  1) 구글 크롬 설치
  2) pip install playwright   (playwright install 은 필요 없음)
  3) 국내에서 실행


═══════════════════════════════════════════════════════════════
■ 코드
═══════════════════════════════════════════════════════════════

  거래유형 tradeTypes      : A1=매매  B1=전세  B2=월세  B3=단기
  매물종류 realEstateTypes : A01=아파트  A04=주상복합 등  B01=오피스텔


═══════════════════════════════════════════════════════════════
■ 주의
═══════════════════════════════════════════════════════════════

  · 개인적인 열람 목적으로만 쓰세요.
  · 요청 사이 간격(POLITE_DELAY, 기본 0.8초)을 줄이지 마세요.
  · 수집한 자료를 그대로 재배포하지 마세요.
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request

# ──────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────
CDP_PORT = 9222
CDP_URL = "http://127.0.0.1:%d" % CDP_PORT
PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".naver_land_profile")
POLITE_DELAY = 0.8          # 요청 사이 최소 간격(초) — 줄이지 마세요
BASE = "https://fin.land.naver.com"

TRADE_NAME = {"A1": "매매", "B1": "전세", "B2": "월세", "B3": "단기"}
DIRECTION = {"SS": "남", "EE": "동", "WW": "서", "NN": "북",
             "SE": "남동", "SW": "남서", "NE": "북동", "NW": "북서",
             "ES": "동남", "WS": "서남", "EN": "동북", "WN": "서북"}


# ──────────────────────────────────────────────────────────────
# 크롬 띄우기 / 붙기
# ──────────────────────────────────────────────────────────────
def find_chrome():
    """OS별 크롬 실행파일을 찾는다. CHROME_PATH 환경변수가 있으면 그것을 쓴다."""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env

    system = platform.system()
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser(
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium", "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def cdp_alive():
    try:
        urllib.request.urlopen(CDP_URL + "/json/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_chrome(headless=False):
    """CDP 포트가 열린 크롬을 확보한다. 이미 떠 있으면 그대로 쓴다."""
    if cdp_alive():
        return

    chrome = find_chrome()
    if not chrome:
        raise RuntimeError(
            "구글 크롬을 찾지 못했습니다.\n"
            "크롬을 설치하거나, 환경변수 CHROME_PATH 에 실행파일 경로를 넣어 주세요.")

    args = [
        chrome,
        "--remote-debugging-port=%d" % CDP_PORT,
        "--user-data-dir=" + PROFILE_DIR,      # 평소 쓰는 프로필과 분리
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "about:blank",
    ]
    if headless:
        args.insert(1, "--headless=new")

    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if platform.system() == "Windows":
        kwargs["creationflags"] = 0x08000000        # CREATE_NO_WINDOW
    subprocess.Popen(args, **kwargs)

    for _ in range(40):
        time.sleep(1)
        if cdp_alive():
            return
    raise RuntimeError("크롬 원격 디버깅 포트(%d)가 열리지 않았습니다.\n"
                       "다른 프로그램이 그 포트를 쓰고 있는지 확인해 주세요." % CDP_PORT)


# ──────────────────────────────────────────────────────────────
# 조회기
# ──────────────────────────────────────────────────────────────
# 페이지 안에서 실행될 자바스크립트.
# credentials:'include' 라서 그 페이지의 쿠키가 자동으로 실린다.
_FETCH_JS = """
async ([path, method, body]) => {
  const opt = { method: method, credentials: 'include' };
  if (body) {
    opt.headers = { 'content-type': 'application/json' };
    opt.body = JSON.stringify(body);
  }
  const res = await fetch(path, opt);
  return { status: res.status, text: await res.text() };
}
"""


def _filter(trade_types, estate_types):
    """지도·단지 검색에 쓰는 기본 필터. 네이버 화면의 기본값과 같다."""
    return {
        "tradeTypes": list(trade_types),
        "realEstateTypes": list(estate_types),
        "roomCount": [], "bathRoomCount": [], "optionTypes": [],
        "oneRoomShapeTypes": [], "moveInTypes": [],
        "filtersExclusiveSpace": False, "floorTypes": [],
        "directionTypes": [], "hasArticlePhoto": False,
        "isAuthorizedByOwner": False, "parkingTypes": [],
        "entranceTypes": [], "hasArticle": False,
    }


class NaverLand:
    """실제 크롬 페이지 안에서 네이버 부동산 API를 호출한다."""

    def __init__(self, headless=False, quiet=False):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "playwright 가 없습니다.  pip install playwright  후 다시 실행하세요.\n"
                "('playwright install' 은 하지 않아도 됩니다.)")

        ensure_chrome(headless=headless)
        self.quiet = quiet
        self._pw = sync_playwright().start()
        browser = self._pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        self.page = ctx.new_page()
        # 쿠키(NAC/NACT)를 받기 위해 먼저 사이트를 연다.
        self.page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

    def log(self, *a):
        if not self.quiet:
            print(*a, flush=True)

    def sleep(self, seconds):
        """요청 사이 간격. GUI 는 취소에 반응하도록 이 메서드를 덮어쓴다."""
        time.sleep(seconds)

    def call(self, path, method="GET", body=None):
        res = self.page.evaluate(_FETCH_JS, [path, method, body])
        self.sleep(POLITE_DELAY)                 # 사람 속도 — 줄이지 마세요
        if res["status"] != 200:
            raise RuntimeError("HTTP %s — %s" % (res["status"], path))
        return json.loads(res["text"])

    # ── 지역 이름 → 좌표 ─────────────────────────────────────
    def find_region(self, query):
        """'서울시 양천구 신정동' 또는 '신정동' → 그 동의 좌표를 찾는다."""
        words = query.split()
        cities = self.call(
            "/front-api/v1/legalDivision/infoListByLevel?regionLevelType=SI")["result"]

        # 시/도 고르기 — 질의에 시 이름이 들어 있으면 그것, 없으면 전부 훑는다
        picked = [c for c in cities
                  if any(w[:2] in c["legalDivisionName"] for w in words)]
        if not picked:
            picked = cities

        hits = []
        for city in picked:
            dongs = self.call(
                "/front-api/v1/legalDivision/infoListByLevel"
                "?regionLevelType=EUP&legalDivisionNumber=%s"
                % city["legalDivisionNumber"])["result"]
            for d in dongs:
                full = d.get("fullAddress") or d.get("legalDivisionName") or ""
                if all(w in full for w in words):
                    hits.append(d)
            if hits:
                break
        return hits

    # ── 단지 기본정보 ────────────────────────────────────────
    def complex_info(self, complex_no):
        d = self.call("/front-api/v1/complex/mapComplexSummaryInfo"
                      "?complexNumber=%s" % complex_no)
        r = d["result"]
        ci, ac = r["complexInfo"], r["articleCountInfoDto"]
        addr = ci.get("address", {})
        return {
            "complexNumber": ci["complexNumber"],
            "name": ci["name"],
            "sector": addr.get("sector", ""),
            "jibun": addr.get("jibun", ""),
            "road": addr.get("roadName", ""),
            "households": ci.get("totalHouseholdNumber"),
            "year": (ci.get("useApprovalDate") or "")[:4],
            "deal": ac.get("dealCount", 0),
            "jeonse": ac.get("leaseDepositCount", 0),
            "wolse": ac.get("leaseMonthlyCount", 0),
            "url": r.get("url", ""),
        }

    # ── 지도 영역 안의 단지 번호 ─────────────────────────────
    def complexes_in_area(self, left, right, bottom, top,
                          trade_types=("A1", "B1"),
                          estate_types=("A01", "A04", "B01")):
        body = {
            "filter": _filter(trade_types, estate_types),
            "boundingBox": {"left": left, "right": right,
                            "top": top, "bottom": bottom},
            "precision": 15, "userChannelType": "PC",
        }
        d = self.call("/front-api/v1/complex/complexClusters", "POST", body)
        return [c["complexNumber"] for c in d["result"]["clusters"]]

    # ── 단지의 매물 전량 (페이지 넘김 포함) ──────────────────
    def articles(self, complex_no, trade_types=("A1",), max_pages=12):
        out, last, page = [], [], 0
        while True:
            body = {
                "size": 30, "complexNumber": int(complex_no),
                "tradeTypes": list(trade_types),
                "pyeongTypes": [], "dongNumbers": [],
                "userChannelType": "PC",
                "articleSortType": "RANKING_DESC",
                "lastInfo": last,
            }
            d = self.call("/front-api/v1/complex/article/list", "POST", body)
            r = d["result"]
            out += r.get("list") or []
            page += 1
            if not r.get("hasNextPage") or page >= max_pages:
                break
            last = r.get("lastInfo") or []
        return out

    def close(self):
        try:
            self.page.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# 매물 한 건 → 표 한 줄
# ──────────────────────────────────────────────────────────────
def money(v):
    """1370000000 → '13억 7,000'"""
    v = int(v or 0)
    if not v:
        return ""
    eok, man = v // 100000000, (v % 100000000) // 10000
    if eok:
        return "%d억 %s" % (eok, format(man, ",")) if man else "%d억" % eok
    return format(man, ",") + "만"


def flatten(item, complex_name=""):
    x = item.get("representativeArticleInfo") or item
    price = x.get("priceInfo") or {}
    space = x.get("spaceInfo") or {}
    detail = x.get("articleDetail") or {}
    verify = x.get("verificationInfo") or {}
    broker = x.get("brokerInfo") or {}

    # 호가 변동 이력 — 화면에는 잘 안 보이는 값입니다
    hist = price.get("priceChangeHistories") or []
    change = ""
    if len(hist) >= 2:
        first = hist[0].get("dealPrice") or hist[0].get("warrantyPrice") or 0
        last = hist[-1].get("dealPrice") or hist[-1].get("warrantyPrice") or 0
        if first and last and first != last:
            change = ("▼" if last < first else "▲") + money(abs(last - first))

    return {
        "단지": x.get("complexName") or complex_name,
        "매물번호": x.get("articleNumber", ""),
        "거래유형": TRADE_NAME.get(x.get("tradeType"), x.get("tradeType", "")),
        "가격": money(price.get("dealPrice") or price.get("warrantyPrice")),
        "월세": money(price.get("rentPrice")),
        "동": x.get("dongName", ""),
        "공급면적": space.get("supplySpaceName", ""),
        "전용면적": space.get("exclusiveSpaceName", ""),
        "층": detail.get("floorInfo", ""),
        "향": DIRECTION.get(detail.get("direction"), detail.get("direction", "")),
        "호가변동": change,
        "관리비": money(price.get("managementFeeAmount")),
        "확인일": verify.get("articleConfirmDate", ""),
        "중개사": broker.get("brokerageName", ""),
        "특징": (detail.get("articleFeatureDescription") or "")[:80],
        "_원": int(price.get("dealPrice") or price.get("warrantyPrice") or 0),
        "_월세원": int(price.get("rentPrice") or 0),
        "_관리비원": int(price.get("managementFeeAmount") or 0),
        "_단지번호": x.get("complexNumber", ""),
    }


COLUMNS = ["단지", "거래유형", "가격", "월세", "동", "공급면적", "전용면적",
           "층", "향", "호가변동", "관리비", "확인일", "중개사", "특징", "매물번호"]


def write_csv(rows, path, columns=None):
    columns = columns or COLUMNS
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return os.path.abspath(path)


def print_table(rows, limit=40):
    if not rows:
        print("매물이 없습니다.")
        return
    head = "%-16s %-5s %-12s %-6s %-9s %-7s %-4s %-9s %s" % (
        "단지", "거래", "가격", "동", "전용", "층", "향", "호가변동", "확인일")
    print(head)
    print("-" * 92)
    for r in rows[:limit]:
        print("%-16s %-5s %-12s %-6s %-9s %-7s %-4s %-9s %s" % (
            r["단지"][:15], r["거래유형"], r["가격"], r["동"],
            r["전용면적"], r["층"], r["향"], r["호가변동"] or "·", r["확인일"]))
    if len(rows) > limit:
        print("... 외 %d건 (전체는 --csv 로 저장하세요)" % (len(rows) - limit))


def summarize(rows):
    prices = sorted(r["_원"] for r in rows if r["_원"])
    if not prices:
        return
    down = [r for r in rows if r["호가변동"].startswith("▼")]
    up = [r for r in rows if r["호가변동"].startswith("▲")]
    print("\n총 %d건 · 최저 %s / 중위 %s / 최고 %s" % (
        len(rows), money(prices[0]), money(prices[len(prices) // 2]),
        money(prices[-1])))
    print("호가 내린 매물 %d건 · 올린 매물 %d건" % (len(down), len(up)))


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        if r["매물번호"] in seen:
            continue
        seen.add(r["매물번호"])
        out.append(r)
    return out


# ──────────────────────────────────────────────────────────────
# 명령 (터미널 단독 실행용)
# ──────────────────────────────────────────────────────────────
def collect(land, targets, trades):
    """단지 목록을 받아 매물을 전부 모은다."""
    rows = []
    for n, t in enumerate(targets, 1):
        try:
            items = land.articles(t["complexNumber"], trades)
        except Exception as e:
            land.log("  ! %s 실패: %s" % (t["name"], str(e)[:50]))
            continue
        rows += [flatten(i, t["name"]) for i in items]
        land.log("  [%d/%d] %s — 누적 %d건" % (n, len(targets), t["name"], len(rows)))
    return dedupe(rows)


def scan_area(land, left, right, bottom, top, filter_word, trades, estates,
              limit=200):
    """영역 안 단지를 훑는다. 단지 하나당 조회 1회라 후보가 많으면 오래 걸린다."""
    numbers = land.complexes_in_area(left, right, bottom, top, trades, estates)
    total = len(numbers)
    if total > limit:
        land.log("영역 안 단지 후보 %d개 — 상한 %d개까지만 봅니다." % (total, limit))
        numbers = numbers[:limit]
    else:
        land.log("영역 안 단지 후보 %d개 — 기본정보를 확인합니다." % total)

    targets = []
    for n, no in enumerate(numbers, 1):
        try:
            info = land.complex_info(no)
        except Exception:
            continue
        if filter_word and filter_word not in info["sector"]:
            continue
        targets.append(info)
        if n % 10 == 0:
            land.log("  ...%d/%d 확인, 대상 %d개" % (n, len(numbers), len(targets)))

    targets.sort(key=lambda t: -(t["deal"] + t["jeonse"] + t["wolse"]))
    return targets


def show_targets(targets):
    print("\n대상 단지 %d개" % len(targets))
    print("%-9s %-24s %-6s %-7s %5s %5s %5s" %
          ("번호", "단지명", "준공", "세대", "매매", "전세", "월세"))
    print("-" * 74)
    for t in targets:
        print("%-9s %-24s %-6s %-7s %5s %5s %5s" % (
            t["complexNumber"], t["name"][:22], t["year"], t["households"],
            t["deal"], t["jeonse"], t["wolse"]))


def cmd_info(args, land):
    for k, v in land.complex_info(args.complex_number).items():
        print("%-14s %s" % (k, v))


def cmd_complex(args, land):
    trades = args.trade.split(",")
    info = land.complex_info(args.complex_number)
    print("%s (%s) · %s세대 · %s년 준공\n" %
          (info["name"], info["sector"], info["households"], info["year"]))
    rows = dedupe([flatten(i, info["name"])
                   for i in land.articles(args.complex_number, trades)])
    rows.sort(key=lambda r: r["_원"])
    print_table(rows)
    summarize(rows)
    if args.csv:
        print("\nCSV 저장:", write_csv(rows, args.csv))


def cmd_area(args, land):
    targets = scan_area(land, args.left, args.right, args.bottom, args.top,
                        args.filter, args.trade.split(","), args.estate.split(","),
                        args.limit)
    show_targets(targets)
    if not args.articles:
        print("\n매물까지 뽑으려면 --articles 를 붙이세요.")
        return
    print("\n매물 수집 중...")
    rows = collect(land, targets, args.trade.split(","))
    rows.sort(key=lambda r: (r["단지"], r["_원"]))
    print()
    print_table(rows)
    summarize(rows)
    if args.csv:
        print("\nCSV 저장:", write_csv(rows, args.csv))


def cmd_region(args, land):
    hits = land.find_region(args.query)
    if not hits:
        sys.exit("'%s' 을(를) 찾지 못했습니다. '서울시 양천구 신정동' 처럼 적어 보세요." % args.query)
    if len(hits) > 1:
        print("여러 곳이 걸렸습니다. 앞의 것으로 진행합니다:")
        for h in hits[:8]:
            print("   -", h.get("fullAddress"))
    region = hits[0]
    dong = region.get("legalDivisionName", "")
    c = region["coordinates"]
    lon, lat = c["xCoordinate"], c["yCoordinate"]
    dx, dy = args.span, args.span * 0.8
    print("\n%s  (중심 %.5f, %.5f)" % (region.get("fullAddress"), lon, lat))

    targets = scan_area(land, lon - dx, lon + dx, lat - dy, lat + dy,
                        dong, args.trade.split(","), args.estate.split(","),
                        args.limit)
    show_targets(targets)
    if not args.articles:
        print("\n매물까지 뽑으려면 --articles 를 붙이세요.")
        return
    print("\n매물 수집 중...")
    rows = collect(land, targets, args.trade.split(","))
    rows.sort(key=lambda r: (r["단지"], r["_원"]))
    print()
    print_table(rows)
    summarize(rows)
    if args.csv:
        print("\nCSV 저장:", write_csv(rows, args.csv))


def main():
    p = argparse.ArgumentParser(
        description="네이버 부동산 매물 조회 (실제 크롬 경유)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="GUI 로 쓰려면  python app.py  를 실행하세요.")
    p.add_argument("--headless", action="store_true",
                   help="크롬 창을 띄우지 않는다 (차단 가능성이 있어 권장하지 않음)")
    p.add_argument("--quiet", action="store_true", help="진행 로그를 줄인다")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("region", help="동 이름으로 단지·매물 찾기")
    q.add_argument("query", help='예: "서울시 양천구 신정동"')
    q.add_argument("--span", type=float, default=0.013)
    q.add_argument("--limit", type=int, default=200)
    q.add_argument("--trade", default="A1")
    q.add_argument("--estate", default="A01")
    q.add_argument("--articles", action="store_true")
    q.add_argument("--csv")

    q = sub.add_parser("complex", help="단지 하나의 매물 전량")
    q.add_argument("complex_number")
    q.add_argument("--trade", default="A1")
    q.add_argument("--csv")

    q = sub.add_parser("info", help="단지 기본정보")
    q.add_argument("complex_number")

    q = sub.add_parser("area", help="지도 영역(경위도)으로 찾기")
    q.add_argument("left", type=float)
    q.add_argument("right", type=float)
    q.add_argument("bottom", type=float)
    q.add_argument("top", type=float)
    q.add_argument("--filter", default="")
    q.add_argument("--trade", default="A1")
    q.add_argument("--estate", default="A01")
    q.add_argument("--limit", type=int, default=200)
    q.add_argument("--articles", action="store_true")
    q.add_argument("--csv")

    args = p.parse_args()
    land = NaverLand(headless=args.headless, quiet=args.quiet)
    try:
        {"region": cmd_region, "complex": cmd_complex,
         "info": cmd_info, "area": cmd_area}[args.cmd](args, land)
    except RuntimeError as e:
        msg = str(e)
        if "429" in msg:
            print("\n429 — 요청이 너무 잦습니다. 몇 분 뒤 다시 시도하세요.")
        elif "401" in msg or "403" in msg:
            print("\n인증 거부 — 뜬 크롬 창에서 네이버 부동산을 직접 한 번 열어 본 뒤 재시도하세요.")
        else:
            print("\n실패: " + msg)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    finally:
        land.close()


if __name__ == "__main__":
    main()
