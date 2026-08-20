#!/bin/sh
# macOS / Linux 에서 더블클릭하거나 터미널에서 실행
cd "$(dirname "$0")" || exit 1
exec python3 app.py "$@"
