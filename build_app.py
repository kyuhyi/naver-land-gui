# -*- coding: utf-8 -*-
"""
build_app.py — 실행파일 만들기 (Windows · macOS · Linux)

    pip install pyinstaller
    python build_app.py
    python build_app.py --debug     # 콘솔이 뜨는 폴더 형태 (원인 추적용)

결과
    Windows  dist/BSD-NaverLand.exe          한 파일, 더블클릭
    macOS    dist/BSD-NaverLand.app          앱 번들 (+ 배포용 zip)
    Linux    dist/BSD-NaverLand/BSD-NaverLand

공통 주의
  · 크롬은 포함되지 않습니다. 쓰는 PC 마다 구글 크롬이 설치돼 있어야 합니다.
  · 파일명은 반드시 ASCII 로 두세요. PyInstaller 의 onefile 부트로더는
    실행파일 이름에 한글이 들어가면 압축을 풀지 못하고 창도 오류도 없이
    종료코드 0 으로 조용히 끝납니다. 창 제목과 Dock 이름에는 한글이 그대로
    나오므로 보이는 데는 지장이 없습니다.

macOS 주의
  · 크로스 빌드는 안 됩니다. 맥용 .app 은 맥에서 빌드해야 합니다.
    맥이 없으면 .github/workflows/build-macos.yml 이 GitHub 의 맥 러너에서
    대신 빌드해 줍니다.
  · 서명하지 않은 앱이라 처음 열 때 Gatekeeper 가 막습니다. 아래 중 하나로:
        xattr -dr com.apple.quarantine dist/BSD-NaverLand.app
    또는 Finder 에서 앱을 우클릭 → 열기 → 다시 열기.
  · 러너 아키텍처대로 나옵니다(arm64 러너 → Apple Silicon 전용).
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "BSD-NaverLand"                 # ASCII 고정 — 위 주의 참고
DISPLAY_NAME = "네이버 부동산 매물 조회기"
BUNDLE_ID = "kr.co.bsd.naverland"
VERSION = "0.1.0"

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


def log(*a):
    print(*a, flush=True)


# ──────────────────────────────────────────────────────────────
# 아이콘
# ──────────────────────────────────────────────────────────────
def make_windows_icon(png):
    ico = os.path.join(APP_DIR, "assets", "app.ico")
    if os.path.exists(ico):
        return ico
    try:
        from PIL import Image
        Image.open(png).convert("RGBA").save(
            ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        log("아이콘 변환:", ico)
        return ico
    except Exception as e:
        log("아이콘 변환 실패(무시하고 진행):", e)
        return None


def make_mac_icon(png):
    """iconutil 로 .icns 를 만든다. 없으면 Pillow 로 시도."""
    icns = os.path.join(APP_DIR, "assets", "app.icns")
    if os.path.exists(icns):
        return icns

    if shutil.which("iconutil"):
        try:
            from PIL import Image
            src = Image.open(png).convert("RGBA")
            iconset = os.path.join(APP_DIR, "assets", "app.iconset")
            shutil.rmtree(iconset, ignore_errors=True)
            os.makedirs(iconset)
            for size in (16, 32, 128, 256, 512):
                src.resize((size, size), Image.LANCZOS).save(
                    os.path.join(iconset, "icon_%dx%d.png" % (size, size)))
                src.resize((size * 2, size * 2), Image.LANCZOS).save(
                    os.path.join(iconset, "icon_%dx%d@2x.png" % (size, size)))
            subprocess.check_call(["iconutil", "-c", "icns", iconset, "-o", icns])
            shutil.rmtree(iconset, ignore_errors=True)
            log("아이콘 변환:", icns)
            return icns
        except Exception as e:
            log("iconutil 변환 실패:", e)

    try:
        from PIL import Image
        Image.open(png).convert("RGBA").save(icns)
        log("아이콘 변환(Pillow):", icns)
        return icns
    except Exception as e:
        log("아이콘 변환 실패(무시하고 진행):", e)
        return None


# ──────────────────────────────────────────────────────────────
# macOS 번들 마무리
# ──────────────────────────────────────────────────────────────
def finish_mac_bundle(app_path):
    """Info.plist 를 손보고 배포용 zip 을 만든다."""
    import plistlib

    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(plist_path, "rb") as f:
            info = plistlib.load(f)
        info.update({
            "CFBundleName": NAME,
            "CFBundleDisplayName": DISPLAY_NAME,
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            # 시스템이 라이트 모드여도 앱은 어둡게 — 화면 전체가 다크 테마다
            "NSAppearance": "NSAppearanceNameDarkAqua",
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": "BSD · Business System Development",
        })
        with open(plist_path, "wb") as f:
            plistlib.dump(info, f)
        log("Info.plist 정리 완료")
    except Exception as e:
        log("Info.plist 수정 실패(무시하고 진행):", e)

    # ditto 로 묶어야 실행 권한과 심볼릭 링크가 살아남는다. zip 으로는 깨진다.
    arch = platform.machine()          # arm64 / x86_64
    out = os.path.join(APP_DIR, "dist", "%s-macos-%s.zip" % (NAME, arch))
    if shutil.which("ditto"):
        subprocess.check_call(["ditto", "-c", "-k", "--keepParent", app_path, out])
        log("배포용 zip:", out, "(%.0f MB)" % (os.path.getsize(out) / 1048576))
    else:
        log("ditto 가 없어 zip 은 건너뜁니다.")
    return out


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="실행파일 빌드")
    ap.add_argument("--debug", action="store_true",
                    help="콘솔이 뜨는 폴더 형태로 만들어 오류를 바로 본다")
    args = ap.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("pyinstaller 가 없습니다.  pip install pyinstaller  후 다시 실행하세요.")

    png = os.path.join(APP_DIR, "assets", "bsd-symbol-color.png")
    icon = make_mac_icon(png) if IS_MAC else make_windows_icon(png) if IS_WIN else None

    name = NAME + ("_debug" if args.debug else "")
    # 맥은 .app 번들이라 onefile 을 쓰지 않는다(느리고 서명이 꼬인다).
    onefile = IS_WIN and not args.debug

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--console" if args.debug else "--windowed",
        "--name", name,
        "--add-data", "assets%sassets" % os.pathsep,
        "--collect-all", "playwright",
        "--hidden-import", "models",
        "--hidden-import", "worker",
        "--hidden-import", "theme",
        "--hidden-import", "naver_land",
        "--hidden-import", "selftest",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtQuick3D",
        "--exclude-module", "PySide6.QtCharts",
        "--exclude-module", "PySide6.QtDataVisualization",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "matplotlib",
        "--exclude-module", "tkinter",
    ]
    if onefile:
        cmd.append("--onefile")
    if icon:
        cmd += ["--icon", icon]
    if IS_MAC and not args.debug:
        cmd += ["--osx-bundle-identifier", BUNDLE_ID]
    cmd.append(os.path.join(APP_DIR, "app.py"))

    log("실행:", " ".join(cmd), "\n")
    if subprocess.call(cmd, cwd=APP_DIR) != 0:
        sys.exit("빌드 실패")

    dist = os.path.join(APP_DIR, "dist")
    if IS_MAC and not args.debug:
        app = os.path.join(dist, name + ".app")
        if not os.path.isdir(app):
            sys.exit("앱 번들을 찾지 못했습니다: " + app)
        finish_mac_bundle(app)
        log("\n완성:", app)
        log("처음 열 때 Gatekeeper 가 막으면:")
        log("  xattr -dr com.apple.quarantine '%s'" % app)
    else:
        out = os.path.join(dist, name + (".exe" if onefile else ""))
        if not os.path.exists(out):
            sys.exit("결과물을 찾지 못했습니다: " + out)
        size = (os.path.getsize(out) if onefile else
                sum(os.path.getsize(os.path.join(r, f))
                    for r, _, fs in os.walk(out) for f in fs)) / 1048576
        log("\n완성: %s  (%.0f MB)" % (out, size))

    log("\n확인:  <실행파일> --selftest   →  selftest.log 의 끝줄이 SELFTEST PASS 면 정상")


if __name__ == "__main__":
    main()
