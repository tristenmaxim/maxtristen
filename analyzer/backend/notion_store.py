import mimetypes
import os
import httpx

TOKEN = os.getenv('NOTION_TOKEN', '')
DATABASE = os.getenv('NOTION_DATABASE_ID', '')
BASE = 'https://api.notion.com/v1'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Notion-Version': '2025-09-03'}


def request(method, path, **kwargs):
    response = httpx.request(method, BASE + path, headers=HEADERS, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def rich(text):
    return [{'type': 'text', 'text': {'content': text[i:i + 1900]}} for i in range(0, len(text), 1900)]


def create_entry(url, source):
    properties = {
        'Название': {'title': rich('Обработка материала')},
        'Источник': {'select': {'name': source}},
        'Статус': {'select': {'name': 'Обработка'}},
    }
    if url:
        properties['Ссылка'] = {'url': url}
    return request('POST', '/pages', json={'parent': {'database_id': DATABASE}, 'properties': properties})


def update_entry(page_id, title, description, tags, status, source=None):
    properties = {
        'Название': {'title': rich(title[:1900])},
        'Описание': {'rich_text': rich(description[:1900])},
        'Теги': {'multi_select': [{'name': t[:80]} for t in tags[:8] if t and ',' not in t]},
        'Статус': {'select': {'name': status}},
    }
    if source:
        properties['Источник'] = {'select': {'name': source}}
    request('PATCH', '/pages/' + page_id, json={'properties': properties})


def set_status(page_id, status):
    request('PATCH', '/pages/' + page_id, json={'properties': {'Статус': {'select': {'name': status}}}})


def append_text(page_id, heading, text):
    blocks = [{'object': 'block', 'type': 'heading_2', 'heading_2': {'rich_text': rich(heading)}}]
    blocks += [{'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': rich(text[i:i + 1900])}} for i in range(0, len(text), 1900)]
    for i in range(0, len(blocks), 90):
        request('PATCH', f'/blocks/{page_id}/children', json={'children': blocks[i:i + 90]})


def append_file(page_id, path):
    mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    upload = request('POST', '/file_uploads', json={'filename': os.path.basename(path), 'content_type': mime})
    with open(path, 'rb') as f:
        request('POST', '/file_uploads/' + upload['id'] + '/send', files={'file': (os.path.basename(path), f, mime)})
    kind = 'video' if mime.startswith('video/') else 'image' if mime.startswith('image/') else 'file'
    block = {'object': 'block', 'type': kind, kind: {'type': 'file_upload', 'file_upload': {'id': upload['id']}}}
    request('PATCH', f'/blocks/{page_id}/children', json={'children': [block]})
