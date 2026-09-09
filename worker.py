# -*- coding: utf-8 -*-
"""worker.py — 크롬/네이버 조회를 백그라운드 스레드에서 돌린다.

playwright 의 sync API 는 만들어진 스레드에 묶이므로, 한 번의 검색이
스레드 하나 안에서 생성 → 조회 → 정리까지 마친다. 크롬 프로세스 자체는
계속 살아 있어서 다음 검색은 붙기만 하면 된다(빠름).
"""

import time

from PySide6.QtCore import QThread, Signal

import naver_land as nl


class Cancelled(Exception):
    """사용자가 중지를 눌렀을 때."""


class UserError(Exception):
    """사용자에게 그대로 보여줄 오류."""


class GuiLand(nl.NaverLand):
    """엔진에 로그 신호와 취소 반응을 붙인 버전."""

    def __init__(self, worker, headless=False, show_hud=True):
        self._w = worker
        super().__init__(headless=headless, quiet=True, show_hud=show_hud)

    def log(self, *a):
        text = " ".join(str(x) for x in a)
        self._w.log.emit(text)
        self.hud.log(text)

    def sleep(self, seconds):
        # 취소에 빨리 반응하도록 잘게 쪼개 잔다
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._w.is_cancelled():
                raise Cancelled()
            time.sleep(0.05)

    def call(self, path, method="GET", body=None):
        if self._w.is_cancelled():
            raise Cancelled()
        return super().call(path, method, body)


