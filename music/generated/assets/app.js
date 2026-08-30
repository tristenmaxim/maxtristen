/* Склейка: движок Strudel, генератор, интерфейс. */

const $ = (id) => document.getElementById(id);
const BARS = 32;

const state = {
  booted: false, booting: null, playing: false,
  scene: 'lofi', seed: (Math.random() * 1e9) | 0,
  track: null, t0: 0, cps: 0.3, regenAt: -1,
  params: { master: 0.8, intensity: 0.6, brightness: 0.5, space: 0.5, texture: 0.35 },
};

/* ---------- адрес страницы ---------- */
{
  const q = new URLSearchParams(location.search);
  if (q.get('scene') && SCENES[q.get('scene')]) state.scene = q.get('scene');
  if (q.get('seed') && /^\d+$/.test(q.get('seed'))) state.seed = parseInt(q.get('seed'), 10);
  // без параметров — подсказываем сцену по времени суток
  else if (!q.get('scene')) {
    const h = new Date().getHours();
    state.scene = h >= 23 || h < 6 ? 'sleep' : h < 11 ? 'focus' : h < 18 ? 'lofi' : 'jazz';
  }
}

/* ---------- сцены ---------- */
function renderScenes() {
  $('scenes').innerHTML = '';
  for (const [id, sc] of Object.entries(SCENES)) {
    const b = document.createElement('button');
    b.className = 'scene' + (id === state.scene ? ' on' : '');
    b.innerHTML = '<b></b><span></span>';
    b.querySelector('b').textContent = sc.label;
    b.querySelector('span').textContent = sc.hint;
    b.onclick = () => selectScene(id);
    $('scenes').appendChild(b);
  }
  $('scene-name').textContent = SCENES[state.scene].label;
  $('scene-hint').textContent = SCENES[state.scene].hint;
}

function selectScene(id) {
  if (id === state.scene) return;
  state.scene = id;
  state.seed = (Math.random() * 1e9) | 0;
  renderScenes();
  syncUrl();
  buildTrack();
  if (state.playing) switchLive();
}

/* ---------- генерация ---------- */
function buildTrack(inherit) {
  state.track = generateTrack(state.seed, state.scene, {
    bars: BARS, inherit,
    intensity: state.params.intensity,
    brightness: state.params.brightness,
    space: state.params.space,
    texture: state.params.texture,
    master: state.params.master,
  });
  $('code').textContent = state.track.code;
  paintMeta();
  paintLikes();
  return state.track;
}

function paintMeta() {
  const m = state.track.meta;
  $('np-key').textContent = m.key;
  $('np-bpm').textContent = m.bpm + ' BPM';
  $('np-prog').textContent = m.progression;
  $('seedchip').textContent = 'seed ' + m.seed;
  const box = $('chords');
  box.innerHTML = '';
  m.chords.forEach((c) => {
    const el = document.createElement('div');
    el.className = 'chord'; el.textContent = c;
    box.appendChild(el);
  });
}

function syncUrl() {
  const q = new URLSearchParams({ scene: state.scene, seed: String(state.seed) });
  history.replaceState(null, '', location.pathname + '?' + q);
}

/* ---------- запуск движка ---------- */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const CDN = 'https://cdn.jsdelivr.net/gh/';
const GH = 'https://raw.githubusercontent.com/';
// raw.githubusercontent отдаёт файлы медленно и без кэша — переписываем на jsDelivr
const viaCdn = (url) => {
  if (!url.startsWith(GH)) return url;
  const [owner, repo, ref, ...rest] = url.slice(GH.length).split('/');
  return CDN + owner + '/' + repo + '@' + ref + '/' + rest.join('/');
};

const SAMPLE_PACKS = [
  CDN + 'felixroos/dough-samples@main/tidal-drum-machines.json',
  CDN + 'felixroos/dough-samples@main/piano.json',
  CDN + 'felixroos/dough-samples@main/vcsl.json',
  CDN + 'eddyflux/crate@main/strudel.json',      // пыльные лоу-фай барабаны
];

const packMaps = {};
async function loadPack(url) {
  const map = await fetch(url).then((r) => r.json());
  if (map._base) map._base = viaCdn(map._base);
  packMaps[url] = map;
  return window.samples(map);
}

