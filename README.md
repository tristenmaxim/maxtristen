# maxtristen

Личный набор веб-инструментов, один сайт с разделами:

- `music/` — плеер фоновой музыки поверх YouTube-плейлиста (статика)
- `photo/` — AI-обработка изображений через OpenRouter (FastAPI)
- `downloader/` — скачивание видео с YouTube/TikTok/Instagram через yt-dlp (Express)

Живёт на `https://maxtristen.com/`.

## Деплой

Push в `main` → `.github/workflows/deploy.yml` синкает репо на сервер, ставит зависимости,
рестартует `maxtristen-photo`/`maxtristen-downloader` (systemd) и перекладывает nginx-конфиг.
Конфиги — в `deploy/`.

Реальные `.env` на сервере кладутся вручную (`scp`), в репозиторий не попадают — см.
`photo/backend/.env.example` для списка нужных переменных. Так же `music/assets/config.local.js`
(см. `config.local.js.example`) — YouTube API key.

## Локальный запуск

```bash
# photo
cd photo/backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env  # вписать OPENROUTER_API_KEY
venv/bin/uvicorn main:app --reload --port 8001

# downloader (нужен yt-dlp и ffmpeg в PATH)
cd downloader/backend && npm install
PORT=8003 node server.js

# music — статика, открыть music/index.html или python3 -m http.server
```
