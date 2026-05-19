# 🎵 MacYandexMusicRPC

macOS версия [WinYandexMusicRPC](https://github.com/FozerG/WinYandexMusicRPC) by FozerG.

Discord Rich Presence для отображения музыки из Яндекс Музыки (и других источников) в Discord.

![macOS](https://img.shields.io/badge/OS-macOS-blue?logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)

## Что умеет

- Показывает «Слушает Яндекс Музыку» вместо «играет в»
- Название трека, артист, обложка, альбом
- Прогресс-бар с таймером
- Иконка play/pause у обложки
- Кнопки «Откр. в браузере» и «Откр. в прилож.» (deep link)
- Фильтрация по источнику — только Яндекс Музыка и браузеры
- Иконка в menu bar macOS

## Установка

### 1. Зависимости системы

```bash
# nowplaying-cli — трек из системы
brew install nowplaying-cli

# media-control — источник трека (для фильтрации)
brew tap ungive/media-control
brew install media-control
```

### 2. Python зависимости

```bash
pip install -r requirements.txt
```

### 3. Запуск

**Без окна Terminal:** двойной клик по `MacYandexMusicRPC.app` (только иконка 🎵 в menu bar).

При первом запуске macOS покажет запрос **Универсального доступа** (нужен `nowplaying-cli`, чтобы читать «Сейчас играет»). Если пропустил — меню 🎵 → **Доступ к медиа…**

Из **Terminal** раньше могло работать без отдельного запроса: разрешение было у **Terminal.app**, а не у MacYandexMusicRPC.

Логи: `~/.config/macyandexrpc/run.log`

Или:

```bash
git clone https://github.com/nfsrbgames-del/MacYandexMusicRPC.git
cd MacYandexMusicRPC
bash setup.command    # brew: nowplaying-cli, media-control + .env
open -gj MacYandexMusicRPC.app
```

`python MacYandexMusicRPC.py` — для отладки (виден вывод в Terminal).

`run_music_rpc.command` — открывает `.app`, если есть; иначе фоновый запуск.

pip-зависимости ставятся при **первом** запуске скрипта. `setup.command` нужен для **brew**-утилит (их Python сам не поставит).

### Настройки (меню 🎵)

- **Токен Яндекс Музыки** — macOS Keychain (или `YANDEX_TOKEN` в `.env`)
- **Показать логи** / **Перезапустить RPC**

**Строгий поиск** (`STRONG_FIND` в `.env`) — как у [WinYandexMusicRPC](https://github.com/FozerG/WinYandexMusicRPC): при `true` в Discord попадает только точное совпадение с Яндексом; при `false` — первый результат поиска (удобно для VK/Spotify в браузере, но бывают ошибки).

Токен необязателен, но помогает при VPN. Получить: [инструкция](https://github.com/MarshalX/yandex-music-api/discussions/513)

```bash
cp .env.example .env   # CLIENT_ID, STRONG_FIND, UPDATE_INTERVAL
```

## Структура проекта

```
MacYandexMusicRPC/
├── MacYandexMusicRPC.py
├── MacYandexMusicRPC.app   # запуск без Terminal
├── setup.command           # brew + автозапуск
├── run_music_rpc.command
├── .env.example
├── requirements.txt
├── LICENSE
└── README.md
```

## Фильтрация источников

| Источник | bundleIdentifier | Результат |
|----------|------------------|-----------|
| Приложение Яндекс Музыки | `ru.yandex.desktop.music` | ✅ Показывает сразу |
| Яндекс Музыка в браузере | `com.google.Chrome` и т.д. | ✅ Показывает если найдено в Яндексе |
| YouTube / прочее | `com.google.Chrome` | 🚫 Блокирует (не найдено в Яндексе) |
| Telegram / другое приложение | `ru.telegram.macOS` | 🚫 Блокирует сразу |

Узнать bundleIdentifier приложения: `media-control get` (пока играет музыка)

## Отличия от оригинала (Windows)

| | Windows (оригинал) | macOS (эта версия) |
|---|---|---|
| Медиа-контроль | `Windows.Media.Control` | `nowplaying-cli` + `media-control` |
| Трей | `pystray` | `rumps` (menu bar) |
| Определение приложения | WinRT session | `media-control` bundleIdentifier |
| Настройки | GUI (PyQt) + keyring | menu bar + `.env` |
| Токен | keyring | Keychain + `.env` |

## Благодарности

- [FozerG](https://github.com/FozerG) — оригинальный [WinYandexMusicRPC](https://github.com/FozerG/WinYandexMusicRPC)
- [MarshalX](https://github.com/MarshalX) — [yandex-music-api](https://github.com/MarshalX/yandex-music-api)
- [ungive](https://github.com/ungive) — [media-control](https://github.com/ungive/media-control)
