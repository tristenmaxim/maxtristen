import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx

import gemini
import notion_store

MAX_FILE = 4_500_000


def source_for(url):
    host = urlparse(url or '').hostname or ''
    if host == 'tiktok.com' or host.endswith('.tiktok.com'):
        return 'TikTok'
    if host in ('x.com', 'twitter.com', 'www.x.com', 'www.twitter.com', 'mobile.twitter.com'):
        return 'X'
    if host == 'instagram.com' or host.endswith('.instagram.com'):
        return 'Instagram'
    if youtube_url(url):
        return 'YouTube'
    return 'Другое' if url else 'Telegram'


def youtube_url(url):
    parsed = urlparse(url or '')
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https'):
        return None
    if host in ('youtu.be', 'www.youtu.be'):
        video_id = parsed.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        parts = parsed.path.strip('/').split('/')
        if parts[0] in ('shorts', 'live', 'embed') and len(parts) > 1:
            video_id = parts[1]
        elif parsed.path.rstrip('/') == '/watch':
            video_id = parse_qs(parsed.query).get('v', [''])[0]
        else:
            return None
    else:
        return None
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        return None
    return f'https://www.youtube.com/watch?v={video_id}'


def youtube_metadata(url):
    selection = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc1]/best'
    try:
        result = subprocess.run(['yt-dlp', '--no-playlist', '--ignore-config', '--skip-download',
                                 '--dump-single-json', '-f', selection, '--impersonate', 'chrome', youtube_url(url)],
                                capture_output=True, text=True, check=True, timeout=90)
        info = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {'size': None, 'duration': None, 'title': None}
    formats = info.get('requested_formats') or []
    sizes = [f.get('filesize') or f.get('filesize_approx') for f in formats]
    size = sum(sizes) if sizes and all(isinstance(x, (int, float)) and x > 0 for x in sizes) else info.get('filesize') or info.get('filesize_approx')
    if not isinstance(size, (int, float)) or size <= 0:
        size = None
    duration = info.get('duration')
    if not isinstance(duration, (int, float)) or not 0 < duration < 604800:
        duration = None
    return {'size': int(size) if size else None, 'duration': float(duration) if duration else None,
            'title': str(info.get('title') or '')[:500] or None}


def tweet(url, directory):
    match = re.search(r'/(?:status|statuses)/(\d+)', urlparse(url).path)
    if not match:
        raise ValueError('Не удалось определить номер публикации X')
    response = httpx.get(f'https://api.fxtwitter.com/status/{match.group(1)}', headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=30)
    response.raise_for_status()
    post = response.json().get('tweet')
    if not post:
        raise ValueError('Публикация X недоступна')
    text = post.get('text') or ''
    paths = []
    for index, item in enumerate((post.get('media') or {}).get('all') or []):
        media_url = item.get('url')
        if not media_url or item.get('type') not in ('photo', 'video', 'gif'):
            continue
        ext = '.jpg' if item['type'] == 'photo' else '.mp4'
        path = os.path.join(directory, f'x-{index}{ext}')
        with httpx.stream('GET', media_url, headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=120) as result:
            result.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in result.iter_bytes():
                    f.write(chunk)
        paths.append(path)
    return text, paths


def instagram(url, directory):
    extracted = subprocess.run(['/usr/bin/python3', os.path.join(os.path.dirname(__file__), 'instagram_extract.py'), url],
                               capture_output=True, text=True, check=True, timeout=120)
    data = json.loads(extracted.stdout)
    paths = []
    for index, item in enumerate(data['media']):
        ext = '.jpg' if item['type'] == 'image' else '.mp4'
        path = os.path.join(directory, f'instagram-{index}{ext}')
        with httpx.stream('GET', item['url'], headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.instagram.com/'},
                          follow_redirects=True, timeout=120) as result:
            result.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in result.iter_bytes():
                    f.write(chunk)
        paths.append(path)
    return data['text'], paths


def tiktok_photo_url(url):
    parsed = urlparse(url)
    if '/photo/' in parsed.path:
        return url
    if '/video/' in parsed.path:
        return None
    response = httpx.head(url, headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=30)
    final = str(response.url)
    return final if '/photo/' in urlparse(final).path else None


