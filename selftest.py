# -*- coding: utf-8 -*-
"""
selftest.py — 빌드가 제대로 됐는지 확인한다.

    BSD-NaverLand.exe --selftest

창을 띄우지 않고 크롬 연결 → 단지 조회 → 매물 조회까지 실제로 해 본 뒤,
실행파일 옆에 selftest.log 를 남깁니다. 배포 전 점검용입니다.
"""

import os
import sys
import time
import traceback

TEST_COMPLEX = "8742"          # 목동우성2차


def run(log_dir, assets_dir):
    lines = []
    t0 = time.time()

    def say(text):
        line = "[%6.1fs] %s" % (time.time() - t0, text)
        lines.append(line)
        try:
            print(line, flush=True)
        except Exception:
            pass

    ok = False
    try:
        say("frozen        : %s" % bool(getattr(sys, "frozen", False)))
        say("실행파일      : %s" % sys.executable)
        say("assets 폴더   : %s (있음=%s)" % (assets_dir, os.path.isdir(assets_dir)))
        for name in ("bsd-white.png", "bsd-symbol-color.png"):
            p = os.path.join(assets_dir, name)
            say("  %-22s %s" % (name, "OK" if os.path.exists(p) else "없음"))

        import playwright
        drv = os.path.join(os.path.dirname(playwright.__file__), "driver")
        say("playwright    : %s" % os.path.dirname(playwright.__file__))
        say("  driver/node.exe        %s" %
            ("OK" if os.path.exists(os.path.join(drv, "node.exe")) else "없음"))

        from playwright.sync_api import sync_playwright  # noqa: F401
        say("playwright import OK")

        import naver_land as nl
        say("크롬 연결 시도…")
        land = nl.NaverLand(quiet=True)
        try:
            say("크롬 연결 OK")
            info = land.complex_info(TEST_COMPLEX)
            say("단지 정보 OK : %s · %s · %s세대 · %s년 · 매매 %s건" % (
                info["name"], info["sector"], info["households"],
                info["year"], info["deal"]))

            items = land.articles(TEST_COMPLEX, ["A1"])
            rows = [nl.flatten(i, info["name"]) for i in items]
            rows = nl.dedupe(rows)
            say("매물 조회 OK : %d건" % len(rows))
            for r in rows[:3]:
                say("  %s %s %s %s %s" % (r["단지"], r["거래유형"], r["가격"],
                                          r["전용면적"], r["층"]))
            prices = sorted(r["_원"] for r in rows if r["_원"])
            if prices:
                say("  최저 %s / 중위 %s / 최고 %s" % (
                    nl.money(prices[0]), nl.money(prices[len(prices) // 2]),
                    nl.money(prices[-1])))
            ok = bool(rows)
        finally:
            land.close()

        say("SELFTEST PASS" if ok else "SELFTEST FAIL — 매물이 0건입니다")
    except Exception:
        say("SELFTEST FAIL")
        lines.append(traceback.format_exc())

    path = os.path.join(log_dir, "selftest.log")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(os.linesep.join(lines))
            f.write(os.linesep)
    except OSError:
        pass
    return 0 if ok else 1
