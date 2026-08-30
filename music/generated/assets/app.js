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
const SAMPLE_PACKS = ['tidal-drum-machines', 'piano', 'vcsl'];
const GH = 'https://raw.githubusercontent.com/';
const CDN = 'https://cdn.jsdelivr.net/gh/';
// raw.githubusercontent отдаёт файлы медленно и без кэша — переписываем на jsDelivr
const viaCdn = (url) => {
  if (!url.startsWith(GH)) return url;
  const [owner, repo, ref, ...rest] = url.slice(GH.length).split('/');
  return CDN + owner + '/' + repo + '@' + ref + '/' + rest.join('/');
};

const packMaps = {};
async function loadPack(name) {
  const map = await fetch(CDN + 'felixroos/dough-samples@main/' + name + '.json').then((r) => r.json());
  if (map._base) map._base = viaCdn(map._base);
  packMaps[name] = map;
  return window.samples(map);
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

/* Находим файлы для нужного инструмента и нужного участка диапазона. */
function urlsFor(instrument, notes, limit) {
  for (const map of Object.values(packMaps)) {
    const entry = map[instrument];
    if (!entry) continue;
    const base = map._base || '';
    if (Array.isArray(entry)) return entry.slice(0, limit).map((f) => base + f);
    const items = Object.entries(entry)
      .map(([k, v]) => ({ midi: keyToMidi(k), file: Array.isArray(v) ? v[0] : v }))
      .filter((x) => x.midi !== null);
    if (!items.length) return [];
    const dist = (x) => Math.min(...notes.map((n) => Math.abs(n - x.midi)));
    return items.sort((a, b) => dist(a) - dist(b)).slice(0, limit).map((x) => base + x.file);
  }
  return [];
}

/* Прогрев: кладём сэмплы в HTTP-кэш браузера, музыка при этом не прерывается. */
const warmed = new Set();
async function warmSamples(sceneId, notes, budget = 4000) {
  const sc = SCENES[sceneId];
  const urls = new Set();
  urlsFor(sc.keySound, notes, 6).forEach((u) => urls.add(u));
  urlsFor(sc.melSound, notes, 5).forEach((u) => urls.add(u));
  if (sc.drums) for (const slot of ['bd', 'sd', 'hh', 'oh', 'rim', 'perc'])
    urlsFor(sc.drums.bank + '_' + slot, notes, 1).forEach((u) => urls.add(u));
  const todo = [...urls].filter((u) => !warmed.has(u));
  if (!todo.length) return;
  todo.forEach((u) => warmed.add(u));
  // ждём недолго: остальное дотечёт в фоне, к нужным тактам успеет
  await Promise.race([
    Promise.all(todo.map((u) => fetch(u).then((r) => r.arrayBuffer()).catch(() => warmed.delete(u)))),
    sleep(budget),
  ]);
}

function boot() {
  if (state.booted) return Promise.resolve();
  if (state.booting) return state.booting;
  state.booting = (async () => {
    await window.initStrudel({
      prebake: () => Promise.all(SAMPLE_PACKS.map((n) =>
        loadPack(n).catch((e) => console.warn('пак не загрузился:', n, e)))),
    });
    for (let i = 0; i < 100 && typeof window.evaluate !== 'function'; i++) await sleep(50);
    state.booted = true;
  })();
  return state.booting;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
  await warmSamples(state.scene, track.notesUsed);
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
  await warmSamples(state.scene, state.track.notesUsed);
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
  buildTrack({ bpm: prev.bpm, tonic: prev.tonic, mode: prev.mode, family: prev.family });
  syncUrl();
  warmSamples(state.scene, state.track.notesUsed);
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
