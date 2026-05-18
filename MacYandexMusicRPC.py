#!/usr/bin/env python3
"""
MacYandexMusicRPC v1.8
GitHub: https://github.com/FozerG/WinYandexMusicRPC

Требования (устанавливаются автоматически при первом запуске):
  brew install nowplaying-cli
  brew tap ungive/media-control && brew install media-control
"""

import subprocess
import time
import threading
import os
import sys
import json
import re
from itertools import permutations
from datetime import datetime

# ============================================================
# АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================

REQUIRED_PACKAGES = {
    "pypresence": "pypresence",
    "rumps": "rumps",
    "yandex_music": "yandex-music",
    "keyring": "keyring",
}

def _ensure_packages():
    """Проверяем и устанавливаем pip-зависимости."""
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return

    print(f"📦 Устанавливаю зависимости: {', '.join(missing)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "--break-system-packages", *missing],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ Зависимости установлены")
    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        print(f"   Установи вручную: {sys.executable} -m pip install --break-system-packages {' '.join(missing)}")
        sys.exit(1)

_ensure_packages()

# ============================================================
# ИМПОРТЫ (после автоустановки)
# ============================================================

import rumps
import keyring
from pypresence import Presence as DiscordRPC, PipeClosed, InvalidID
from pypresence.types import ActivityType
from yandex_music import Client

# ============================================================
# НАСТРОЙКИ
# ============================================================

_load_dotenv = lambda: None  # заглушка

