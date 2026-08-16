let currentWallet = null;
let editingId = null;

const ownerBar = document.getElementById('ownerBar');
const newPostBtn = document.getElementById('newPostBtn');

const listView = document.getElementById('listView');
const postList = document.getElementById('postList');

const postView = document.getElementById('postView');
const postTitle = document.getElementById('postTitle');
const postDate = document.getElementById('postDate');
const postBody = document.getElementById('postBody');
const postOwnerActions = document.getElementById('postOwnerActions');
const backToListBtn = document.getElementById('backToListBtn');
const editPostBtn = document.getElementById('editPostBtn');
const deletePostBtn = document.getElementById('deletePostBtn');

const composeView = document.getElementById('composeView');
const composeTitle = document.getElementById('composeTitle');
const composeBody = document.getElementById('composeBody');
const composePublished = document.getElementById('composePublished');
const composeError = document.getElementById('composeError');
const saveComposeBtn = document.getElementById('saveComposeBtn');
const backFromComposeBtn = document.getElementById('backFromComposeBtn');

const connectBtn = document.getElementById('connectBtn');
const logoutBtn = document.getElementById('logoutBtn');
const connectStatus = document.getElementById('connectStatus');

function showView(view) {
    [listView, postView, composeView].forEach((v) => v.classList.add('hidden'));
    view.classList.remove('hidden');
}

async function connectWallet() {
    if (!window.ethereum) {
        connectStatus.textContent = 'MetaMask не найден в браузере';
        connectStatus.classList.remove('hidden');
        return;
    }
    connectBtn.disabled = true;
    try {
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        const address = accounts[0];
        const { nonce } = await (await fetch('api/auth/nonce')).json();
        const domain = window.location.host;
        const issuedAt = new Date().toISOString();
        const message = `${domain} wants you to sign in with your Ethereum account:\n${address}\n\nSign in to Blog\n\nURI: ${window.location.origin}\nVersion: 1\nChain ID: 1\nNonce: ${nonce}\nIssued At: ${issuedAt}`;

        const signature = await window.ethereum.request({
            method: 'personal_sign',
            params: [message, address],
        });

        const res = await fetch('api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, signature }),
        });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new Error(body.detail || 'Не удалось войти');
        }
        const data = await res.json();
        setOwner(data.wallet);
    } catch (err) {
        connectStatus.textContent = err.message || 'Отклонено';
        connectStatus.classList.remove('hidden');
    } finally {
        connectBtn.disabled = false;
    }
}

async function logout() {
    await fetch('api/auth/logout', { method: 'POST' });
    setOwner(null);
    showView(listView);
    loadList();
}

function setOwner(wallet) {
    currentWallet = wallet;
    const isOwner = !!wallet;
    ownerBar.classList.toggle('hidden', !isOwner);
    connectBtn.classList.toggle('hidden', isOwner);
    logoutBtn.classList.toggle('hidden', !isOwner);
    connectStatus.classList.add('hidden');
}

function renderPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    const head = document.createElement('div');
    head.className = 'post-card-head';
    const title = document.createElement('h2');
    title.className = 'post-title';
    title.textContent = post.title;
    head.appendChild(title);
    if (!post.published) {
        const badge = document.createElement('span');
        badge.className = 'draft-badge';
        badge.textContent = 'черновик';
        head.appendChild(badge);
    }
    card.appendChild(head);
    const date = document.createElement('p');
    date.className = 'post-date';
    date.textContent = new Date(post.created_at + 'Z').toLocaleDateString('ru-RU');
    card.appendChild(date);
    card.addEventListener('click', () => openPost(post.id));
    return card;
}

async function loadList() {
    const res = await fetch('api/posts');
    const posts = await res.json();
    postList.innerHTML = '';
    if (posts.length === 0) {
        postList.innerHTML = '<p style="color: var(--muted); font-size: 14px;">Пока пусто.</p>';
        return;
    }
    posts.forEach((p) => postList.appendChild(renderPostCard(p)));
}

async function openPost(id) {
    const res = await fetch(`api/posts/${id}`);
    if (!res.ok) return;
    const post = await res.json();
    postTitle.textContent = post.title;
    postDate.textContent = new Date(post.created_at + 'Z').toLocaleDateString('ru-RU') + (post.published ? '' : ' · черновик');
    postBody.innerHTML = post.body_html;
    postOwnerActions.classList.toggle('hidden', !currentWallet);
    postOwnerActions.dataset.postId = post.id;
    postView.dataset.currentPost = JSON.stringify(post);
    showView(postView);
}

function openCompose(post) {
    editingId = post ? post.id : null;
    composeTitle.value = post ? post.title : '';
    composeBody.value = post ? post.body_markdown : '';
    composePublished.checked = post ? !!post.published : false;
    composeError.classList.add('hidden');
    showView(composeView);
}

async function saveCompose() {
    const payload = {
        title: composeTitle.value.trim(),
        body_markdown: composeBody.value,
        published: composePublished.checked,
    };
    if (!payload.title || !payload.body_markdown) {
        composeError.textContent = 'Заголовок и текст обязательны';
        composeError.classList.remove('hidden');
        return;
    }
    saveComposeBtn.disabled = true;
    try {
        const url = editingId ? `api/posts/${editingId}` : 'api/posts';
        const method = editingId ? 'PUT' : 'POST';
        const res = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error((await res.json()).detail || 'Не получилось сохранить');
        showView(listView);
        loadList();
    } catch (err) {
        composeError.textContent = err.message;
        composeError.classList.remove('hidden');
    } finally {
        saveComposeBtn.disabled = false;
    }
}

async function deleteCurrentPost() {
    const post = JSON.parse(postView.dataset.currentPost || '{}');
    if (!post.id || !confirm('Удалить пост?')) return;
    await fetch(`api/posts/${post.id}`, { method: 'DELETE' });
    showView(listView);
    loadList();
}

newPostBtn.addEventListener('click', () => openCompose(null));
backToListBtn.addEventListener('click', () => { showView(listView); loadList(); });
backFromComposeBtn.addEventListener('click', () => showView(listView));
saveComposeBtn.addEventListener('click', saveCompose);
editPostBtn.addEventListener('click', () => openCompose(JSON.parse(postView.dataset.currentPost)));
deletePostBtn.addEventListener('click', deleteCurrentPost);
connectBtn.addEventListener('click', connectWallet);
logoutBtn.addEventListener('click', logout);

(async function init() {
    const res = await fetch('api/auth/me');
    if (res.ok) {
        const data = await res.json();
        setOwner(data.wallet);
    }
    loadList();
})();
