import json
import os
import re
import subprocess
from urllib.parse import urlparse

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
    return 'Другое' if url else 'Telegram'


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
    template = os.path.join(workdir, 'part-%04d.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', 'scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2', '-c:v', 'libx264', '-preset', 'fast', '-b:v', '400k', '-maxrate', '400k', '-bufsize', '800k', '-c:a', 'aac', '-b:a', '64k', '-f', 'segment', '-segment_time', '45', '-force_key_frames', 'expr:gte(t,n_forced*45)', '-reset_timestamps', '1', template], check=True, timeout=1800)
    parts = sorted(os.path.join(workdir, x) for x in os.listdir(workdir) if re.fullmatch(r'part-\d+\.mp4', x))
    if not parts or any(os.path.getsize(x) > MAX_FILE for x in parts):
        raise ValueError('Не удалось разбить видео на файлы меньше 5 МБ')
    return parts


def describe(text, images=()):
    prompt = ('Проанализируй материал. Верни только JSON с полями title, summary и tags (массив из 2–6 кратких тегов на русском). Не выдумывай факты. Материал:\n' + text[:30000])
    contents = [prompt]
    for image in images:
        contents.append(gemini._client.files.upload(file=image))
    result = gemini.generate(contents=contents, config={'response_mime_type': 'application/json', 'temperature': 0.2})
    data = json.loads(result.text)
    return str(data.get('title') or 'Материал'), str(data.get('summary') or ''), [str(x) for x in data.get('tags', []) if isinstance(x, str)]


def upload_media(page_id, paths, directory):
    for i, path in enumerate(paths):
        workdir = os.path.join(directory, f'prepared-{i}')
        os.makedirs(workdir, exist_ok=True)
        for part in files_for_notion(path, workdir):
            notion_store.append_file(page_id, part)