def _load_env():
    """Читаем .env файл если есть."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value

_load_env()

CLIENT_ID = os.environ.get("CLIENT_ID", "1269826362399522849")
STRONG_FIND = os.environ.get("STRONG_FIND", "true").lower() in ("true", "1", "yes")
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", "5"))

KEYRING_SERVICE = "MacYandexMusicRPC"
KEYRING_KEY = "yandex_token"

# ============================================================
# ФИЛЬТРАЦИЯ
# ============================================================

YANDEX_APP_BUNDLES = {
    "ru.yandex.desktop.music",
    "ru.yandex.music.mac",
    "ru.yandex.music",
    "com.yandex.music",
}

BROWSER_BUNDLES = {
    "com.apple.Safari", "com.apple.SafariTechnologyPreview",
    "com.google.Chrome", "com.microsoft.edgemac",
    "org.mozilla.firefox", "com.operasoftware.Opera",
    "ru.yandex.browser", "company.thebrowser.Browser",
    "com.brave.Browser", "com.vivali.Vivaldi",
}

DISCORD_PROCESSES = ["Discord", "Discord Canary", "Discord PTB", "Vesktop"]

ICON_PLAYING = "https://raw.githubusercontent.com/FozerG/WinYandexMusicRPC/main/assets/Playing.png"
ICON_PAUSED = "https://raw.githubusercontent.com/FozerG/WinYandexMusicRPC/main/assets/Paused.png"

CONFIG_PATH = os.path.expanduser("~/.config/macyandexrpc/config.json")


# ============================================================
# УТИЛИТЫ
# ============================================================

def get_token():
    """
    Токен из keyring (системное хранилище macOS Keychain).
    Fallback: .env файл или переменная окружения.
    """
    # 1. Keyring (самый безопасный)
    try:
        token = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
        if token:
            return token
    except Exception:
        pass

    # 2. .env файл / переменная окружения
    return os.environ.get("YANDEX_TOKEN", "")


def set_token(token: str):
    """Сохраняем токен в keyring (macOS Keychain)."""
    try:
        if token:
            keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, token)
        else:
            # Удалить токен
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_KEY)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        print(f"[WARN] keyring: {e}")


def is_discord_running() -> bool:
    try:
        for name in DISCORD_PROCESSES:
            result = subprocess.run(
                ["pgrep", "-x", name], capture_output=True, timeout=2
            )
            if result.returncode == 0:
                return True
        return False
    except Exception:
        return True


def check_brew_deps():
    """Проверяем brew-зависимости и логируем."""
    missing = []
    for cmd in ["nowplaying-cli", "media-control"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=2)
        except FileNotFoundError:
            missing.append(cmd)

    if missing:
        msg = f"Не установлено: {', '.join(missing)}\n\n"
        if "nowplaying-cli" in missing:
            msg += "brew install nowplaying-cli\n"
        if "media-control" in missing:
            msg += "brew tap ungive/media-control && brew install media-control\n"
        msg += "\nБез них скрипт не будет работать."
        rumps.alert("⚠️ Зависимости", msg)
        return False
    return True


def clean_title_feat(title: str) -> str:
    return re.sub(
        r'\(feat\.?.*?\)|\(ft\.?.*?\)|\(с участием.*?\)|\(при уч\.?.*?\)',
        '', title, flags=re.IGNORECASE
    ).strip()


def format_duration(seconds):
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"


def extract_deep_link(url):
    pattern = r"https://music\.yandex\.ru/album/(\d+)/track/(\d+)"
    match = re.match(pattern, url)
    if match:
        album_id, track_id = match.groups()
        return f"yandexmusic://album/{album_id}/track/{track_id}"
    return None


def build_buttons(track_url):
    buttons = []
    if track_url:
        buttons.append({"label": "Откр. в браузере", "url": track_url})
        deep_link = extract_deep_link(track_url)
        if deep_link:
            buttons.append({"label": "Откр. в прилож.", "url": deep_link})
    for button in buttons:
        if len(button["label"].encode("utf-8")) > 32:
            print(f"[WARN] Label > 32 байт!")
    return buttons


def get_media_source():
    try:
        result = subprocess.run(
            ["media-control", "get"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("bundleIdentifier") or data.get("parentApplicationBundleIdentifier")
    except Exception:
        pass
    return None


def get_nowplaying() -> dict | None:
    try:
        result = subprocess.run(
            ["nowplaying-cli", "get", "title", "artist", "album",
             "playbackRate", "elapsedTime", "duration"],
            capture_output=True, text=True, timeout=3
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return None

        title = lines[0].strip() if lines[0].strip() != "null" else None
        artist = lines[1].strip() if lines[1].strip() != "null" else None
        album = lines[2].strip() if len(lines) > 2 and lines[2].strip() != "null" else None
        pr = lines[3].strip() if len(lines) > 3 else "0"
        el = lines[4].strip() if len(lines) > 4 else "0"
        du = lines[5].strip() if len(lines) > 5 else "0"

        if not title:
            return None

        try: playback_rate = float(pr)
        except ValueError: playback_rate = 0.0
        try: elapsed = float(el) if el != "null" else 0.0
        except ValueError: elapsed = 0.0
        try: duration = float(du) if du != "null" else 0.0
        except ValueError: duration = 0.0

        source = get_media_source()

        return {
            "title": title, "artist": artist or "Unknown Artist", "album": album,
            "is_playing": playback_rate > 0, "elapsed": elapsed,
            "duration": duration, "source": source,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    except Exception:
        return None


def search_yandex(client: Client, title: str, artist: str) -> dict | None:
    try:
        clean = clean_title_feat(title).replace("'", "").replace("\'", "")
        query = f"{clean} {artist}".strip()

        result = client.search(query, type_="track")
        if not result or not result.tracks or not result.tracks.results:
            result = client.search(clean, type_="track")
        if not result or not result.tracks or not result.tracks.results:
            return None

        tracks = result.tracks.results
        found = None

        for track in tracks[:5]:
            track_title = (track.title or "").lower()
            if STRONG_FIND:
                if track_title != title.lower() and track_title != clean.lower():
                    continue
                if track.artists:
                    names = [a.name for a in track.artists]
                    matched = False
                    for perm in permutations(names):
                        if " ".join(perm).lower() == artist.lower():
                            matched = True
                            break
                    if not matched and artist.lower() not in ", ".join(names).lower():
                        continue
                found = track
                break
            else:
                found = track
                break

        if not found and tracks:
            found = tracks[0]
        if not found:
            return None

        cover_url = f"https://{found.cover_uri.replace('%%', '400x400')}" if found.cover_uri else None
        album_title = found.albums[0].title if found.albums else None
        album_id = found.albums[0].id if found.albums else None

        track_url = None
        if found.id and album_id:
            track_url = f"https://music.yandex.ru/album/{album_id}/track/{found.id}"
        elif found.id:
            track_url = f"https://music.yandex.ru/track/{found.id}"

        return {
            "title": found.title or title,
            "artist": ", ".join([a.name for a in (found.artists or [])]) or artist,
            "album": album_title, "album_id": album_id,
            "cover_url": cover_url, "track_url": track_url,
        }
    except Exception:
        return None


# ============================================================
# ПРИЛОЖЕНИЕ
# ============================================================

class MacYandexMusicRPC(rumps.App):

    def __init__(self):
        super().__init__("🎵", quit_button="Выход")

        self.current_track = None
        self.track_identity = None
        self.rpc_connected = False
        self.rpc = None
        self.yandex_client = None
        self.logs = []
        self.last_ya = None
        self.blocked_identity = None
        self.source_log_done = {}
        self.token_set = False
        self.frozen_elapsed = 0       # Запомненная позиция при паузе
        self.frozen_duration = 0      # Запомненная длительность при паузе
        self.track_start_time = 0     # time.time() когда трек начал играть
        self.was_playing = False      # Предыдущее состояние play/pause

        self.menu = [
            rumps.MenuItem("MacYandexMusicRPC v1.8", callback=None),
            None,
            rumps.MenuItem("▶ Не играет", callback=None),
            None,
            rumps.MenuItem("🔑 Токен Яндекс Музыки", callback=self.setup_token),
            rumps.MenuItem("📋 Показать логи", callback=self.show_logs),
            rumps.MenuItem("🔄 Перезапустить RPC", callback=self.restart_rpc),
            None,
        ]

        threading.Thread(target=self.initialize, daemon=True).start()

    # === ЛОГИ ===

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self.logs.append(line)
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def show_logs(self, _=None):
        text = "\n".join(self.logs[-40:]) if self.logs else "Логов пока нет"
        rumps.alert("📋 Логи", text)

    # === ТОКЕН ===

    def setup_token(self, _=None):
        """
        GUI для управления токеном через keyring.
        Токен хранится в macOS Keychain — безопасно.
        """
        current = ""
        try:
            current = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY) or ""
        except Exception:
            pass

        hint = "Текущий токен сохранён в Keychain" if current else "Токен не задан"
        hint += "\n\nОставь пустым чтобы удалить токен"
        hint += "\n\nПолучить токен: github.com/MarshalX/yandex-music-api/discussions/513"

        response = rumps.Window(
            "🔑 Токен Яндекс Музыки\n\n" + hint,
            "Токен Яндекс Музыки",
            default_text=current if current else "",
            dimensions=(400, 80),
        ).run()

        if response.clicked:
            new_token = response.text.strip()
            if new_token:
                set_token(new_token)
                self.log("🔑 Токен сохранён в Keychain")
                self.token_set = True
                # Переподключаем Яндекс с новым токеном
                threading.Thread(target=self._reconnect_yandex, daemon=True).start()
            elif not new_token and current:
                set_token("")
                self.log("🔑 Токен удалён из Keychain")
                self._reconnect_yandex()

    def _reconnect_yandex(self):
        """Переподключаем Яндекс с новым токеном."""
        token = get_token()
        try:
            self.yandex_client = Client(token if token else None).init()
            self.log("✅ Яндекс Музыка переподключена")
        except Exception as e:
            self.log(f"⚠️ Яндекс: {e}")
            try:
                self.yandex_client = Client().init()
            except Exception:
                self.yandex_client = None

    # === ИНИЦИАЛИЗАЦИЯ ===

    def initialize(self):
        self.log("Инициализация MacYandexMusicRPC v1.8...")

        # Проверяем brew-зависимости
        check_brew_deps()

        # Токен
        token = get_token()
        if token:
            self.token_set = True
            self.log("🔑 Токен: загружен из Keychain")
        else:
            env_token = os.environ.get("YANDEX_TOKEN", "")
            if env_token:
                self.log("🔑 Токен: из .env файла")
            else:
                self.log("ℹ️ Токен не задан — поиск без авторизации")

        # Яндекс
        try:
            self.yandex_client = Client(token if token else None).init()
            self.log("✅ Яндекс Музыка подключена")
        except Exception as e:
            self.log(f"⚠️ Яндекс: {e}")
            try:
                self.yandex_client = Client().init()
            except Exception as e2:
                self.log(f"❌ Яндекс недоступна: {e2}")

        # Discord
        self.wait_for_discord()
        self.log("🚀 Мониторинг запущен")
        self.update_loop()

    def wait_for_discord(self):
        if is_discord_running():
            self.connect_discord()
            return
        self.log("⏳ Ждём Discord...")
        while True:
            time.sleep(3)
            if is_discord_running():
                self.connect_discord()
                return

    def connect_discord(self):
        try:
            if self.rpc:
                try: self.rpc.close()
                except: pass
            self.rpc = DiscordRPC(CLIENT_ID)
            self.rpc.connect()
            self.rpc_connected = True
            self.log("✅ Discord RPC подключён")
        except Exception as e:
            self.rpc_connected = False
            self.log(f"❌ Discord RPC: {e}")

    def restart_rpc(self, _=None):
        self.log("🔄 Перезапуск RPC...")
        threading.Thread(target=self.connect_discord, daemon=True).start()

    # === ОСНОВНОЙ ЦИКЛ ===

    def update_loop(self):
        while True:
            try:
                self.update_status()
            except Exception as e:
                self.log(f"❌ Ошибка: {e}")
            time.sleep(UPDATE_INTERVAL)

    def clear_rpc(self):
        self.current_track = None
        self.track_identity = None
        self.last_ya = None
        self.title = "🎵"
        self.menu["▶ Не играет"].title = "▶ Не играет"
        if self.rpc_connected:
            try: self.rpc.clear()
            except: pass

    def update_status(self):
        now = get_nowplaying()

        if not now or not now["title"]:
            if self.current_track is not None:
                self.log("⏹ Остановлено")
                self.clear_rpc()
                self.blocked_identity = None
                self.was_playing = False
            return

        title = now["title"]
        artist = now["artist"]
        album = now["album"]
        is_playing = now["is_playing"]
        elapsed = now["elapsed"]
        duration = now["duration"]
        source = now.get("source")

        # Фильтрация
        if source:
            if source not in self.source_log_done:
                self.source_log_done[source] = True
                if len(self.source_log_done) > 50:
                    self.source_log_done.clear()
                if source in YANDEX_APP_BUNDLES:
                    self.log(f"📱 {source}")
                elif source in BROWSER_BUNDLES:
                    self.log(f"🌐 {source}")
                else:
                    self.log(f"🚫 {source}")
            if source in YANDEX_APP_BUNDLES:
                pass
            elif source in BROWSER_BUNDLES:
                pass
            else:
                if self.current_track is not None:
                    self.clear_rpc()
                return

        track_identity = f"{title}||{artist}"
        track_changed = (track_identity != self.track_identity)

        # Заблокированный трек — молчим
        if track_identity == self.blocked_identity:
            return

        # Формируем ключ: трек + состояние
        track_key = f"{track_identity}||{is_playing}"

        # Тот же трек, тот же статус → ничего не делаем
        if track_key == self.current_track:
            return

        # Определяем что произошло
        just_started = (self.current_track is None)
        hit_pause = (not is_playing and self.was_playing)
        hit_resume = (is_playing and not self.was_playing)

        # Обновляем трек-идентити при смене
        if track_changed:
            self.track_identity = track_identity

        # Меню
        self.menu["▶ Не играет"].title = (
            f"{'▶' if is_playing else '⏸'} {title[:30]}{'...' if len(title)>30 else ''}"
        )
        self.title = "🎵"

        # === НА ПАУЗЕ (обновляем ОДИН раз, потом молчим) ===
        # Discord не умеет замораживать прогресс-бар — он тикает сам.
        # Как в оригинале: обновляем один раз с иконкой паузы, дальше не трогаем.
        if not is_playing:
            if hit_pause:
                # Считаем где остановились
                if self.track_start_time > 0:
                    self.frozen_elapsed = time.time() - self.track_start_time
                else:
                    self.frozen_elapsed = elapsed if elapsed > 0 else 0
                self.frozen_duration = duration if duration > 0 else 0
                self.current_track = track_key

                self.log(f"⏸ {title} — {artist}  [{format_duration(self.frozen_elapsed)} / {format_duration(self.frozen_duration)}]")

                # Обновляем Discord ОДИН раз: иконка паузы, без start/end
                if self.rpc_connected and self.last_ya is not None:
                    try:
                        ya = self.last_ya
                        lt_val = ya.get("album")
                        lt = lt_val[:128] if lt_val and lt_val != ya["title"] else None
                        btns = build_buttons(ya.get("track_url")) if ya.get("track_url") else None
                        self.rpc.update(
                            activity_type=ActivityType.LISTENING,
                            details=ya["title"][:128], state=ya["artist"][:128],
                            large_image=ya.get("cover_url") or "yandex_music",
                            large_text=lt,
                            small_image=ICON_PAUSED, small_text="На паузе",
                            buttons=btns,
                        )
                    except (PipeClosed, InvalidID, ConnectionError, OSError):
                        self.rpc_connected = False
                        self.wait_for_discord()
                    except Exception:
                        pass

            self.was_playing = False
            return

        # === ИГРАЕТ ===
        self.was_playing = True
        self.current_track = track_key

        # Поиск в Яндексе (только при смене трека)
        if track_changed or just_started:
            self.last_ya = search_yandex(self.yandex_client, title, artist) if self.yandex_client else None

        ya = self.last_ya

        if not ya and (source in BROWSER_BUNDLES or source is None):
            self.blocked_identity = track_identity
            self.log(f"🚫 Не найдено: {title}")
            self.clear_rpc()
            return

        self.blocked_identity = None

        if ya:
            dt, da, cover, url, an = ya["title"], ya["artist"], ya.get("cover_url"), ya.get("track_url"), ya.get("album")
        else:
            dt, da, cover, url, an = title, artist, None, None, album

        lt = an[:128] if an and an != dt else None
        btns = build_buttons(url) if url else None

        # Discord
        if not self.rpc_connected:
            if not is_discord_running(): return
            self.connect_discord()
        if not self.rpc_connected: return

        try:
            st = et = None
            if hit_resume and self.frozen_elapsed > 0:
                # Продолжение после паузы — с запомненной позиции
                real_elapsed = self.frozen_elapsed
            elif track_changed or just_started:
                # Новый трек
                real_elapsed = elapsed if elapsed > 0 else 0
            else:
                real_elapsed = elapsed if elapsed > 0 else 0

            real_duration = duration if duration > 0 else (self.frozen_duration if hit_resume else 0)

            if real_duration > 0:
                st = int(time.time() - real_elapsed)
                et = int(st + real_duration)

            # Запоминаем когда трек начал (для паузы)
            self.track_start_time = time.time() - real_elapsed

            self.rpc.update(
                activity_type=ActivityType.LISTENING,
                details=dt[:128], state=da[:128],
                large_image=cover or "yandex_music", large_text=lt,
                small_image=ICON_PLAYING, small_text="Проигрывается",
                start=st, end=et, buttons=btns,
            )
            if track_changed or just_started:
                self.log(f"▶ {dt} — {da}")
            elif hit_resume:
                self.log(f"▶ Продолжение: {dt}  [{format_duration(real_elapsed)} / {format_duration(real_duration)}]")
        except (PipeClosed, InvalidID, ConnectionError, OSError):
            self.rpc_connected = False
            self.wait_for_discord()
        except Exception:
            pass


# ============================================================
# ТОЧКА ВХОДА
# ============================================================

def main():
    # Проверяем что мы в macOS
    if sys.platform != "darwin":
        print("❌ Только для macOS!")
        sys.exit(1)

    print("🎵 MacYandexMusicRPC v1.8")
    print("   Иконка в menu bar — настройки через меню 🎵")

    # Запускаем (rumps приложение, без терминала)
    app = MacYandexMusicRPC()
    app.run()


if __name__ == "__main__":
    main()
