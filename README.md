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

# media-control — источник трека (обязательно для фильтрации!)
brew tap ungive/media-control
brew install media-control
```

### 2. Python зависимости

```bash
pip install -r requirements.txt
```

### 3. Запуск

```bash
python MacYandexMusicRPC.py
```

**Всё.** Зависимости установятся автоматически.

Токен Яндекс Музыки — через меню 🎵 → **🔑 Токен Яндекс Музыки**. Хранится в macOS Keychain (безопасно).

> Или через `.env` файл: `cp .env.example .env` и заполни. `YANDEX_TOKEN` необязателен, но помогает при VPN/блокировках. Получить: [инструкция](https://github.com/MarshalX/yandex-music-api/discussions/513)

## Структура проекта

```
MacYandexMusicRPC/
├── MacYandexMusicRPC.py   # Основной скрипт
├── .env.example            # Пример настроек (коммитится)
├── .env                    # Твои настройки (НЕ коммитится!)
├── .gitignore              # Запрещает .env и мусор
├── requirements.txt        # Python зависимости
├── LICENSE                 # MIT
└── README.md               # Этот файл
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
| Настройки | GUI (PyQt) + keyring | `.env` файл |
| Токен | keyring | `.env` или переменная окружения |

## Благодарности

- [FozerG](https://github.com/FozerG) — оригинальный [WinYandexMusicRPC](https://github.com/FozerG/WinYandexMusicRPC)
- [MarshalX](https://github.com/MarshalX) — [yandex-music-api](https://github.com/MarshalX/yandex-music-api)
- [ungive](https://github.com/ungive) — [media-control](https://github.com/ungive/media-control)
