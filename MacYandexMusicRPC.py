#!/usr/bin/env python3
# MacYandexMusicRPC v1.8
# https://github.com/nfsrbgames-del/MacYandexMusicRPC
# brew install nowplaying-cli
# brew tap ungive/media-control && brew install media-control

import subprocess
import time
import threading
import os
import sys
import json
import re
import shutil
import atexit
from itertools import permutations
from datetime import datetime

# .app из Finder не видит PATH из Terminal — добавляем Homebrew
def _extend_path():
    extra = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/homebrew/sbin"]
    cur = os.environ.get("PATH", "")
    parts = cur.split(os.pathsep) if cur else []
    for p in reversed(extra):
        if p not in parts:
            parts.insert(0, p)
    os.environ["PATH"] = os.pathsep.join(parts)


_extend_path()


def _resolve_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for base in ("/opt/homebrew/bin", "/usr/local/bin"):
        path = os.path.join(base, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


NOWPLAYING_CLI = _resolve_tool("nowplaying-cli")
MEDIA_CONTROL = _resolve_tool("media-control")

LOG_DIR = os.path.expanduser("~/.config/macyandexrpc")
LOG_FILE = os.path.join(LOG_DIR, "run.log")
PID_FILE = os.path.join(LOG_DIR, "app.pid")


def _file_log(line: str):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _cleanup_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def _ax_is_trusted() -> bool | None:
    """None — API недоступен."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        pass
    try:
        import ctypes
        lib = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return None


def _ax_prompt_system() -> bool:
    """Системный диалог «добавить в Универсальный доступ» (только PyObjC, без ctypes)."""
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        return True
    except Exception:
        return False


def accessibility_trusted(prompt: bool = False) -> bool:
    trusted = _ax_is_trusted()
    if trusted is True:
        return True
    if not prompt:
        return False
    if _ax_prompt_system():
        return bool(_ax_is_trusted())
    prompt_accessibility_dialog()
    trusted = _ax_is_trusted()
    return trusted is True


def prompt_accessibility_dialog():
    script = (
        'display dialog "Для Discord RPC нужен Универсальный доступ.\\n\\n'
        "Включи: MacYandexMusicRPC или Python.\\n"
        "Если не помогло — нажми + и добавь из /opt/homebrew/bin: "
        'media-control и nowplaying-cli." '
        'with title "MacYandexMusicRPC" buttons {"Открыть настройки", "Позже"} '
        "default button 1"
    )
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if "Открыть" in (r.stdout or ""):
            open_accessibility_settings()
    except Exception:
        open_accessibility_settings()


def open_accessibility_settings():
    for url in (
        "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Accessibility",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    ):
        if subprocess.run(["open", url], capture_output=True).returncode == 0:
            return


REQUIRED_PACKAGES = {
    "pypresence": "pypresence",
    "rumps": "rumps",
    "yandex_music": "yandex-music",
    "keyring": "keyring",
}


def _ensure_packages():
    missing = []
    for module, package in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return

    print(f"Устанавливаю: {', '.join(missing)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "--break-system-packages", *missing],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"Ошибка установки: {e}")
        print(f"  {sys.executable} -m pip install --break-system-packages {' '.join(missing)}")
        sys.exit(1)


_ensure_packages()

import rumps
import keyring
from pypresence import Presence as DiscordRPC, PipeClosed, InvalidID
from pypresence.types import ActivityType
from yandex_music import Client


def _load_env():
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
PAUSE_CLEAR_SEC = 5 * 60

KEYRING_SERVICE = "MacYandexMusicRPC"
KEYRING_KEY = "yandex_token"

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


def get_token():
    try:
        token = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
        if token:
            return token
    except Exception:
        pass
    return os.environ.get("YANDEX_TOKEN", "")


def set_token(token: str):
    try:
        if token:
            keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, token)
        else:
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
                ["pgrep", "-x", name], capture_output=True, timeout=2,
            )
            if result.returncode == 0:
                return True
        return False
    except Exception:
        return True


def check_brew_deps():
    missing = []
    if not NOWPLAYING_CLI:
        missing.append("nowplaying-cli")
    if not MEDIA_CONTROL:
        missing.append("media-control")

    if missing:
        msg = f"Не установлено: {', '.join(missing)}\n\n"
        if "nowplaying-cli" in missing:
            msg += "brew install nowplaying-cli\n"
        if "media-control" in missing:
            msg += "brew tap ungive/media-control && brew install media-control\n"
        msg += "\nБез них скрипт не будет работать."
        rumps.alert("Зависимости", msg)
        return False
    return True


def clean_title_feat(title: str) -> str:
    return re.sub(
        r'\(feat\.?.*?\)|\(ft\.?.*?\)|\(с участием.*?\)|\(при уч\.?.*?\)',
        '', title, flags=re.IGNORECASE,
    ).strip()


def format_duration(seconds):
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"


def trunc(s, n=128):
    if not s:
        return s
    return s[:n]


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
            print("[WARN] label кнопки > 32 байт")
    return buttons


def get_media_source():
    now = get_nowplaying_from_media_control()
    if now:
        return now.get("source")
    try:
        if not MEDIA_CONTROL:
            return None
        result = subprocess.run(
            [MEDIA_CONTROL, "get"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("bundleIdentifier") or data.get("parentApplicationBundleIdentifier")
    except Exception:
        pass
    return None


def _parse_media_control_payload(data: dict) -> dict | None:
    title = data.get("title")
    if not title:
        return None

    rate = float(data.get("playbackRate") or 0)
    if "playing" in data:
        is_playing = bool(data["playing"])
    else:
        is_playing = rate > 0

    return {
        "title": title,
        "artist": data.get("artist") or "Unknown Artist",
        "album": data.get("album"),
        "is_playing": is_playing,
        "elapsed": float(data.get("elapsedTime") or 0),
        "duration": float(data.get("duration") or 0),
        "source": data.get("bundleIdentifier") or data.get("parentApplicationBundleIdentifier"),
    }


def get_nowplaying_from_media_control() -> dict | None:
    try:
        if not MEDIA_CONTROL:
            return None
        result = subprocess.run(
            [MEDIA_CONTROL, "get"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return _parse_media_control_payload(json.loads(result.stdout))
    except Exception:
        return None


def get_nowplaying_from_nowplaying_cli() -> dict | None:
    try:
        if not NOWPLAYING_CLI:
            return None
        result = subprocess.run(
            [NOWPLAYING_CLI, "get", "title", "artist", "album",
             "playbackRate", "elapsedTime", "duration"],
            capture_output=True, text=True, timeout=3,
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

        try:
            playback_rate = float(pr)
        except ValueError:
            playback_rate = 0.0
        try:
            elapsed = float(el) if el != "null" else 0.0
        except ValueError:
            elapsed = 0.0
        try:
            duration = float(du) if du != "null" else 0.0
        except ValueError:
            duration = 0.0

        source = None
        if MEDIA_CONTROL:
            try:
                mc = subprocess.run(
                    [MEDIA_CONTROL, "get"],
                    capture_output=True, text=True, timeout=3,
                )
                if mc.returncode == 0 and mc.stdout.strip():
                    bundle_data = json.loads(mc.stdout)
                    source = (
                        bundle_data.get("bundleIdentifier")
                        or bundle_data.get("parentApplicationBundleIdentifier")
                    )
            except Exception:
                pass

        return {
            "title": title,
            "artist": artist or "Unknown Artist",
            "album": album,
            "is_playing": playback_rate > 0,
            "elapsed": elapsed,
            "duration": duration,
            "source": source,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    except Exception:
        return None


def get_nowplaying() -> dict | None:
    # media-control отдаёт всё одним JSON; nowplaying-cli — отдельный процесс, часто без доступа
    media = get_nowplaying_from_media_control()
    if media:
        return media
    return get_nowplaying_from_nowplaying_cli()


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
            "album": album_title,
            "album_id": album_id,
            "cover_url": cover_url,
            "track_url": track_url,
        }
    except Exception:
        return None


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
        self.frozen_elapsed = 0
        self.frozen_duration = 0
        self.track_start_time = 0
        self.was_playing = False
        self.paused_since = 0
        self.pause_rpc_sent = False
        self._ax_prompt_done = False

        self.menu = [
            rumps.MenuItem("MacYandexMusicRPC v1.8", callback=None),
            None,
            rumps.MenuItem("▶ Не играет", callback=None),
            None,
            rumps.MenuItem("Доступ к медиа…", callback=self.request_accessibility),
            rumps.MenuItem("Токен Яндекс Музыки", callback=self.setup_token),
            rumps.MenuItem("Показать логи", callback=self.show_logs),
            rumps.MenuItem("Перезапустить RPC", callback=self.restart_rpc),
            None,
        ]

        threading.Thread(target=self.initialize, daemon=True).start()

    @rumps.timer(1)
    def _accessibility_on_start(self, timer):
        if self._ax_prompt_done:
            return
        self._ax_prompt_done = True
        timer.stop()
        if accessibility_trusted(False):
            self.log("Универсальный доступ: OK")
            self._diagnose_media_cli()
            return
        self.log("Нужен Универсальный доступ")
        accessibility_trusted(prompt=True)
        if accessibility_trusted(False):
            self.log("Универсальный доступ: OK")
        else:
            rumps.notification(
                title="MacYandexMusicRPC",
                subtitle="Включи Универсальный доступ",
                message="MacYandexMusicRPC или Python в списке настроек",
            )
        self._diagnose_media_cli()

    def request_accessibility(self, _=None):
        if accessibility_trusted(False):
            rumps.alert("Доступ к медиа", "Универсальный доступ уже включён.")
            return
        accessibility_trusted(prompt=True)
        if accessibility_trusted(False):
            rumps.alert("Доступ к медиа", "Готово. Можно включать музыку.")
        else:
            rumps.alert(
                "Доступ к медиа",
                "Включи переключатель для MacYandexMusicRPC (или Python), "
                "затем перезапусти приложение.",
            )

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        _file_log(line)
        self.logs.append(line)
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def show_logs(self, _=None):
        text = "\n".join(self.logs[-40:]) if self.logs else "Логов пока нет"
        rumps.alert("Логи", text)

    def setup_token(self, _=None):
        current = get_token()
        hint = "Токен в Keychain" if current else "Токен не задан"
        hint += "\n\nПустое поле — удалить токен"
        hint += "\n\nhttps://github.com/MarshalX/yandex-music-api/discussions/513"

        response = rumps.Window(
            "Токен Яндекс Музыки\n\n" + hint,
            "Токен",
            default_text=current or "",
            dimensions=(400, 80),
        ).run()

        if response.clicked:
            new_token = response.text.strip()
            if new_token:
                set_token(new_token)
                self.log("Токен сохранён")
                threading.Thread(target=self._reconnect_yandex, daemon=True).start()
            elif not new_token and current:
                set_token("")
                self.log("Токен удалён")
                self._reconnect_yandex()

    def _reconnect_yandex(self):
        token = get_token()
        try:
            self.yandex_client = Client(token if token else None).init()
            self.log("Яндекс переподключена")
        except Exception as e:
            self.log(f"Яндекс: {e}")
            try:
                self.yandex_client = Client().init()
            except Exception:
                self.yandex_client = None

    def initialize(self):
        self.log("Старт v1.8")

        token = get_token()
        if token:
            self.log("Токен: Keychain")
        elif os.environ.get("YANDEX_TOKEN"):
            self.log("Токен: .env")
        else:
            self.log("Токен не задан")

        try:
            self.yandex_client = Client(token if token else None).init()
            self.log("Яндекс OK")
        except Exception as e:
            self.log(f"Яндекс: {e}")
            try:
                self.yandex_client = Client().init()
            except Exception as e2:
                self.log(f"Яндекс недоступна: {e2}")

        self.wait_for_discord()
        self.log("Мониторинг")
        self.update_loop()

    def _diagnose_media_cli(self):
        now = get_nowplaying()
        if now:
            src = f" ({now['source']})" if now.get("source") else ""
            self.log(f"Медиа OK: {now['title']} — {now['artist']}{src}")
            return

        mc = get_nowplaying_from_media_control()
        npc = get_nowplaying_from_nowplaying_cli()
        self.log(
            "Медиа пусто. Включи музыку. Если играет — меню «Доступ к медиа…» "
            "и в Универсальном доступе добавь (+): "
            f"Python, media-control, nowplaying-cli "
            f"({MEDIA_CONTROL or '?'}, {NOWPLAYING_CLI or '?'})"
        )
        if mc is None and MEDIA_CONTROL:
            self.log("media-control: нет ответа")
        if npc is None and NOWPLAYING_CLI:
            self.log("nowplaying-cli: нет ответа")

    def wait_for_discord(self):
        if is_discord_running():
            self.connect_discord()
            return
        self.log("Ждём Discord...")
        while True:
            time.sleep(3)
            if is_discord_running():
                self.connect_discord()
                return

    def connect_discord(self):
        try:
            if self.rpc:
                try:
                    self.rpc.close()
                except Exception:
                    pass
            self.rpc = DiscordRPC(CLIENT_ID)
            self.rpc.connect()
            self.rpc_connected = True
            self.log("Discord RPC OK")
        except Exception as e:
            self.rpc_connected = False
            self.log(f"Discord RPC: {e}")

    def restart_rpc(self, _=None):
        self.log("Перезапуск RPC")
        threading.Thread(target=self.connect_discord, daemon=True).start()

    def update_loop(self):
        while True:
            try:
                self.update_status()
            except Exception as e:
                self.log(f"Ошибка: {e}")
            time.sleep(UPDATE_INTERVAL)

    def _elapsed_from_system(self, reported):
        if reported and reported > 0:
            return float(reported)
        if self.track_start_time > 0:
            return max(0.0, time.time() - self.track_start_time)
        return max(0.0, self.frozen_elapsed)

    def _duration_from_system(self, reported):
        if reported and reported > 0:
            return float(reported)
        return max(0.0, self.frozen_duration)

    def _pause_too_long(self):
        return bool(self.paused_since and time.time() - self.paused_since > PAUSE_CLEAR_SEC)

    def _send_paused_presence(self):
        # Как WinYandexMusicRPC: без start/end (полоска пропадает), время — текстом
        if not self.last_ya or self.pause_rpc_sent:
            return
        if not is_discord_running():
            return
        if not self.rpc_connected:
            self.connect_discord()
        if not self.rpc_connected:
            return

        ya = self.last_ya
        elapsed = self.frozen_elapsed
        duration = self.frozen_duration
        time_label = None
        if duration > 0:
            time_label = f"На паузе {format_duration(elapsed)} / {format_duration(duration)}"

        try:
            lt_val = ya.get("album")
            lt = trunc(lt_val) if lt_val and lt_val != ya["title"] else None
            if time_label and elapsed > 0:
                lt = time_label
            btns = build_buttons(ya.get("track_url")) if ya.get("track_url") else None
            kwargs = dict(
                activity_type=ActivityType.LISTENING,
                details=trunc(ya["title"]),
                state=trunc(ya["artist"]),
                large_image=ya.get("cover_url") or "yandex_music",
                large_text=lt,
                small_image=ICON_PAUSED,
                small_text=time_label or "На паузе",
                buttons=btns,
            )
            self.rpc.update(**kwargs)
            self.pause_rpc_sent = True
        except (PipeClosed, InvalidID, ConnectionError, OSError):
            self.rpc_connected = False
            threading.Thread(target=self.wait_for_discord, daemon=True).start()
        except Exception:
            pass

    def clear_rpc(self):
        self.current_track = None
        self.track_identity = None
        self.last_ya = None
        self.paused_since = 0
        self.pause_rpc_sent = False
        self.title = "🎵"
        self.menu["▶ Не играет"].title = "▶ Не играет"
        if self.rpc_connected:
            try:
                self.rpc.clear()
            except Exception:
                pass

    def update_status(self):
        now = get_nowplaying()

        if not now or not now["title"]:
            if self.current_track is not None:
                self.log("Остановлено")
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

        if source:
            if source not in self.source_log_done:
                self.source_log_done[source] = True
                if len(self.source_log_done) > 50:
                    self.source_log_done.clear()
                if source in YANDEX_APP_BUNDLES:
                    self.log(f"app {source}")
                elif source in BROWSER_BUNDLES:
                    self.log(f"browser {source}")
                else:
                    self.log(f"block {source}")
            if source not in YANDEX_APP_BUNDLES and source not in BROWSER_BUNDLES:
                if self.current_track is not None:
                    self.clear_rpc()
                return

        track_identity = f"{title}||{artist}"
        track_changed = track_identity != self.track_identity

        if track_identity == self.blocked_identity:
            return

        track_key = f"{track_identity}||{is_playing}"

        if track_key == self.current_track:
            if not is_playing and self._pause_too_long():
                self.log("Пауза > 5 мин")
                self.clear_rpc()
                self.blocked_identity = None
                self.was_playing = False
            return

        just_started = self.current_track is None
        hit_pause = not is_playing and self.was_playing
        hit_resume = is_playing and not self.was_playing

        if track_changed:
            self.track_identity = track_identity

        self.menu["▶ Не играет"].title = (
            f"{'▶' if is_playing else '⏸'} {title[:30]}{'...' if len(title) > 30 else ''}"
        )
        self.title = "🎵"

        if not is_playing:
            if hit_pause:
                self.frozen_elapsed = self._elapsed_from_system(elapsed)
                self.frozen_duration = self._duration_from_system(duration)
                self.current_track = track_key
                self.paused_since = time.time()
                self.pause_rpc_sent = False

                self.log(
                    f"Пауза {title} — {artist}  "
                    f"[{format_duration(self.frozen_elapsed)} / {format_duration(self.frozen_duration)}]"
                )
                self._send_paused_presence()

            self.was_playing = False
            return

        self.paused_since = 0
        self.pause_rpc_sent = False
        self.was_playing = True
        self.current_track = track_key

        if track_changed or just_started:
            self.last_ya = search_yandex(self.yandex_client, title, artist) if self.yandex_client else None

        ya = self.last_ya

        if not ya and (source in BROWSER_BUNDLES or source is None):
            self.blocked_identity = track_identity
            self.log(f"Не найдено: {title}")
            self.clear_rpc()
            return

        self.blocked_identity = None

        if ya:
            dt = ya["title"]
            da = ya["artist"]
            cover = ya.get("cover_url")
            url = ya.get("track_url")
            an = ya.get("album")
        else:
            dt, da, cover, url, an = title, artist, None, None, album

        lt = trunc(an) if an and an != dt else None
        btns = build_buttons(url) if url else None

        if not self.rpc_connected:
            if not is_discord_running():
                return
            self.connect_discord()
        if not self.rpc_connected:
            return

        try:
            st = et = None
            if hit_resume:
                sys_el = self._elapsed_from_system(elapsed)
                real_elapsed = sys_el if sys_el > 0 else self.frozen_elapsed
            else:
                real_elapsed = self._elapsed_from_system(elapsed)

            real_duration = self._duration_from_system(duration)

            if real_duration > 0:
                st = int(time.time() - real_elapsed)
                et = int(st + real_duration)

            self.track_start_time = time.time() - real_elapsed

            self.rpc.update(
                activity_type=ActivityType.LISTENING,
                details=trunc(dt),
                state=trunc(da),
                large_image=cover or "yandex_music",
                large_text=lt,
                small_image=ICON_PLAYING,
                small_text="Проигрывается",
                start=st,
                end=et,
                buttons=btns,
            )
            if track_changed or just_started:
                self.log(f"▶ {dt} — {da}")
            elif hit_resume:
                self.log(
                    f"Продолжение: {dt}  "
                    f"[{format_duration(real_elapsed)} / {format_duration(real_duration)}]"
                )
        except (PipeClosed, InvalidID, ConnectionError, OSError):
            self.rpc_connected = False
            self.wait_for_discord()
        except Exception:
            pass


def main():
    if sys.platform != "darwin":
        print("Только macOS")
        sys.exit(1)

    try:
        import AppKit
        AppKit.NSApp.setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )
    except Exception:
        pass

    if not check_brew_deps():
        sys.exit(1)

    atexit.register(_cleanup_pid)
    _file_log("--- запуск ---")
    print("MacYandexMusicRPC v1.8 — иконка в menu bar", flush=True)
    try:
        MacYandexMusicRPC().run()
    except Exception as e:
        _file_log(f"FATAL: {e}")
        try:
            rumps.alert("MacYandexMusicRPC", f"Ошибка запуска:\n{e}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
