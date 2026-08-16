const connectGate = document.getElementById('connectGate');
const connectBtn = document.getElementById('connectBtn');
const connectStatus = document.getElementById('connectStatus');
const appEl = document.getElementById('app');
const logoutBtn = document.getElementById('logoutBtn');
const linkBtn = document.getElementById('linkBtn');
const linkResult = document.getElementById('linkResult');

const form = document.getElementById('submitForm');
const urlInput = document.getElementById('url');
const fileInput = document.getElementById('file-upload');
const fileNameEl = document.getElementById('fileName');
const submitBtn = document.getElementById('submitBtn');
const errorEl = document.getElementById('formError');
const libraryEl = document.getElementById('library');

function showStatus(text) {
    connectStatus.textContent = text;
    connectStatus.classList.remove('hidden');
}

async function connectWallet() {
    if (!window.ethereum) {
        showStatus('MetaMask не найден в браузере');
        return;
    }
    connectBtn.disabled = true;
    try {
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        const address = accounts[0];
        const { nonce } = await (await fetch('/api/auth/nonce')).json();
        const domain = window.location.host;
        const issuedAt = new Date().toISOString();
        const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\nSign in to Analyzer\n\nURI: ${window.location.origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${issuedAt}`;

        const signature = await window.ethereum.request({
            method: 'personal_sign',
            params: [message, address],
        });

        const res = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, signature }),
        });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.detail || 'Не удалось войти');
        }
        showApp();
    } catch (err) {
        showStatus(err.message || 'Отклонено');
    } finally {
        connectBtn.disabled = false;
    }
}

async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    appEl.classList.add('hidden');
    connectGate.classList.remove('hidden');
}

async function getLinkCode() {
    linkBtn.disabled = true;
    try {
        const res = await fetch('/api/telegram/link-code', { method: 'POST' });
        const data = await res.json();
        linkResult.textContent = `Отправь боту @${data.bot_username}: /link ${data.code}`;
        linkResult.classList.remove('hidden');
    } finally {
        linkBtn.disabled = false;
    }
}

function showApp() {
    connectGate.classList.add('hidden');
    appEl.classList.remove('hidden');
    poll();
}

connectBtn.addEventListener('click', connectWallet);
logoutBtn.addEventListener('click', logout);
linkBtn.addEventListener('click', getLinkCode);

(async function checkAuth() {
    const res = await fetch('/api/auth/me');
    if (res.ok) showApp();
})();

const STATUS_LABELS = {
    queued: 'В очереди',
    downloading: 'Скачивается',
    transcribing: 'Расшифровывается',
    done: 'Готово',
    error: 'Ошибка',
};

fileInput.addEventListener('change', () => {
    fileNameEl.textContent = fileInput.files[0] ? fileInput.files[0].name : '';
    if (fileInput.files[0]) urlInput.value = '';
});
urlInput.addEventListener('input', () => {
    if (urlInput.value) {
        fileInput.value = '';
        fileNameEl.textContent = '';
    }
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.classList.add('hidden');

    const url = urlInput.value.trim();
    const file = fileInput.files[0];
    if (!url && !file) {
        errorEl.textContent = 'Укажи ссылку или выбери файл';
        errorEl.classList.remove('hidden');
        return;
    }

    const formData = new FormData();
    if (file) formData.append('file', file);
    else formData.append('url', url);

    submitBtn.disabled = true;
    try {
        const res = await fetch('/api/entries', { method: 'POST', body: formData });
        if (!res.ok) throw new Error((await res.json()).detail || 'Не получилось добавить');
        form.reset();
        fileNameEl.textContent = '';
        await refreshLibrary();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
    }
});

function renderEntry(entry) {
    const card = document.createElement('div');
    card.className = 'entry-card';
    card.id = `entry-${entry.id}`;

    const head = document.createElement('div');
    head.className = 'entry-card-head';
    const source = document.createElement('span');
    source.className = 'entry-source';
    source.textContent = entry.source_ref || `файл #${entry.id}`;
    const badge = document.createElement('span');
    badge.className = `status-badge status-${entry.status}`;
    badge.textContent = STATUS_LABELS[entry.status] || entry.status;
    head.appendChild(source);
    head.appendChild(badge);
    card.appendChild(head);

    if (entry.status === 'error' && entry.error_message) {
        const err = document.createElement('div');
        err.className = 'entry-error';
        err.textContent = entry.error_message;
        card.appendChild(err);
    }

    if (entry.status === 'done') {
        const details = document.createElement('details');
        details.className = 'entry-transcript';
        const summary = document.createElement('summary');
        summary.textContent = 'Транскрипт';
        const pre = document.createElement('pre');
        pre.textContent = 'Загрузка…';
        details.appendChild(summary);
        details.appendChild(pre);
        details.addEventListener('toggle', async () => {
            if (details.open && pre.textContent === 'Загрузка…') {
                const res = await fetch(`/api/entries/${entry.id}`);
                const full = await res.json();
                pre.textContent = full.transcript || '';
            }
        }, { once: false });
        card.appendChild(details);
    }

    return card;
}

async function refreshLibrary() {
    const res = await fetch('/api/entries');
    const entries = await res.json();
    libraryEl.innerHTML = '';
    entries.forEach((entry) => libraryEl.appendChild(renderEntry(entry)));
    return entries.some((e) => e.status !== 'done' && e.status !== 'error');
}

async function poll() {
    const hasPending = await refreshLibrary();
    setTimeout(poll, hasPending ? 5000 : 15000);
}
