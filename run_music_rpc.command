#!/bin/bash
# MacYandexMusicRPC — Запуск
DIR="$(cd "$(dirname "$0")" && pwd)"

# Ищем Python
if [ -f "/opt/homebrew/bin/python3.12" ]; then
    PYTHON="/opt/homebrew/bin/python3.12"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "❌ Python не найден! Запусти setup.command"
    exit 1
fi

# Ищем скрипт
if [ -f "$DIR/MacYandexMusicRPC.py" ]; then
    SCRIPT="$DIR/MacYandexMusicRPC.py"
elif [ -f "$DIR/main.py" ]; then
    SCRIPT="$DIR/main.py"
else
    echo "❌ Скрипт не найден!"
    exit 1
fi

exec "$PYTHON" "$SCRIPT"