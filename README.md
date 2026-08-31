# maxtristen

Личный набор веб-инструментов, один сайт с разделами:

- `music/` — плеер фоновой музыки поверх YouTube-плейлиста (статика)
- `music/generated/` — генератор лоу-фай и фоновой музыки на Strudel: гармония, ритм и мелодия
  считаются в браузере, записей нет (статика, без бэкенда). Аккорды строит встроенный словарь
  вольтовок iReal из `@strudel/tonal`; приёмы взяты из примеров Strudel (tunes.mjs, Felix Roos,
  CC BY-NC-SA 4.0) — сайт некоммерческий, атрибуция в футере страницы. Барабаны — машинные
  наборы tidal-drum-machines и лоу-фай крейт eddyflux/crate. Есть «живой режим»:
  партитура на весь экран с подсветкой звучащего такта, ручки прямо в тексте, сетка снизу
- `photo/` — AI-обработка изображений через OpenRouter (FastAPI)
- `downloader/` — скачивание видео с YouTube/TikTok/Instagram через yt-dlp (Express)
- `analyzer/` — библиотека видео с автотранскрибацией через Gemini (FastAPI), приём через веб-форму
  или Telegram-бота (webhook), скачивание по ссылке идёт через `downloader/`

Живёт на `https://maxtristen.com/`.

## Деплой

Push в `main` → `.github/workflows/deploy.yml` синкает репо на сервер, ставит зависимости,
рестартует `maxtristen-photo`/`maxtristen-downloader`/`maxtristen-analyzer` (systemd) и перекладывает
nginx-конфиг. Конфиги — в `deploy/`.

Реальные `.env` на сервере кладутся вручную (`scp`), в репозиторий не попадают — см.
`photo/backend/.env.example` / `analyzer/backend/.env.example` для списка нужных переменных. Так же
`music/assets/config.local.js` (см. `config.local.js.example`) — YouTube API key.

Данные `analyzer/` (SQLite + видеофайлы) живут вне репозитория, на сервере в
`/opt/maxtristen-data/analyzer/` — создаётся один раз вручную (`mkdir -p`), деплой их не трогает.
Webhook Telegram-бота регистрируется один раз: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://maxtristen.com/analyzer/telegram-webhook"`.

## Локальный запуск

```bash
# photo
cd photo/backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env  # вписать OPENROUTER_API_KEY
venv/bin/uvicorn main:app --reload --port 8001

# downloader (нужен yt-dlp и ffmpeg в PATH)
cd downloader/backend && npm install
PORT=8003 node server.js

# analyzer (downloader должен быть запущен для скачивания по ссылке)
cd analyzer/backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env  # вписать GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID
venv/bin/uvicorn main:app --reload --port 8004

# music — статика, открыть music/index.html или python3 -m http.server
```
