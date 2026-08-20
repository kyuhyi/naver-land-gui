# -*- coding: utf-8 -*-
"""
build_exe.py — 단독 실행파일(.exe) 만들기

    pip install pyinstaller
    python build_exe.py

결과: dist/BSD-NaverLand.exe  (한 파일, 더블클릭 실행)

· 크롬은 포함되지 않습니다 — 사용자 PC에 설치된 구글 크롬을 그대로 씁니다.
· playwright 의 node 드라이버가 통째로 들어가 용량이 큽니다(200MB 안팎).
· 첫 실행은 압축을 푸느라 10초쯤 걸립니다. 빠르게 뜨길 원하면
  ONEFILE = False 로 바꿔 폴더 형태로 만드세요.
"""

import os
import shutil
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 파일명은 반드시 ASCII 로 두세요.
# PyInstaller 의 onefile 부트로더는 실행파일 이름에 한글이 들어가면
# 압축을 풀지 못하고 아무 창도 없이 조용히 끝납니다(종료코드 0).
# 창 제목·작업표시줄에는 한글 이름이 그대로 나오니 보이는 데는 지장 없습니다.
NAME = "BSD-NaverLand"
ONEFILE = True

# python build_exe.py --debug  → 콘솔이 뜨는 폴더 형태로 만들어 오류를 바로 봅니다
DEBUG = "--debug" in sys.argv


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("pyinstaller 가 없습니다.  pip install pyinstaller  후 다시 실행하세요.")

    icon = os.path.join(APP_DIR, "assets", "bsd-symbol-color.png")
    ico = os.path.join(APP_DIR, "assets", "app.ico")
    if not os.path.exists(ico):
        try:
            from PIL import Image
            im = Image.open(icon).convert("RGBA")
            im.save(ico, sizes=[(256, 256), (128, 128), (64, 64),
                                (48, 48), (32, 32), (16, 16)])
            print("아이콘 변환:", ico)
        except Exception as e:
            print("아이콘 변환 실패(무시하고 진행):", e)
            ico = None

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--console" if DEBUG else "--windowed",
        "--name", NAME + ("_debug" if DEBUG else ""),
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
    if ONEFILE and not DEBUG:
        args.append("--onefile")
    if ico and os.path.exists(ico):
        args += ["--icon", ico]
    args.append(os.path.join(APP_DIR, "app.py"))

    print("실행:", " ".join(args), "\n")
    rc = subprocess.call(args, cwd=APP_DIR)
    if rc != 0:
        sys.exit("빌드 실패 (코드 %d)" % rc)

    name = NAME + ("_debug" if DEBUG else "")
    out = os.path.join(APP_DIR, "dist", name + (".exe" if ONEFILE and not DEBUG else ""))
    if os.path.exists(out):
        size = (os.path.getsize(out) / 1048576 if ONEFILE and not DEBUG
                else sum(os.path.getsize(os.path.join(r, f))
                         for r, _, fs in os.walk(out) for f in fs) / 1048576)
        print("\n완성: %s  (%.0f MB)" % (out, size))
    else:
        print("\n빌드는 끝났는데 결과물을 찾지 못했습니다:", out)


if __name__ == "__main__":
    main()