def tiktok_photos(url, directory):
    result = subprocess.run([sys.executable, '-m', 'gallery_dl', '-j', url],
                            capture_output=True, text=True, check=True, timeout=120)
    records = json.loads(result.stdout)
    text = next((r[-1].get('desc', '') for r in records if r[0] == 2 and isinstance(r[-1], dict)), '')
    paths = []
    allowed = {'jpeg': 'jpg', 'jpg': 'jpg', 'png': 'png', 'webp': 'webp',
               'mp3': 'mp3', 'm4a': 'm4a', 'mp4': 'mp4', 'ogg': 'ogg'}
    for record in records:
        if record[0] != 3 or not isinstance(record[-1], dict):
            continue
        extension = allowed.get(str(record[-1].get('extension', '')).lower())
        if not extension:
            raise ValueError('Неподдерживаемый формат медиа в фотопосте TikTok')
        path = os.path.join(directory, f'tiktok-{len(paths):04d}.{extension}')
        with httpx.stream('GET', record[1], headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.tiktok.com/'},
                          follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        paths.append(path)
    if not paths:
        raise ValueError('Фотопост TikTok не содержит доступных файлов')
    return text, paths


def files_for_notion(path, workdir):
    if os.path.getsize(path) <= MAX_FILE:
        return [path]
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.webp'):
        target = os.path.join(workdir, 'compressed.jpg')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', 'scale=1600:1600:force_original_aspect_ratio=decrease', '-q:v', '5', target], check=True, timeout=120)
        if os.path.getsize(target) > MAX_FILE:
            raise ValueError('Не удалось уменьшить изображение до 5 МБ')
        return [target]
    if ext in ('.mp3', '.m4a', '.aac', '.wav', '.ogg'):
        template = os.path.join(workdir, 'audio-%04d.m4a')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vn', '-c:a', 'aac', '-b:a', '64k', '-f', 'segment', '-segment_time', '420', '-reset_timestamps', '1', template], check=True, timeout=1800)
        parts = sorted(os.path.join(workdir, x) for x in os.listdir(workdir) if re.fullmatch(r'audio-\d+\.m4a', x))
        if not parts or any(os.path.getsize(x) > MAX_FILE for x in parts):
            raise ValueError('Не удалось разбить аудио на файлы меньше 5 МБ')
        return parts
    template = os.path.join(workdir, 'part-%04d.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', 'scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2', '-c:v', 'libx264', '-preset', 'fast', '-b:v', '400k', '-maxrate', '400k', '-bufsize', '800k', '-c:a', 'aac', '-b:a', '64k', '-f', 'segment', '-segment_time', '45', '-force_key_frames', 'expr:gte(t,n_forced*45)', '-reset_timestamps', '1', template], check=True, timeout=1800)
    parts = sorted(os.path.join(workdir, x) for x in os.listdir(workdir) if re.fullmatch(r'part-\d+\.mp4', x))
    if not parts or any(os.path.getsize(x) > MAX_FILE for x in parts):
        raise ValueError('Не удалось разбить видео на файлы меньше 5 МБ')
    return parts


def describe(text, media=()):
    prompt = ('Проанализируй весь материал: видео, изображения, видимый на них текст, аудио и расшифровку. '
              'Учитывай смысл изображения даже если на аудио только музыка. Утверждения авторов передавай как их слова, '
              'не выдавай за проверенные факты и не выдумывай детали. Верни JSON с полями title, summary, '
              'tags (2–6 коротких тегов на русском) и visual_text (значимый видимый текст на языке оригинала; '
              'пустая строка, если текста нет или он неразборчив). Расшифровка и текст публикации:\n' + text[:30000])
    contents = [prompt]
    uploaded = []
    try:
        for path in media:
            item = gemini._client.files.upload(file=path)
            uploaded.append(item)
            deadline = time.monotonic() + 600
            while item.state.name == 'PROCESSING' and time.monotonic() < deadline:
                time.sleep(3)
                item = gemini._client.files.get(name=item.name)
            if item.state.name != 'ACTIVE':
                raise RuntimeError(f'Не удалось подготовить медиа для анализа: {item.state.name}')
            contents.append(item)
        result = gemini.generate(contents=contents, config={'response_mime_type': 'application/json', 'temperature': 0.2})
        data = json.loads(result.text)
        tags = [str(x) for x in data.get('tags', []) if isinstance(x, str)]
        return str(data.get('title') or 'Материал'), str(data.get('summary') or ''), tags, str(data.get('visual_text') or '')
    finally:
        for item in uploaded:
            try:
                gemini._client.files.delete(name=item.name)
            except Exception:
                pass


def upload_media(page_id, paths, directory, saved=0, on_saved=None):
    position = 0
    for i, path in enumerate(paths):
        workdir = os.path.join(directory, f'prepared-{i}')
        os.makedirs(workdir, exist_ok=True)
        for part in files_for_notion(path, workdir):
            position += 1
            if position <= saved:
                continue
            notion_store.append_file(page_id, part)
            if on_saved:
                on_saved(position)