function boot() {
  if (state.booted) return Promise.resolve();
  if (state.booting) return state.booting;
  state.booting = (async () => {
    await window.initStrudel({
      prebake: () => Promise.all(SAMPLE_PACKS.map((u) =>
        loadPack(u).catch((e) => console.warn('пак не загрузился:', u, e)))),
    });
    for (let i = 0; i < 100 && typeof window.evaluate !== 'function'; i++) await sleep(50);
    state.booted = true;
  })();
  return state.booting;
}

/* Разбор имён вида C4 / A#3 / Ds1 в MIDI. */
const LETTER = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
function keyToMidi(k) {
  const m = /^([A-G])([#sb]*)(-?\d+)$/.exec(k);
  if (!m) return null;
  let pc = LETTER[m[1]];
  for (const ch of m[2]) pc += ch === 'b' ? -1 : 1;
  return (parseInt(m[3], 10) + 1) * 12 + pc;
}

/* Файлы инструмента. Имя может быть с индексом: crate_bd:37 — тогда нужен
   ровно этот файл, у крейта их полсотни на слот. */
function urlsFor(name, notes, limit) {
  const [base, idxStr] = String(name).split(':');
  const idx = idxStr === undefined ? null : parseInt(idxStr, 10);
  for (const map of Object.values(packMaps)) {
    const entry = map[base];
    if (!entry) continue;
    const pre = map._base || '';
    if (Array.isArray(entry)) {
      if (idx !== null) return entry[idx % entry.length] ? [pre + entry[idx % entry.length]] : [];
      return entry.slice(0, limit).map((f) => pre + f);
    }
    const items = Object.entries(entry)
      .map(([k, v]) => ({ midi: keyToMidi(k), file: Array.isArray(v) ? v[0] : v }))
      .filter((x) => x.midi !== null);
    if (!items.length) return [];
    const dist = (x) => Math.min(...notes.map((n) => Math.abs(n - x.midi)));
    return items.sort((a, b) => dist(a) - dist(b)).slice(0, limit).map((x) => pre + x.file);
  }
  return [];
}

/* Прогрев: кладём сэмплы в HTTP-кэш браузера, музыка при этом не прерывается.
   Имена берём прямо из сгенерированного кода, чтобы ничего не забыть. */
const warmed = new Set();
async function warmSamples(track, budget = 4000) {
  const code = track.code;
  const urls = new Set();
  const drums = new Set();
  for (const m of code.matchAll(/\bs\("([^"]+)"\)/g))
    for (const tok of m[1].split(/\s+/)) if (tok && tok !== '~' && !/^[<>\[\]]/.test(tok)) drums.add(tok);
  drums.forEach((d) => urlsFor(d, track.notesUsed, 1).forEach((u) => urls.add(u)));
  for (const m of code.matchAll(/\.s\("([^"]+)"\)/g))
    urlsFor(m[1], track.notesUsed, 6).forEach((u) => urls.add(u));

  const todo = [...urls].filter((u) => !warmed.has(u));
  if (!todo.length) return;
  todo.forEach((u) => warmed.add(u));
  // ждём недолго: остальное дотечёт в фоне, к нужным тактам успеет
  await Promise.race([
    Promise.all(todo.map((u) => fetch(u).then((r) => r.arrayBuffer()).catch(() => warmed.delete(u)))),
    sleep(budget),
  ]);
}

/* ---------- транспорт ---------- */
async function startTrack() {
  try { await startTrackInner(); }
  catch (e) {
    console.error(e);
    $('play').disabled = false;
    $('status').textContent = 'Не получилось запустить: ' + e.message;
  }
}

async function startTrackInner() {
  $('play').disabled = true;
  $('status').textContent = state.booted ? 'Собираю трек…' : 'Загружаю движок и сэмплы…';
  await boot();
  // до загрузки Strudel гармония считается запасной таблицей — пересобираем,
  // чтобы взять словарь вольтовок iReal
  if (!state.track || state.track.meta.voicedBy !== 'ireal') buildTrack();
  const track = state.track;
  $('status').textContent = 'Подгружаю инструменты…';
  await warmSamples(track);
  await window.evaluate(track.code, true);
  state.cps = track.meta.bpm / 60 / 4;
  state.t0 = window.getAudioContext().currentTime;
  state.playing = true;
  state.regenAt = BARS - 1;
  $('play').disabled = false;
  $('play').classList.add('playing');
  $('play-ico').textContent = '⏸';
  $('status').textContent = 'Играет. Трек пересобирается каждые ' + BARS + ' тактов.';
}

function stopTrack() {
  window.hush();
  state.playing = false;
  $('play').classList.remove('playing');
  $('play-ico').textContent = '▶';
  $('status').textContent = 'Пауза.';
}

$('play').onclick = () => (state.playing ? stopTrack() : startTrack());

$('regen').onclick = () => {
  state.seed = (Math.random() * 1e9) | 0;
  syncUrl();
  buildTrack();
  if (state.playing) restartSeamless();
};

/* Отметки «нравится» копятся в браузере: по ним видно, что общего у треков,
   которые реально слушают — темп, лад, грув, набор барабанов. */
const LIKES_KEY = 'maxtristen-music-likes';
function readLikes() {
  try { return JSON.parse(localStorage.getItem(LIKES_KEY) || '[]'); } catch (e) { return []; }
}
function paintLikes() {
  const n = readLikes().length;
  $('like-count').textContent = n ? String(n) : '';
  const liked = readLikes().some((x) => x.seed === state.seed && x.scene === state.scene);
  $('like').classList.toggle('on', liked);
}
$('like').onclick = () => {
  const m = state.track.meta;
  let likes = readLikes();
  const i = likes.findIndex((x) => x.seed === m.seed && x.scene === m.sceneId);
  if (i >= 0) likes.splice(i, 1);
  else likes.push({
    seed: m.seed, scene: m.sceneId, key: m.key, bpm: m.bpm, groove: m.groove,
    kit: m.kit, phraseLen: m.phraseLen, bassStyle: m.bassStyle,
    progression: m.progression, chords: m.chords, at: new Date().toISOString(),
  });
  likes = likes.slice(-300);
  try { localStorage.setItem(LIKES_KEY, JSON.stringify(likes)); } catch (e) {}
  paintLikes();
  $('status').textContent = i >= 0 ? 'Убрал из отмеченных.' : 'Отмечено. Всего: ' + likes.length;
};

$('share').onclick = async () => {
  syncUrl();
  try { await navigator.clipboard.writeText(location.href); $('status').textContent = 'Ссылка на этот трек скопирована.'; }
  catch (e) { $('status').textContent = location.href; }
};

$('codetoggle').onclick = () => {
  const c = $('code');
  c.classList.toggle('hidden');
  $('codetoggle').textContent = c.classList.contains('hidden') ? 'Показать партитуру (код Strudel)' : 'Скрыть партитуру';
};

/* Подмена паттерна на лету: cat выбирает такт по номеру цикла,
   поэтому позиция в аранжировке не сбивается. */
/* Смена сцены на ходу: сначала тихо тянем новые сэмплы, потом подменяем паттерн. */
async function switchLive() {
  $('status').textContent = 'Подгружаю инструменты…';
  await warmSamples(state.track);
  await restartSeamless();
  $('status').textContent = 'Играет. Трек пересобирается каждые ' + BARS + ' тактов.';
}

async function restartSeamless() {
  if (!state.booted) return;
  state.cps = state.track.meta.bpm / 60 / 4;
  await window.evaluate(state.track.code, true);
}

/* ---------- ручки ---------- */
let knobTimer = null;
function bindKnob(id, key, fmt) {
  const el = $(id), out = $('v-' + key);
  el.value = Math.round(state.params[key] * 100);
  out.textContent = el.value + '%';
  el.oninput = () => {
    state.params[key] = el.value / 100;
    out.textContent = el.value + '%';
    clearTimeout(knobTimer);
    knobTimer = setTimeout(() => {
      buildTrack();
      if (state.playing) restartSeamless();
    }, 260);
  };
}
bindKnob('k-master', 'master');
bindKnob('k-intensity', 'intensity');
bindKnob('k-brightness', 'brightness');
bindKnob('k-space', 'space');
bindKnob('k-texture', 'texture');

/* ---------- часы аранжировки ---------- */
function tick() {
  if (!state.playing || !state.track) return;
  const ctx = window.getAudioContext();
  const cycle = (ctx.currentTime - state.t0) * state.cps;
  const bar = Math.floor(cycle) % BARS;
  const m = state.track.meta;
  $('np-bar').textContent = (bar + 1) + ' / ' + BARS;
  $('np-section').textContent = SECTION_RU[m.sections[bar].name] || m.sections[bar].name;
  const ci = bar % m.chords.length;
  document.querySelectorAll('.chord').forEach((el, i) => el.classList.toggle('on', i === ci));

  if (bar === state.regenAt) {
    state.regenAt = -1;
    nextTrack();
  } else if (bar === 0) {
    state.regenAt = BARS - 1;
  }
}

const SECTION_RU = { intro: 'вступление', A: 'основная', B: 'развитие', break: 'брейк', C: 'кульминация', outro: 'кода' };

async function nextTrack() {
  const prev = state.track.meta;
  state.seed = (Math.random() * 1e9) | 0;
  // сет держит одну гармонию две аранжировки подряд и только на третьей
  // уходит в новую — иначе каждые полторы минуты начинается другая пьеса
  state.setPos = ((state.setPos || 0) + 1) % 3;
  const keepProg = state.setPos !== 0;
  buildTrack({
    bpm: prev.bpm, tonic: prev.tonic, mode: prev.mode, family: prev.family, hard: keepProg,
    progDef: keepProg ? prev.progDef : null, prog: keepProg ? prev.prog : null,
  });
  syncUrl();
  warmSamples(state.track);
  state.cps = state.track.meta.bpm / 60 / 4;
  await window.evaluate(state.track.code, true);
}
// таймер, а не requestAnimationFrame: во вкладке в фоне rAF засыпает, а музыка играет дальше
setInterval(tick, 200);

/* ---------- фоновая графика ---------- */
(function viz() {
  const cv = $('viz'), g = cv.getContext('2d');
  let W = 0, H = 0, level = 0, phase = 0;
  const resize = () => {
    const d = Math.min(devicePixelRatio || 1, 2);
    W = cv.width = innerWidth * d; H = cv.height = innerHeight * d;
    cv.style.width = innerWidth + 'px'; cv.style.height = innerHeight + 'px';
    g.setTransform(d, 0, 0, d, 0, 0);
  };
  addEventListener('resize', resize); resize();

  const wave = new Float32Array(256);
  const smooth = new Float32Array(256);
  let rot = 0;

  function draw() {
    requestAnimationFrame(draw);
    const w = innerWidth, h = innerHeight;
    let peak = 0;
    const an = window.strudel && strudel.analysers && strudel.analysers[1];
    if (an && state.playing) {
      const buf = new Float32Array(an.fftSize);
      an.getFloatTimeDomainData(buf);
      for (let i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i]));
      const step = buf.length / wave.length;
      for (let i = 0; i < wave.length; i++) wave[i] = buf[(i * step) | 0];
      // сглаживаем, иначе кольцо превращается в колючку
      const K = 6;
      for (let i = 0; i < smooth.length; i++) {
        let acc = 0;
        for (let k = -K; k <= K; k++) acc += wave[(i + k + wave.length) % wave.length];
        smooth[i] += (acc / (K * 2 + 1) - smooth[i]) * 0.35;
      }
    } else {
      for (let i = 0; i < smooth.length; i++) smooth[i] *= 0.94;
    }
    level += (peak - level) * (peak > level ? 0.2 : 0.02);
    phase += 0.0015;
    rot += 0.0008;

    g.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2;
    const base = Math.min(w, h) * 0.5;
    const r = base * (0.78 + level * 0.14 + Math.sin(phase * 3) * 0.015);

    const glow = g.createRadialGradient(cx, cy, r * 0.15, cx, cy, r * 1.5);
    glow.addColorStop(0, 'rgba(217,179,130,' + (0.05 + level * 0.09).toFixed(3) + ')');
    glow.addColorStop(0.55, 'rgba(127,168,160,' + (0.03 + level * 0.05).toFixed(3) + ')');
    glow.addColorStop(1, 'rgba(10,11,13,0)');
    g.fillStyle = glow;
    g.fillRect(0, 0, w, h);

    for (let k = 0; k < 3; k++) {
      const rr = r * (0.78 + k * 0.14) + Math.sin(phase * (2 + k) + k) * 5;
      g.beginPath();
      g.arc(cx, cy, rr, 0, Math.PI * 2);
      g.strokeStyle = 'rgba(236,231,223,' + (0.04 - k * 0.01 + level * 0.03).toFixed(3) + ')';
      g.lineWidth = 1;
      g.stroke();
    }

    g.beginPath();
    const N = smooth.length;
    for (let i = 0; i <= N; i++) {
      const a = (i / N) * Math.PI * 2 + rot;
      const rr = r + (smooth[i % N] || 0) * base * 0.16;
      const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath();
    g.strokeStyle = 'rgba(217,179,130,' + (0.14 + level * 0.22).toFixed(3) + ')';
    g.lineWidth = 1.4;
    g.stroke();
  }
  draw();
})();

/* ---------- старт ---------- */
renderScenes();
buildTrack();
syncUrl();
