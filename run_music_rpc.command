#!/bin/bash
# Предпочтительно: двойной клик по MacYandexMusicRPC.app (без Terminal)
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/MacYandexMusicRPC.app"

if [ -d "$APP" ]; then
    open -gj "$APP"
    exit 0
fi

if pgrep -f "MacYandexMusicRPC.py" >/dev/null 2>&1; then
    exit 0
fi

if [ -f "/opt/homebrew/bin/python3.12" ]; then
    PYTHON="/opt/homebrew/bin/python3.12"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "Python не найден. Запусти setup.command"
    exit 1
fi

SCRIPT="$DIR/MacYandexMusicRPC.py"
LOG_DIR="$HOME/.config/macyandexrpc"
mkdir -p "$LOG_DIR"
nohup "$PYTHON" -u "$SCRIPT" >>"$LOG_DIR/run.log" 2>&1 &
exit 0
