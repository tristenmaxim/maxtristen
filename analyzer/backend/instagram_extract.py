import json
import sys

import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE
from yt_dlp.networking.impersonate import ImpersonateTarget


original_extract = InstagramIE._extract_product_media


def extract_media(self, media):
    info = original_extract(self, media)
    if not info['formats'] and info['thumbnails']:
        info['_meaningly_image'] = True
        info['formats'] = [{'url': info['thumbnails'][-1]['url']}]
    return info


InstagramIE._extract_product_media = extract_media
options = {'quiet': True, 'no_warnings': True, 'skip_download': True,
           'impersonate': ImpersonateTarget.from_str('chrome')}
with yt_dlp.YoutubeDL(options) as downloader:
    result = downloader.extract_info(sys.argv[1], download=False, process=False)
    media = []
    for entry in result.get('entries') or [result]:
        formats = entry.get('formats') or []
        if formats:
            best = max(formats, key=lambda f: (f.get('width') or 0) * (f.get('height') or 0))
            media.append({'type': 'image' if entry.get('_meaningly_image') else 'video', 'url': best['url']})
    print(json.dumps({'text': result.get('description') or '', 'media': media}))
