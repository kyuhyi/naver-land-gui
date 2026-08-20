#!/usr/bin/env bash
# 빌드 결과물을 릴리스에 붙인다. 맥·윈도우 잡이 공용으로 쓴다.
#
# 릴리스 자산은 Actions 아티팩트 저장 용량과 별개로 계산된다.
# 아티팩트 용량이 차 있어도 이쪽으로는 올라간다.
set -euo pipefail

TAG="${TAG:-build-latest}"

cat > "${RUNNER_TEMP:-/tmp}/notes.md" <<'NOTES'
최신 커밋에서 자동으로 구운 실행파일입니다. 쓰는 컴퓨터에 맞는 걸 받으세요.

| 파일 | 어디에 |
|------|--------|
| `BSD-NaverLand.exe` | 윈도우 64비트 |
| `BSD-NaverLand-macos-arm64.zip` | 맥 · M1 이후 (Apple Silicon) |
| `BSD-NaverLand-macos-x86_64.zip` | 맥 · 인텔 |

맥이 어느 쪽인지 모르겠으면 터미널에서 `uname -m` — `arm64` 면 위, `x86_64` 면 아래.

### 준비물

**구글 크롬**이 설치돼 있어야 합니다. 앱에 크롬은 들어 있지 않습니다.
그리고 **국내 IP** 에서만 조회됩니다. 해외·VPN·클라우드 서버에서는
네이버가 응답 자체를 주지 않습니다.

### 맥에서 처음 열 때

개발자 인증서로 서명한 앱이 아니라 Gatekeeper 가 한 번 막습니다.
압축을 푼 뒤 Finder 에서 앱을 **우클릭 → 열기 → 다시 열기**.

그래도 「손상되었기 때문에 열 수 없습니다」 가 뜨면 터미널에서:

```
xattr -cr BSD-NaverLand.app && codesign --force --deep --sign - BSD-NaverLand.app
```

### 잘 깔렸는지 확인

```
# 맥
BSD-NaverLand.app/Contents/MacOS/BSD-NaverLand --selftest
cat ~/Library/Logs/BSD-NaverLand/selftest.log

# 윈도우
BSD-NaverLand.exe --selftest
type selftest.log
```

끝줄이 `SELFTEST PASS` 면 정상입니다. 크롬 연결부터 실제 매물 조회까지
해 본 결과입니다.
NOTES

gh release view "$TAG" >/dev/null 2>&1 || \
  gh release create "$TAG" \
    --title "실행파일 (최신 빌드)" \
    --notes-file "${RUNNER_TEMP:-/tmp}/notes.md" \
    --prerelease || true

gh release upload "$TAG" "$@" --clobber
echo "받는 곳: $(gh release view "$TAG" --json url --jq .url)"
