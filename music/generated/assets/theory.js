/* Музыкальная теория: строй, лады, аккорды, голосоведение.
   Всё в MIDI-числах: 60 = C4. */

const RNG = (seed) => {
  let a = seed >>> 0;
  return () => {
    a += 0x6D2B79F5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

const R = {
  int: (r, a, b) => a + Math.floor(r() * (b - a + 1)),
  pick: (r, arr) => arr[Math.floor(r() * arr.length)],
  chance: (r, p) => r() < p,
  // взвешенный выбор: items = [[value, weight], ...]
  weighted: (r, items) => {
    const total = items.reduce((s, i) => s + i[1], 0);
    let x = r() * total;
    for (const [v, w] of items) { x -= w; if (x <= 0) return v; }
    return items[items.length - 1][0];
  },
  shuffle: (r, arr) => {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  },
};

const NOTE_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
const pcName = (pc) => NOTE_NAMES[((pc % 12) + 12) % 12];

const SCALES = {
  ionian:       [0, 2, 4, 5, 7, 9, 11],
  dorian:       [0, 2, 3, 5, 7, 9, 10],
  phrygian:     [0, 1, 3, 5, 7, 8, 10],
  lydian:       [0, 2, 4, 6, 7, 9, 11],
  mixolydian:   [0, 2, 4, 5, 7, 9, 10],
  aeolian:      [0, 2, 3, 5, 7, 8, 10],
  harmonicMinor:[0, 2, 3, 5, 7, 8, 11],
  majPent:      [0, 2, 4, 7, 9],
  minPent:      [0, 3, 5, 7, 10],
  kumoi:        [0, 2, 3, 7, 9],
  hirajoshi:    [0, 2, 3, 7, 8],
};

/* Аккорды: полный набор тонов от основного тона. */
const CHORDS = {
  maj7:   [0, 4, 7, 11],
  maj9:   [0, 4, 7, 11, 14],
  maj69:  [0, 4, 7, 9, 14],
  majS11: [0, 4, 7, 11, 18],
  min7:   [0, 3, 7, 10],
  min9:   [0, 3, 7, 10, 14],
  min11:  [0, 3, 7, 10, 14, 17],
  min6:   [0, 3, 7, 9],
  minMaj7:[0, 3, 7, 11],
  dom7:   [0, 4, 7, 10],
  dom9:   [0, 4, 7, 10, 14],
  dom13:  [0, 4, 7, 10, 14, 21],
  domS9:  [0, 4, 7, 10, 15],
  domB9:  [0, 4, 7, 10, 13],
  domB13: [0, 4, 7, 10, 14, 20],
  m7b5:   [0, 3, 6, 10],
  dim7:   [0, 3, 6, 9],
  sus2:   [0, 2, 7, 14],
  sus4:   [0, 5, 7, 14],
  sus7:   [0, 5, 7, 10, 14],
  add9:   [0, 4, 7, 14],
};

/* Безосновные («rootless») джазовые вольтовки — то, что реально играет левая/правая рука
   пианиста, когда бас держит основной тон. Интервалы от основного тона аккорда. */
const VOICINGS = {
  maj7:   [[4, 11, 14, 16], [11, 14, 16, 21]],
  maj9:   [[4, 7, 11, 14], [11, 14, 16, 19]],
  maj69:  [[4, 9, 14, 16], [9, 14, 16, 21]],
  majS11: [[4, 11, 14, 18], [11, 14, 18, 21]],
  min7:   [[3, 7, 10, 14], [10, 14, 15, 19]],
  min9:   [[3, 7, 10, 14], [10, 14, 15, 19]],
  min11:  [[3, 10, 14, 17], [10, 14, 17, 19]],
  min6:   [[3, 9, 14, 16], [9, 14, 15, 19]],
  minMaj7:[[3, 7, 11, 14], [11, 14, 15, 19]],
  dom7:   [[4, 10, 14, 16], [10, 14, 16, 21]],
  dom9:   [[4, 10, 14, 16], [10, 14, 16, 19]],
  dom13:  [[4, 9, 10, 14], [10, 14, 16, 21]],
  domS9:  [[4, 10, 15, 16], [10, 15, 16, 20]],
  domB9:  [[4, 9, 10, 13], [10, 13, 16, 21]],
  domB13: [[4, 8, 10, 14], [10, 14, 16, 20]],
  m7b5:   [[3, 6, 10, 14], [10, 14, 15, 18]],
  dim7:   [[3, 6, 9, 14], [6, 9, 12, 15]],
  sus2:   [[2, 7, 9, 14], [7, 14, 16, 21]],
  sus4:   [[5, 7, 10, 14], [10, 14, 17, 19]],
  sus7:   [[5, 10, 14, 17], [10, 14, 17, 21]],
  add9:   [[4, 7, 14, 16], [7, 14, 16, 19]],
};

const chordTones = (rootPc, type) => (CHORDS[type] || CHORDS.min7).map((i) => (rootPc + i) % 12);

/* Голосоведение: выбираем октавное положение и обращение так, чтобы аккорд
   лежал в нужном регистре и двигался минимально относительно предыдущего. */
function voiceChord(rootPc, type, prev, center = 65, rnd = null) {
  const shapes = VOICINGS[type] || VOICINGS.min7;
  const shape = rnd ? R.pick(rnd, shapes) : shapes[0];
  const base = shape.map((i) => rootPc + i);
  const candidates = [];
  for (let rot = 0; rot < base.length; rot++) {
    // обращение: rot нижних голосов поднимаем на октаву
    const rotated = [...new Set(base.map((n, i) => (i < rot ? n + 12 : n)))].sort((a, b) => a - b);
    if (rotated.length < 3) continue;
    for (let oct = 2; oct <= 7; oct++) {
      const v = rotated.map((n) => n + 12 * oct);
      if (v[0] < 46 || v[v.length - 1] > 88) continue;
      const mean = v.reduce((s, n) => s + n, 0) / v.length;
      let cost = Math.abs(mean - center) * 1.0;
      if (prev && prev.length) {
        // сумма минимальных перемещений голосов
        let move = 0;
        for (const n of v) move += Math.min(...prev.map((p) => Math.abs(p - n)));
        cost += (move / v.length) * 1.6;
        cost += Math.abs(v[v.length - 1] - prev[prev.length - 1]) * 0.8; // верхний голос ведём плавно
      }
      candidates.push({ v, cost });
    }
  }
  if (!candidates.length) return base.map((n) => n + 60);
  candidates.sort((a, b) => a.cost - b.cost);
  return candidates[0].v;
}

/* Ближайшая нота с заданным классом высоты к ориентиру. */
const nearestPc = (pc, ref) => {
  const base = ref - (((ref % 12) - (((pc % 12) + 12) % 12) + 12) % 12);
  return Math.abs(base - ref) <= Math.abs(base + 12 - ref) ? base : base + 12;
};

/* Абсолютные ноты лада в диапазоне. */
function scaleNotes(tonicPc, mode, lo, hi) {
  const ivs = SCALES[mode] || SCALES.dorian;
  const out = [];
  for (let oct = 0; oct <= 9; oct++) {
    for (const iv of ivs) {
      const n = tonicPc + iv + 12 * oct;
      if (n >= lo && n <= hi) out.push(n);
    }
  }
  return out.sort((a, b) => a - b);
}

const snapToSet = (note, set) => {
  let best = set[0], bd = 1e9;
  for (const n of set) { const d = Math.abs(n - note); if (d < bd) { bd = d; best = n; } }
  return best;
};

/* Библиотека прогрессий. r — смещение основного тона в полутонах от тоники,
   поэтому влезают и модальные заимствования, и хроматика. */
const PROGRESSIONS = {
  minor: [
    { name: 'royal road', bars: [{ r: 8, t: 'maj7' }, { r: 10, t: 'dom13' }, { r: 7, t: 'min7' }, { r: 0, t: 'min9' }] },
    { name: 'i–iv–VII–III', bars: [{ r: 0, t: 'min9' }, { r: 5, t: 'min9' }, { r: 10, t: 'dom13' }, { r: 3, t: 'maj7' }] },
    { name: 'ii–V–i', bars: [{ r: 2, t: 'm7b5' }, { r: 7, t: 'domB9' }, { r: 0, t: 'min9' }, { r: 0, t: 'min6' }] },
    { name: 'i–VI–III–VII', bars: [{ r: 0, t: 'min9' }, { r: 8, t: 'maj9' }, { r: 3, t: 'maj7' }, { r: 10, t: 'dom9' }] },
    { name: 'dorian vamp', bars: [{ r: 0, t: 'min9' }, { r: 5, t: 'dom9' }, { r: 0, t: 'min11' }, { r: 5, t: 'dom13' }] },
    { name: 'descending', bars: [{ r: 0, t: 'min9' }, { r: 10, t: 'maj7' }, { r: 8, t: 'maj9' }, { r: 7, t: 'dom13' }] },
    { name: 'i–bII–i', bars: [{ r: 0, t: 'min9' }, { r: 1, t: 'maj7' }, { r: 0, t: 'min9' }, { r: 7, t: 'domS9' }] },
    { name: 'lament', bars: [{ r: 0, t: 'min9' }, { r: 0, t: 'minMaj7' }, { r: 0, t: 'min7' }, { r: 8, t: 'maj7' }] },
    { name: 'iv–V–III–vi', bars: [{ r: 5, t: 'min9' }, { r: 7, t: 'sus7' }, { r: 3, t: 'maj9' }, { r: 0, t: 'min11' }] },
  ],
  major: [
    { name: 'I–vi–ii–V', bars: [{ r: 0, t: 'maj9' }, { r: 9, t: 'min9' }, { r: 2, t: 'min7' }, { r: 7, t: 'dom13' }] },
    { name: 'I–IV#11', bars: [{ r: 0, t: 'maj9' }, { r: 5, t: 'majS11' }, { r: 4, t: 'min7' }, { r: 9, t: 'dom9' }] },
    { name: 'ii–V–I turn', bars: [{ r: 2, t: 'min9' }, { r: 7, t: 'dom13' }, { r: 0, t: 'maj9' }, { r: 9, t: 'domS9' }] },
    { name: 'I–iii–IV–iv', bars: [{ r: 0, t: 'maj9' }, { r: 4, t: 'min7' }, { r: 5, t: 'maj7' }, { r: 5, t: 'min6' }] },
    { name: 'lydian drift', bars: [{ r: 0, t: 'maj9' }, { r: 2, t: 'maj7' }, { r: 0, t: 'majS11' }, { r: 7, t: 'sus7' }] },
    { name: 'I–VI–ii–V', bars: [{ r: 0, t: 'maj69' }, { r: 9, t: 'domB9' }, { r: 2, t: 'min9' }, { r: 7, t: 'dom13' }] },
    { name: 'backdoor', bars: [{ r: 0, t: 'maj9' }, { r: 5, t: 'min9' }, { r: 10, t: 'dom9' }, { r: 0, t: 'maj7' }] },
    { name: 'I–bIII–IV', bars: [{ r: 0, t: 'maj9' }, { r: 3, t: 'maj7' }, { r: 5, t: 'maj9' }, { r: 7, t: 'sus7' }] },
  ],
  modal: [
    { name: 'two-chord dorian', bars: [{ r: 0, t: 'min11' }, { r: 0, t: 'min11' }, { r: 5, t: 'dom9' }, { r: 5, t: 'dom9' }] },
    { name: 'suspended air', bars: [{ r: 0, t: 'sus2' }, { r: 0, t: 'sus2' }, { r: 7, t: 'sus4' }, { r: 7, t: 'sus4' }] },
    { name: 'lydian pedal', bars: [{ r: 0, t: 'maj9' }, { r: 0, t: 'maj9' }, { r: 2, t: 'min9' }, { r: 2, t: 'min9' }] },
    { name: 'aeolian float', bars: [{ r: 0, t: 'min9' }, { r: 0, t: 'min9' }, { r: 8, t: 'maj9' }, { r: 8, t: 'maj9' }] },
    { name: 'quartal drift', bars: [{ r: 0, t: 'sus2' }, { r: 5, t: 'maj9' }, { r: 0, t: 'sus4' }, { r: 10, t: 'maj7' }] },
  ],
};

/* Тритоновая замена доминанты и вторичные доминанты — лёгкая «джазовость». */
function reharmonize(bars, rnd, amount) {
  return bars.map((b, i) => {
    const c = { ...b };
    if (/^dom/.test(c.t) && R.chance(rnd, amount * 0.35)) {
      c.r = (c.r + 6) % 12;                       // тритоновая замена
      c.t = R.pick(rnd, ['dom13', 'domS9', 'dom9']);
    } else if (/^min/.test(c.t) && R.chance(rnd, amount * 0.25)) {
      c.t = c.t === 'min7' ? 'min9' : 'min11';    // расширение
    } else if (/^maj/.test(c.t) && R.chance(rnd, amount * 0.25)) {
      c.t = R.pick(rnd, ['maj9', 'maj69', 'majS11']);
    }
    return c;
  });
}