class SearchWorker(QThread):
    """params['mode'] 에 따라 region / complex / info / area 를 수행."""

    log = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)          # (현재, 전체) — 전체 0 이면 불확정
    complexesReady = Signal(list)        # 단지 목록
    articlesBatch = Signal(list)         # 매물 묶음 (단지 하나 분량)
    infoReady = Signal(dict)             # 단지 기본정보
    done = Signal(bool, str)             # (성공?, 메시지)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.p = params
        self._cancel = False
        self.land = None

    # ── 취소 ────────────────────────────────────────────────
    def cancel(self):
        self._cancel = True

    def is_cancelled(self):
        return self._cancel or self.isInterruptionRequested()

    def _check(self):
        if self.is_cancelled():
            raise Cancelled()

    # ── 앱 상태줄과 크롬 패널에 같이 알린다 ─────────────────
    def _say(self, text, phase=None):
        self.status.emit(text)
        if self.land:
            self.land.hud.set(status=text, **({"phase": phase} if phase else {}))

    def _cards(self, rows):
        """방금 찾은 매물 몇 건을 크롬 패널에 카드로 띄운다."""
        if not self.land:
            return
        self.land.hud.cards([{
            "name": r.get("단지", ""),
            "price": r.get("가격", ""),
            "meta": " · ".join(x for x in (r.get("전용면적"), r.get("층")) if x),
        } for r in rows[:6]])

    # ── 실행 ────────────────────────────────────────────────
    def run(self):
        p = self.p
        nl.POLITE_DELAY = float(p.get("delay", 0.8))
        try:
            self.status.emit("크롬 연결 중…")
            self.progress.emit(0, 0)
            self.land = GuiLand(self, headless=p.get("headless", False),
                                show_hud=p.get("show_hud", True))
            self.log.emit("크롬 연결 완료 · 요청 간격 %.1f초" % nl.POLITE_DELAY)
            self._check()

            {"region": self._region, "complex": self._complex,
             "info": self._info, "area": self._area}[p["mode"]]()

            self.land.hud.done(True, "완료")
            self.done.emit(True, "완료")

        except Cancelled:
            if self.land:
                self.land.hud.done(False, "사용자가 중지했습니다.")
            self.done.emit(False, "사용자가 중지했습니다.")
        except UserError as e:
            self.done.emit(False, str(e))
        except (RuntimeError, SystemExit) as e:
            self.done.emit(False, self._explain(str(e)))
        except Exception as e:
            self.done.emit(False, "%s: %s" % (type(e).__name__, e))
        finally:
            if self.land:
                self.land.close()
                self.land = None

    @staticmethod
    def _explain(msg):
        if "429" in msg:
            return ("429 — 요청이 너무 잦습니다. 몇 분 뒤 다시 시도하거나 "
                    "요청 간격을 늘려 주세요.")
        if "401" in msg or "403" in msg:
            return ("인증 거부 — 열려 있는 크롬 창에서 네이버 부동산을 "
                    "직접 한 번 열어 본 뒤 재시도하세요.")
        if "Timeout" in msg or "timeout" in msg:
            return ("응답이 없습니다. 국내 IP 인지, 크롬 창이 살아 있는지 "
                    "확인해 주세요.")
        return msg

    # ── 각 모드 ─────────────────────────────────────────────
    def _region(self):
        p = self.p
        self._say("'%s' 위치를 찾는 중…" % p["query"], phase="지역 검색")
        hits = self.land.find_region(p["query"])
        if not hits:
            raise UserError("'%s' 을(를) 찾지 못했습니다.\n"
                            "'서울시 양천구 신정동' 처럼 적어 보세요." % p["query"])
        if len(hits) > 1:
            self.log.emit("여러 곳이 걸려 첫 번째로 진행합니다: " +
                          " / ".join((h.get("fullAddress") or "") for h in hits[:5]))
        region = hits[0]
        dong = region.get("legalDivisionName", "")
        c = region["coordinates"]
        lon, lat = c["xCoordinate"], c["yCoordinate"]
        dx, dy = p["span"], p["span"] * 0.8
        self.log.emit("%s  (중심 %.5f, %.5f · 반경 약 %.1fkm)" % (
            region.get("fullAddress"), lon, lat, p["span"] * 88))

        targets = self._scan(lon - dx, lon + dx, lat - dy, lat + dy, dong)
        self._maybe_articles(targets)

    def _area(self):
        p = self.p
        targets = self._scan(p["left"], p["right"], p["bottom"], p["top"],
                             p.get("filter", ""))
        self._maybe_articles(targets)

    def _complex(self):
        p = self.p
        no = p["complex_number"]
        self.status.emit("단지 %s 정보 확인 중…" % no)
        info = self.land.complex_info(no)
        self.infoReady.emit(info)
        self.complexesReady.emit([info])
        self.log.emit("%s (%s) · %s세대 · %s년 준공" % (
            info["name"], info["sector"], info["households"], info["year"]))

        self._say("%s 매물 수집 중…" % info["name"], phase="매물 수집")
        self.progress.emit(0, 0)
        items = self.land.articles(no, p["trades"])
        rows = [nl.flatten(i, info["name"]) for i in items]
        self.articlesBatch.emit(rows)
        self._cards(rows)
        self.land.hud.set(articles=len(rows), complexes=1)
        self.log.emit("매물 %d건" % len(rows))

    def _info(self):
        no = self.p["complex_number"]
        self.status.emit("단지 %s 정보 확인 중…" % no)
        info = self.land.complex_info(no)
        self.infoReady.emit(info)
        self.complexesReady.emit([info])
        self.log.emit("%s · %s · %s세대" % (
            info["name"], info["sector"], info["households"]))

    # ── 공통: 영역 훑기 ─────────────────────────────────────
    def _scan(self, left, right, bottom, top, filter_word):
        p = self.p
        self._say("지도 영역 안 단지를 찾는 중…", phase="단지 탐색")
        self.progress.emit(0, 0)
        numbers = self.land.complexes_in_area(
            left, right, bottom, top, p["trades"], p["estates"])
        total = len(numbers)
        limit = p.get("limit", 200)
        if total > limit:
            self.log.emit("단지 후보 %d개 — 상한 %d개까지만 확인합니다." % (total, limit))
            numbers = numbers[:limit]
        else:
            self.log.emit("단지 후보 %d개" % total)

        targets = []
        n_total = len(numbers)
        eta = int(n_total * (nl.POLITE_DELAY + 0.15))
        self._say("단지 기본정보 확인 중… (약 %d초 예상)" % eta, phase="단지 확인")
        for n, no in enumerate(numbers, 1):
            self._check()
            try:
                info = self.land.complex_info(no)
            except Cancelled:
                raise
            except Exception:
                self.progress.emit(n, n_total)
                continue
            if filter_word and filter_word not in info["sector"]:
                self.progress.emit(n, n_total)
                continue
            targets.append(info)
            self.progress.emit(n, n_total)
            self.land.hud.set(status="%s — %s" % (info["name"], info["sector"]),
                              current=n, total=n_total, complexes=len(targets))
            if n % 10 == 0 or n == n_total:
                self.log.emit("  단지 확인 %d/%d — 대상 %d개" % (n, n_total, len(targets)))

        targets.sort(key=lambda t: -(t["deal"] + t["jeonse"] + t["wolse"]))
        self.complexesReady.emit(targets)
        if not targets:
            raise UserError("조건에 맞는 단지가 없습니다.\n"
                            "검색 반경을 넓히거나 매물종류·거래유형을 바꿔 보세요.")
        self.log.emit("대상 단지 %d개" % len(targets))
        return targets

    def _maybe_articles(self, targets):
        p = self.p
        if not p.get("articles"):
            self.status.emit("단지 %d개 — '매물까지 수집'을 켜면 매물을 가져옵니다." % len(targets))
            return
        total = len(targets)
        got = 0
        for n, t in enumerate(targets, 1):
            self._check()
            self._say("매물 수집 중… %d/%d  %s" % (n, total, t["name"]),
                      phase="매물 수집")
            self.land.hud.set(current=n, total=total)
            try:
                items = self.land.articles(t["complexNumber"], p["trades"])
            except Cancelled:
                raise
            except Exception as e:
                self.log.emit("  ! %s 실패: %s" % (t["name"], str(e)[:60]))
                self.progress.emit(n, total)
                continue
            rows = [nl.flatten(i, t["name"]) for i in items]
            got += len(rows)
            if rows:
                self.articlesBatch.emit(rows)
                self._cards(rows)
            self.land.hud.set(articles=got)
            self.progress.emit(n, total)
            self.log.emit("  [%d/%d] %s — %d건 (누적 %d건)" % (
                n, total, t["name"], len(rows), got))


class ChromeWarmupWorker(QThread):
    """크롬만 미리 띄워 두는 가벼운 작업."""

    done = Signal(bool, str)

    def __init__(self, headless=False, parent=None):
        super().__init__(parent)
        self.headless = headless

    def run(self):
        try:
            if nl.cdp_alive():
                self.done.emit(True, "크롬이 이미 준비되어 있습니다.")
                return
            nl.ensure_chrome(headless=self.headless)
            self.done.emit(True, "크롬을 띄웠습니다.")
        except Exception as e:
            self.done.emit(False, str(e))
