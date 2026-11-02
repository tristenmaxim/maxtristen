import json
import ipaddress
import os
import re
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx
import trafilatura
from lxml import html as lxml_html

import gemini
import notion_store

MAX_FILE = 4_500_000


def webpage(url):
    """Retrieve and extract readable text from a public HTML page."""
    with httpx.Client(follow_redirects=False, timeout=30, trust_env=False,
                      headers={'User-Agent': 'MeaninglyBot/1.0 (web page reader)'}) as client:
        for _ in range(6):
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Некорректная ссылка на страницу')
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise ValueError('Страница должна находиться в публичной сети')
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                if 'text/html' not in response.headers.get('content-type', '').lower():
                    raise ValueError('Ссылка ведёт не на HTML-страницу')
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 5_000_000:
                        raise ValueError('Страница слишком большая для обработки')
            text = trafilatura.extract(bytes(data), include_comments=False, include_tables=True)
            if not text or not text.strip():
                raise ValueError('Не удалось извлечь текст страницы: возможно, она недоступна без входа или загружается через JavaScript')
            return text.strip()
    raise ValueError('Слишком много перенаправлений страницы')


def source_for(url):
    host = urlparse(url or '').hostname or ''
    if host in ('t.me', 'www.t.me', 'telegram.me', 'www.telegram.me'):
        return 'Telegram'
    if host == 'tiktok.com' or host.endswith('.tiktok.com'):
        return 'TikTok'
    if host in ('x.com', 'twitter.com', 'www.x.com', 'www.twitter.com', 'mobile.twitter.com'):
        return 'X'
    if host == 'instagram.com' or host.endswith('.instagram.com'):
        return 'Instagram'
    if youtube_url(url):
        return 'YouTube'
    return 'Другое' if url else 'Telegram'


def telegram_post(url, directory):
    parsed = urlparse(url)
    match = re.fullmatch(r'/([A-Za-z][A-Za-z0-9_]{3,31})/(\d+)/?', parsed.path)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('t.me', 'www.t.me', 'telegram.me', 'www.telegram.me') or not match:
        raise ValueError('Поддерживаются только ссылки на публичные публикации Telegram')
    channel, post_id = match.groups()
    response = httpx.get(f'https://t.me/{channel}/{post_id}', params={'embed': '1'},
                         headers={'User-Agent': 'Mozilla/5.0'}, timeout=30, follow_redirects=False)
    response.raise_for_status()
    doc = lxml_html.fromstring(response.content, parser=lxml_html.HTMLParser(encoding='utf-8'))
    posts = doc.xpath('//*[@data-post]')
    if len(posts) != 1 or posts[0].get('data-post', '').lower() != f'{channel}/{post_id}'.lower():
        raise ValueError('Публикация Telegram недоступна или закрыта')
    post = posts[0]
    class_match = lambda name: f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"
    unsupported = ('tgme_widget_message_document_wrap', 'tgme_widget_message_voice_wrap',
                   'tgme_widget_message_audio_wrap', 'tgme_widget_message_poll',
                   'tgme_widget_message_unsupported')
    if any(post.xpath(f'.//*[{class_match(name)}]') for name in unsupported):
        raise ValueError('Формат вложения Telegram пока не поддерживается')
    text_nodes = post.xpath(f'.//*[{class_match("tgme_widget_message_text")}]')
    for node in text_nodes:
        for br in node.xpath('.//br'):
            br.tail = '\n' + (br.tail or '')
        for link in node.xpath('.//a[@href]'):
            href = link.get('href', '')
            if href.startswith(('http://', 'https://')) and href not in link.text_content():
                link.tail = f' ({href})' + (link.tail or '')
    text = '\n\n'.join(n.text_content().strip() for n in text_nodes).strip()
    media_urls = []
    for video in post.xpath(f'.//video[{class_match("tgme_widget_message_video")}][@src]'):
        media_urls.append((video.get('src'), '.mp4'))
    for photo in post.xpath(f'.//*[{class_match("tgme_widget_message_photo_wrap")}][@style]'):
        found = re.search(r"url\(['\"]?(.*?)['\"]?\)", photo.get('style'))
        if not found:
            raise ValueError('Не удалось получить изображение Telegram')
        media_urls.append((found.group(1), '.jpg'))
    if (post.xpath(f'.//*[{class_match("tgme_widget_message_video_wrap")}]') and not
            post.xpath(f'.//video[{class_match("tgme_widget_message_video")}][@src]')):
        raise ValueError('Не удалось получить видео Telegram')
    if len(post.xpath(f'.//*[{class_match("tgme_widget_message_photo_wrap")}]')) != len(
            post.xpath(f'.//*[{class_match("tgme_widget_message_photo_wrap")}][@style]')):
        raise ValueError('Не удалось получить изображение Telegram')
    if not text and not media_urls:
        raise ValueError('Не удалось получить содержимое публикации Telegram')
    paths = []
    for i, (media_url, ext) in enumerate(media_urls):
        host = urlparse(media_url).hostname or ''
        if urlparse(media_url).scheme != 'https' or not (host.endswith('.telesco.pe') or host.endswith('.cdn-telegram.org')):
            raise ValueError('Неожиданный адрес медиа Telegram')
        path = os.path.join(directory, f'telegram-{i}{ext}')
        with httpx.stream('GET', media_url, timeout=120, follow_redirects=False) as media:
            media.raise_for_status()
            with open(path, 'wb') as output:
                for chunk in media.iter_bytes():
                    output.write(chunk)
        paths.append(path)
    return text, paths


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
              'не выдавай за проверенные факты и не выдумывай детали. Верни один JSON-объект с полями title, summary, '
              'tags (2–6 коротких тегов на русском) и visual_text (значимый видимый текст на языке оригинала; '
              'пустая строка, если текста нет или он неразборчив). '
              + ('Далее только начало длинного текста, не додумывай его продолжение. ' if len(text) > 30000 else '')
              + 'Расшифровка и текст публикации:\n' + text[:30000])
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
        if isinstance(data, list):
            if not data or any(not isinstance(item, dict) for item in data):
                raise ValueError('Модель вернула некорректный результат анализа')
            data = {
                'title': next((item.get('title') for item in data if item.get('title')), ''),
                'summary': '\n\n'.join(str(item['summary']) for item in data if item.get('summary')),
                'tags': list(dict.fromkeys(tag for item in data for tag in (item.get('tags') if isinstance(item.get('tags'), list) else []) if isinstance(tag, str))),
                'visual_text': '\n\n'.join(str(item['visual_text']) for item in data if item.get('visual_text')),
            }
        if not isinstance(data, dict):
            raise ValueError('Модель вернула некорректный результат анализа')
        tags = [x for x in data.get('tags', []) if isinstance(x, str)] if isinstance(data.get('tags'), list) else []
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
