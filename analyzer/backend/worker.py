import logging
import threading

import db
import notion_store
import pipeline
import telegram

log = logging.getLogger(__name__)
_wake = threading.Event()
_stop = threading.Event()
_thread = None
MAX_ATTEMPTS = 3


def notify(chat_id, text, entry_id=None):
    if chat_id:
        try:
            telegram.send_message(chat_id, text, entry_id=entry_id)
        except Exception:
            log.exception('Failed to send Telegram notification')


def process_job(job):
    entry_id = job['id']
    try:
        pipeline.process_entry(entry_id)
        db.finish_job(entry_id)
    except Exception as error:
        log.exception('Processing entry %s failed', entry_id)
        if job['attempts'] < MAX_ATTEMPTS:
            db.retry_job(entry_id, str(error), 20 if job['attempts'] == 1 else 60)
            return
        db.fail_job(entry_id, str(error))
        row = db.get_entry(entry_id)
        if row.get('notion_page_id'):
            try:
                notion_store.update_entry(row['notion_page_id'], 'Ошибка обработки', str(error), [], 'Ошибка')
            except Exception:
                log.exception('Failed to update Notion status')
        link = (' Карточка в Notion: ' + row['notion_url']) if row.get('notion_url') else ''
        notify(row.get('telegram_chat_id'), 'Не удалось обработать после трёх попыток.' + link)
        return
    row = db.get_entry(entry_id)
    notify(row.get('telegram_chat_id'), row['transcript'], entry_id=entry_id)
    if row.get('notion_url'):
        notify(row.get('telegram_chat_id'), 'Сохранено в Notion: ' + row['notion_url'])


def _run():
    while not _stop.is_set():
        try:
            job = db.claim_job()
            if job:
                process_job(job)
                continue
        except Exception:
            log.exception('Queue worker failed')
        _wake.wait(2)
        _wake.clear()


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    db.recover_jobs()
    _stop.clear()
    _thread = threading.Thread(target=_run, name='analyzer-queue', daemon=True)
    _thread.start()


def wake():
    _wake.set()


def stop():
    _stop.set()
    _wake.set()
