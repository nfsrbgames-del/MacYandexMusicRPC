#!/bin/bash
# ============================================================
# MacYandexMusicRPC — Установка
# Запусти двойным кликом или: bash setup.command
# ============================================================

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/homebrew/bin/python3.12"
PLIST_NAME="com.macyandexrpc"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "🎵 MacYandexMusicRPC — Установка"
echo "================================"

# 1. Homebrew
if ! command -v brew &>/dev/null; then
    echo "❌ Homebrew не установлен!"
    echo "   Установи: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi
echo "✅ Homebrew"

# 2. Python
if [ ! -f "$PYTHON" ]; then
    echo "📦 Устанавливаю python@3.12..."
    brew install python@3.12
fi
echo "✅ Python: $($PYTHON --version)"

# 3. nowplaying-cli
if ! command -v nowplaying-cli &>/dev/null; then
    echo "📦 Устанавливаю nowplaying-cli..."
    brew install nowplaying-cli
fi
echo "✅ nowplaying-cli"

# 4. media-control
if ! command -v media-control &>/dev/null; then
    echo "📦 Устанавливаю media-control..."
    brew tap ungive/media-control
    brew install media-control
fi
echo "✅ media-control"

# 5. pip зависимости
echo "📦 Устанавливаю pip зависимости..."
$PYTHON -m pip install --break-system-packages -r "$DIR/requirements.txt" 2>/dev/null || \
$PYTHON -m pip install --break-system-packages pypresence yandex-music rumps keyring
echo "✅ pip зависимости"

# 6. .env
if [ ! -f "$DIR/.env" ]; then
    cp "$DIR/.env.example" "$DIR/.env"
    echo "✅ .env создан из .env.example"
else
    echo "✅ .env уже есть"
fi

# 7. Автозапуск
echo ""
echo "Настроить автозапуск при входе в систему?"
read -p "[y/n]: " autostart

if [ "$autostart" = "y" ] || [ "$autostart" = "Y" ]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-gj</string>
        <string>$DIR/MacYandexMusicRPC.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"
    echo "✅ Автозапуск настроен (LaunchAgent)"
else
    # Удалить если было
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm "$PLIST_PATH"
        echo "✅ Автозапуск удалён"
    fi
fi

echo ""
echo "================================"
echo "✅ Установка завершена!"
echo ""
echo "Запуск: двойной клик MacYandexMusicRPC.app (без Terminal)"
echo "   или: $PYTHON $DIR/MacYandexMusicRPC.py"
echo ""
echo "Удалить автозапуск: launchctl unload $PLIST_PATH"
echo "Логи автозапуска: /tmp/macyandexrpc.log"
echo ""
read -p "Запустить сейчас? [y/n]: " run_now
if [ "$run_now" = "y" ] || [ "$run_now" = "Y" ]; then
    open -gj "$DIR/MacYandexMusicRPC.app" 2>/dev/null || open -gj "$DIR/run_music_rpc.command"
fi