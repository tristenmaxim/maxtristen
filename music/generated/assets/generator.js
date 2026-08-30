/* Композитор: из зерна собирает аранжировку и печатает код Strudel. */

const SCENES = {
  lofi: {
    label: 'Lo-Fi Beats',
    hint: 'Boom-bap, 70–82 BPM, родес и виниловый шум',
    bpm: [70, 82],
    tonality: [['minor', 7], ['major', 3]],
    modes: { minor: ['aeolian', 'dorian'], major: ['ionian', 'lydian'] },
    reharm: 0.5, chordScales: 'bebop',
    keySound: 'fmpiano', keyGain: 1.6, keyRoom: 0.35, keyLpf: [1600, 3400],
    bassSound: 'triangle', bassGain: 0.69,
    melSound: 'vibraphone_soft', melGain: 0.92, melReg: [65, 79], melDensity: 0.72,
    padSound: 'sawtooth', padGain: 0.02,
    drums: { bank: 'AkaiMPC60', gain: 0.79, swing: [0.11, 0.17], lpf: 7000 },
    texture: ['vinyl', 'hiss'],
    wow: 0.004, form: 'beat',
  },
  jazz: {
    label: 'Jazz Café',
    hint: 'Джазхоп, 82–92 BPM, рояль и щётки',
    bpm: [82, 92],
    tonality: [['major', 5], ['minor', 5]],
    modes: { minor: ['dorian', 'aeolian', 'harmonicMinor'], major: ['ionian', 'lydian', 'mixolydian'] },
    reharm: 0.85, chordScales: 'bebop',
    keySound: 'piano', keyGain: 1.3, keyRoom: 0.4, keyLpf: [2200, 5200],
    bassSound: 'triangle', bassGain: 0.62,
    melSound: 'piano', melGain: 0.7, melReg: [69, 86], melDensity: 0.78,
    padSound: 'sawtooth', padGain: 0.012,
    drums: { bank: 'LinnDrum', gain: 0.63, swing: [0.15, 0.22], lpf: 9000 },
    texture: ['vinyl'],
    wow: 0.003, form: 'beat',
  },
  focus: {
    label: 'Deep Focus',
    hint: 'Ровный пульс без барабанов, минимум гармонии',
    bpm: [60, 70],
    tonality: [['modal', 8], ['major', 2]],
    modes: { minor: ['dorian', 'aeolian'], major: ['ionian', 'lydian'], modal: ['dorian', 'lydian', 'majPent'] },
    reharm: 0.1, chordScales: 'plain',
    keySound: 'clavisynth', keyGain: 0.85, keyRoom: 0.6, keyLpf: [900, 2200],
    bassSound: 'sine', bassGain: 0.37,
    melSound: 'marimba', melGain: 0.62, melReg: [69, 86], melDensity: 0.8,
    padSound: 'sawtooth', padGain: 0.055,
    drums: null,
    texture: ['hiss', 'pulse'],
    wow: 0.002, form: 'pulse',
  },
  drift: {
    label: 'Ambient Drift',
    hint: 'Дроны и колокольчики, гармония почти не движется',
    bpm: [42, 54],
    tonality: [['modal', 10]],
    modes: { modal: ['lydian', 'majPent', 'kumoi', 'dorian'], minor: ['aeolian'], major: ['lydian'] },
    reharm: 0.05, chordScales: 'plain',
    keySound: 'psaltery_bow', keyGain: 0.8, keyRoom: 0.85, keyLpf: [700, 2000],
    bassSound: 'sine', bassGain: 0.33,
    melSound: 'glockenspiel', melGain: 0.5, melReg: [76, 93], melDensity: 0.3,
    padSound: 'sawtooth', padGain: 0.085,
    drums: null,
    texture: ['hiss', 'air'],
    wow: 0.005, form: 'ambient',
  },
  sleep: {
    label: 'Night Rain',
    hint: 'Дождь, приглушённое пианино, для сна',
    bpm: [46, 56],
    tonality: [['minor', 6], ['modal', 4]],
    modes: { minor: ['aeolian', 'dorian'], modal: ['minPent', 'dorian'], major: ['ionian'] },
    reharm: 0.15, chordScales: 'plain',
    keySound: 'piano', keyGain: 0.9, keyRoom: 0.8, keyLpf: [500, 1400],
    bassSound: 'sine', bassGain: 0.37,
    melSound: 'kalimba', melGain: 0.5, melReg: [59, 74], melDensity: 0.25,
    padSound: 'sawtooth', padGain: 0.065,
    drums: null,
    texture: ['rain', 'hiss'],
    wow: 0.006, form: 'ambient',
  },
};

/* ---------- ритмические кирпичи (сетка 16 шестнадцатых на такт) ---------- */

const KICKS = [
  [0, 7, 10], [0, 6, 10], [0, 3, 8, 14], [0, 10], [0, 7, 11], [0, 6, 9, 10],
  [0, 5, 10, 13], [0, 8], [0, 3, 10], [0, 7, 10, 15],
];
const SNARES = [[4, 12], [4, 12], [4, 12], [4, 11, 12], [4, 12, 14]];
const GHOSTS = [[], [7], [15], [3, 15], [7, 14], [2, 10]];
const HATS = [
  [0, 2, 4, 6, 8, 10, 12, 14],
  [0, 2, 4, 6, 8, 10, 12, 14],
  [0, 2, 3, 4, 6, 8, 10, 11, 12, 14],
  [2, 6, 10, 14],
  [0, 2, 4, 6, 7, 8, 10, 12, 14, 15],
];
const BASSES = [
  [[0, 'r', 6], [10, 'f', 4]],
  [[0, 'r', 8], [8, 'o', 4], [14, 'a', 2]],
  [[0, 'r', 10], [11, 'r', 4]],
  [[0, 'r', 4], [6, 'f', 3], [10, 'r', 4]],
  [[0, 'r', 14]],
  [[0, 'r', 6], [7, 'o', 3], [12, 'f', 3]],
];
const WALKS = [[[0, 'r', 4], [4, 's', 4], [8, 'f', 4], [12, 'a', 4]]];
const COMPS = {
  beat: [[[0, 12]], [[0, 6], [6, 8]], [[2, 6], [8, 7]], [[0, 5], [6, 3], [10, 5]], [[0, 3], [4, 3], [10, 6]], [[3, 6], [10, 6]]],
  pulse: [[[0, 16]], [[0, 8], [8, 8]], [[0, 12], [12, 4]]],
  ambient: [[[0, 26]], [[0, 30]], [[0, 18], [10, 14]]],
};
const MOTIFS = [
  [[0, 3], [3, 1], [4, 4], [10, 4]],
  [[0, 2], [2, 2], [6, 4], [12, 3]],
  [[2, 2], [4, 2], [7, 5], [14, 2]],
  [[0, 6], [8, 3], [11, 4]],
  [[0, 1], [1, 1], [2, 4], [8, 6]],
  [[4, 3], [7, 1], [8, 4], [14, 2]],
  [[0, 4], [6, 2], [8, 2], [10, 6]],
  [[6, 3], [10, 5]],
  [[0, 8], [10, 6]],
  [[0, 2], [3, 1], [4, 3], [8, 2], [11, 5]],
];

/* ---------- вспомогалки для мини-нотации ---------- */

const grid = (n = 16) => new Array(n).fill(null);
const mini = (cells) => cells.map((c) => (c === null || c === undefined ? '~' : c)).join(' ');
const isEmpty = (cells) => cells.every((c) => c === null || c === undefined);
const f2 = (x) => (Math.abs(x) < 0.1 ? Number(x).toFixed(4) : Number(x).toFixed(2)).replace(/0+$/, '').replace(/\.$/, '');

/* ---------- генератор ---------- */

function generateTrack(seed, sceneId, opts = {}) {
  const rnd = RNG(seed);
  const sc = SCENES[sceneId] || SCENES.lofi;
  const bars = opts.bars || 32;
  const intensity = opts.intensity ?? 0.6;

  // при продолжении сета частично наследуем тональность — сет звучит как одно целое
  const inh = opts.inherit && R.chance(rnd, 0.72) ? opts.inherit : null;
  const bpm = inh ? inh.bpm : R.int(rnd, sc.bpm[0], sc.bpm[1]);
  const tonicPc = inh ? inh.tonic : R.int(rnd, 0, 11);
  const family = inh ? inh.family : R.weighted(rnd, sc.tonality);
  const modeList = sc.modes[family] || sc.modes.minor || ['dorian'];
  const progSet = PROGRESSIONS[family] || PROGRESSIONS.minor;
  const progDef = R.pick(rnd, progSet);
  const prog = reharmonize(progDef.bars, rnd, sc.reharm);
  const loop = prog.length;

  // лад подбираем под тонический аккорд: мажорный аккорд — мажорная терция
  const tonicChord = prog.find((c) => c.r === 0) || prog[0];
  const wantThird = chordThird(tonicChord.t);
  const fitting = modeList.filter((m) => modeThird(m) === wantThird);
  const mode = inh ? inh.mode
    : R.pick(rnd, fitting.length ? fitting : [wantThird === 4 ? 'ionian' : 'aeolian']);

  // гармония: голосоведение по кругу, чтобы стык последнего и первого такта тоже был плавным
  const center = sc.form === 'ambient' ? 67 : 64;
  const range = sc.form === 'ambient' ? ['E3', 'C5'] : ['E3', 'A4'];
  let voicings = voiceProgressionIreal(prog, tonicPc, range);
  let voicedBy = 'ireal';
  if (!voicings) {
    voicedBy = 'встроенная таблица';
    voicings = [];
    let prev = null;
    for (let pass = 0; pass < 2; pass++) {
      for (let i = 0; i < loop; i++) {
        const pc = (tonicPc + prog[i].r) % 12;
        const v = voiceChord(pc, prog[i].t, prev, center, rnd);
        if (pass === 1) voicings[i] = v;
        prev = v;
      }
    }
  }

  const scaleSet = scaleNotes(tonicPc, mode, sc.melReg[0] - 12, sc.melReg[1] + 5);
  const chordName = (i) => pcName((tonicPc + prog[i].r) % 12) + CHORD_LABEL[prog[i].t];

  /* --- форма: какие слои звучат в каком такте --- */
  const sections = buildForm(bars, sc.form, rnd);

  /* --- ударные --- */
  const kickBase = R.pick(rnd, KICKS);
  const snareBase = R.pick(rnd, SNARES);
  const ghostBase = R.pick(rnd, GHOSTS);
  // часть треков получает хэты эвклидовым ритмом вместо готового паттерна
  const hatBase = R.chance(rnd, 0.3)
    ? euclidSteps(R.pick(rnd, [7, 9, 11]), 16, R.int(rnd, 0, 3)).map((on, i) => (on ? i : -1)).filter((i) => i >= 0)
    : R.pick(rnd, HATS);
  const percK = R.pick(rnd, [3, 5, 7]);
  const percRot = R.int(rnd, -3, 3);

  const kickBars = [], snareBars = [], hatBars = [], percBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sc.drums || !sec.drums) { kickBars.push(null); snareBars.push(null); hatBars.push(null); percBars.push(null); continue; }
    const fill = (b % 8 === 7) && R.chance(rnd, 0.55);

    const k = grid(), kg = grid();
    let kh = kickBase.slice();
    if (R.chance(rnd, 0.25)) kh = kh.concat([R.pick(rnd, [3, 6, 11, 14])]);
    if (R.chance(rnd, 0.15)) kh = kh.filter((x) => x !== kh[kh.length - 1]);
    for (const st of kh) { k[st] = 'bd'; kg[st] = f2(st === 0 ? 1 : 0.72 + rnd() * 0.22); }
    kickBars.push({ s: k, g: kg });

    const s = grid(), sg = grid();
    for (const st of snareBase) { s[st] = 'sd'; sg[st] = f2(0.82 + rnd() * 0.16); }
    for (const st of ghostBase) if (!s[st] && R.chance(rnd, 0.7)) { s[st] = 'sd'; sg[st] = f2(0.16 + rnd() * 0.12); }
    if (fill) { for (const st of [13, 14, 15]) { s[st] = 'sd'; sg[st] = f2(0.3 + (st - 12) * 0.2); } }
    snareBars.push({ s, g: sg });

    const h = grid(), hg = grid();
    let hits = hatBase.slice();
    if (R.chance(rnd, 0.3 * intensity)) hits = hits.concat([R.pick(rnd, [3, 7, 11, 15])]);
    for (const st of hits) { h[st] = 'hh'; hg[st] = f2((st % 4 === 0 ? 0.62 : 0.38) + rnd() * 0.14); }
    if (R.chance(rnd, 0.4)) { h[14] = 'oh'; hg[14] = f2(0.42); }
    hatBars.push({ s: h, g: hg });

    const p = grid(), pg = grid();
    if (sec.perc) {
      const voice = R.pick(rnd, ['rim', 'perc']);
      euclidSteps(percK, 16, percRot).forEach((on, st) => {
        if (!on || st % 4 === 0) return;              // не спорим с киком на долях
        p[st] = voice; pg[st] = f2(0.18 + rnd() * 0.2);
      });
    }
    percBars.push(isEmpty(p) ? null : { s: p, g: pg });
  }

  /* --- бас --- */
  const bassShape = sc.form === 'beat' && sceneId === 'jazz' && R.chance(rnd, 0.5) ? WALKS[0] : R.pick(rnd, BASSES);
  const bassBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.bass) { bassBars.push(null); continue; }
    const ci = b % loop;
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const nextPc = (tonicPc + prog[(ci + 1) % loop].r) % 12;
    const tones = chordTones(rootPc, prog[ci].t);
    const root = nearestPc(rootPc, sc.form === 'ambient' ? 40 : 40);
    const n = grid(), g = grid(), c = grid();
    const shape = sc.form === 'ambient' ? [[0, 'r', 30]] : bassShape;
    for (const [st, kind, len] of shape) {
      let note = root;
      if (kind === 'f') note = nearestPc((rootPc + 7) % 12, root + 3);
      else if (kind === 'o') note = root + 12;
      else if (kind === 's') note = nearestPc(tones[1], root + 4);
      else if (kind === 'a') note = nearestPc((nextPc + 11) % 12, root + 5);
      n[st] = note; g[st] = f2(0.75 + rnd() * 0.25); c[st] = f2(len);
    }
    bassBars.push({ n, g, c });
  }

  /* --- аккорды --- */
  const compShape = R.pick(rnd, COMPS[sc.form] || COMPS.beat);
  const keyBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.keys) { keyBars.push(null); continue; }
    const v = voicings[b % loop];
    const n = grid(), g = grid(), c = grid();
    let shape = compShape;
    if (sc.form === 'beat' && R.chance(rnd, 0.25)) shape = R.pick(rnd, COMPS.beat);
    shape.forEach(([st, len], idx) => {
      let voice = v;
      if (sc.form === 'beat' && idx > 0 && R.chance(rnd, 0.4)) voice = v.slice(1);      // «догоняющий» аккорд тоньше
      if (sc.form === 'ambient' && R.chance(rnd, 0.5)) voice = v.slice(0, 3);
      n[st] = '[' + voice.join(',') + ']';
      g[st] = f2((idx === 0 ? 0.9 : 0.6) + rnd() * 0.12);
      c[st] = f2(len);
    });
    keyBars.push({ n, g, c });
  }

  /* --- мелодия: мотив с развитием --- */
  const melBars = [];
  let motif = R.pick(rnd, MOTIFS);
  let lastNote = R.pick(rnd, scaleSet.filter((x) => x >= sc.melReg[0] && x <= sc.melReg[1]));
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.melody) { melBars.push(null); continue; }
    const phrasePos = b % 4;
    if (phrasePos === 0) motif = R.chance(rnd, 0.55) ? motif : R.pick(rnd, MOTIFS);
    if (phrasePos === 2 && R.chance(rnd, 0.5)) motif = varyMotif(motif, rnd);
    if (phrasePos === 3 && R.chance(rnd, 0.45)) { melBars.push(null); continue; }  // дыхание фразы

    const ci = b % loop;
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const tones = chordTones(rootPc, prog[ci].t);
    const chordSet = chordNotesInRange(rootPc, prog[ci].t, sc.melReg[0] - 2, sc.melReg[1]);
    // над каждым аккордом свой лад: над доминантой альтерация, над минором
    // дорийский бибоп. Опорные ноты — из аккорда, проходящие — отсюда.
    const cs = chordScaleNotes(rootPc, prog[ci].t, sc.melReg[0] - 2, sc.melReg[1], sc.chordScales);
    const weakPool = cs && cs.length > 4 ? cs : scaleSet;
    const n = grid(), g = grid(), c = grid();
    const arch = Math.sin(((b % 8) / 8) * Math.PI);      // подъём к середине фразы
    motif.forEach(([st, len], idx) => {
      const dens = sc.melDensity + intensity * 0.2 + (sec.name === 'C' ? 0.15 : 0);
      if (rnd() > dens) return;
      const strong = st % 4 === 0;
      const target = sc.melReg[0] + (sc.melReg[1] - sc.melReg[0]) * (0.3 + 0.45 * arch);
      const step = R.weighted(rnd, [[-4, 1], [-3, 2], [-2, 4], [-1, 6], [0, 2], [1, 6], [2, 4], [3, 2], [4, 1]]);
      const pool = strong || idx === 0 ? chordSet : weakPool;
      let cand = lastNote + step * 2;
      cand = cand * 0.72 + target * 0.28;
      let note = snapToSet(cand, pool.filter((x) => x >= sc.melReg[0] - 2 && x <= sc.melReg[1]));
      if (note === lastNote && R.chance(rnd, 0.6)) {
        const alt = pool.filter((x) => Math.abs(x - lastNote) > 0 && Math.abs(x - lastNote) <= 5);
        if (alt.length) note = R.pick(rnd, alt);
      }
      lastNote = note;
      n[st] = note; g[st] = f2((strong ? 0.85 : 0.6) + rnd() * 0.15); c[st] = f2(len);
    });
    melBars.push(isEmpty(n) ? null : { n, g, c });
  }

  /* --- подкладка (дрон/пэд) --- */
  const padBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.pad) { padBars.push(null); continue; }
    const ci = b % loop;
    const v = voicings[ci];
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const low = nearestPc(rootPc, 41);
    const notes = [...new Set([low, low + 12, v[v.length - 1]])];
    padBars.push('[' + notes.join(',') + ']');
  }

  const meta = {
    seed, sceneId, scene: sc.label, bpm, bars,
    key: pcName(tonicPc) + ' ' + MODE_LABEL[mode],
    tonic: tonicPc, mode, family, progression: progDef.name, voicedBy,
    chords: prog.map((_, i) => chordName(i)),
    sections,
  };

  const code = renderCode({
    sc, sceneId, rnd, bpm, bars, intensity, sections,
    kickBars, snareBars, hatBars, percBars, bassBars, keyBars, melBars, padBars,
    meta, master: opts.master ?? 1, brightness: opts.brightness ?? 0.5, space: opts.space ?? 0.5,
    tex: opts.texture ?? 0.35,
  });

  return { code, meta, notesUsed: collectNotes({ bassBars, keyBars, melBars, padBars }) };
}

const CHORD_LABEL = {
  maj7: 'maj7', maj9: 'maj9', maj69: '6/9', majS11: 'maj7#11', min7: 'm7', min9: 'm9', min11: 'm11',
  min6: 'm6', minMaj7: 'mMaj7', dom7: '7', dom9: '9', dom13: '13', domS9: '7#9', domB9: '7b9',
  domB13: '7b13', m7b5: 'm7b5', dim7: 'dim7', sus2: 'sus2', sus4: 'sus4', sus7: '7sus4', add9: 'add9',
  domAlt: '7alt', domS11: '7#11', dom13S11: '13#11', dom13B9: '13b9', min69: 'm6/9',
  sus9: '9sus', sus13: '13sus',
};
const MODE_LABEL = {
  ionian: 'ionian', dorian: 'dorian', phrygian: 'phrygian', lydian: 'lydian', mixolydian: 'mixolydian',
  aeolian: 'aeolian', harmonicMinor: 'harm. minor', majPent: 'maj pent', minPent: 'min pent',
  kumoi: 'kumoi', hirajoshi: 'hirajoshi',
};

function varyMotif(motif, rnd) {
  const out = motif.map(([st, len]) => [st, len]);
  const op = R.int(rnd, 0, 2);
  if (op === 0 && out.length > 1) out.pop();
  else if (op === 1) { const i = R.int(rnd, 0, out.length - 1); out[i] = [Math.min(15, out[i][0] + R.pick(rnd, [1, 2, -1])), out[i][1]]; }
  else { const i = R.int(rnd, 0, out.length - 1); out[i] = [out[i][0], Math.max(1, out[i][1] + R.pick(rnd, [1, -1, 2]))]; }
  return out.sort((a, b) => a[0] - b[0]).filter((x, i, a) => i === 0 || x[0] !== a[i - 1][0]);
}

/* Форма трека. Каждому такту — набор активных слоёв. */
function buildForm(bars, form, rnd) {
  const out = [];
  const withDrums = form === 'beat';
  for (let b = 0; b < bars; b++) {
    const q = Math.floor(b / (bars / 8));   // 8 фаз
    let sec = { name: 'A', drums: withDrums, bass: true, keys: true, melody: true, pad: true, perc: false };
    if (q === 0) sec = { name: 'intro', drums: false, bass: false, keys: true, melody: false, pad: true, perc: false };
    else if (q === 1) sec = { name: 'A', drums: withDrums, bass: true, keys: true, melody: false, pad: true, perc: false };
    else if (q === 2 || q === 3) sec = { name: 'B', drums: withDrums, bass: true, keys: true, melody: true, pad: true, perc: R.chance(rnd, 0.5) };
    else if (q === 4) sec = { name: 'break', drums: false, bass: form !== 'ambient', keys: true, melody: true, pad: true, perc: false };
    else if (q === 5 || q === 6) sec = { name: 'C', drums: withDrums, bass: true, keys: true, melody: true, pad: true, perc: true };
    else sec = { name: 'outro', drums: withDrums && b < bars - 2, bass: true, keys: true, melody: b < bars - 2, pad: true, perc: false };
    out.push(sec);
  }
  return out;
}

function collectNotes({ bassBars, keyBars, melBars, padBars }) {
  const set = new Set();
  const add = (x) => { if (typeof x === 'number') set.add(x); };
  for (const arr of [bassBars, keyBars, melBars]) {
    for (const bar of arr) if (bar) for (const cell of bar.n) {
      if (cell === null) continue;
      if (typeof cell === 'number') add(cell);
      else String(cell).replace(/[[\]]/g, '').split(',').forEach((x) => add(Number(x)));
    }
  }
  for (const p of padBars) if (p) String(p).replace(/[[\]]/g, '').split(',').forEach((x) => add(Number(x)));
  return [...set].sort((a, b) => a - b);
}

/* ---------- печать кода Strudel ---------- */

function catOf(items, fn) {
  const parts = items.map((it) => (it === null ? 'silence' : fn(it)));
  return 'cat(\n    ' + parts.join(',\n    ') + '\n  )';
}

function renderCode(ctx) {
  const { sc, sceneId, bpm, bars, sections, meta } = ctx;
  const master = ctx.master, bright = ctx.brightness, space = ctx.space;
  const L = [];
  const lpfLo = sc.keyLpf[0], lpfHi = sc.keyLpf[1];
  const cutoff = Math.round(lpfLo + (lpfHi - lpfLo) * (0.25 + bright * 1.1));
  const room = (v) => f2(Math.min(0.95, v * (0.6 + space * 0.9)));
  const gain = (v) => f2(v * master);

  L.push('// ' + meta.scene + ' · ' + meta.key + ' · ' + bpm + ' BPM · seed ' + meta.seed);
  L.push('// ' + meta.progression + ': ' + meta.chords.join(' | '));
  L.push('// вольтовки: ' + meta.voicedBy + (meta.voicedBy === 'ireal' ? ' (словарь iReal из @strudel/tonal)' : ''));
  L.push('setcps(' + (bpm / 60 / 4).toFixed(5) + ')');
  L.push('');
  L.push('stack(');

  const layers = [];

  if (sc.drums) {
    const d = sc.drums;
    const drumLayer = (arr, extra) => catOf(arr, (b) => 's("' + mini(b.s) + '").gain("' + mini(b.g) + '")') + extra;
    const dl = [];
    if (ctx.kickBars.some(Boolean)) dl.push('  ' + drumLayer(ctx.kickBars, '.postgain(' + gain(1.1 * d.gain) + ').shape(0.16)'));
    if (ctx.snareBars.some(Boolean)) dl.push('  ' + drumLayer(ctx.snareBars, '.postgain(' + gain(0.8 * d.gain) + ').room(' + room(0.28) + ').roomsize(2).nudge(0.015)'));
    if (ctx.hatBars.some(Boolean)) dl.push('  ' + drumLayer(ctx.hatBars, '.postgain(' + gain(0.5 * d.gain) + ').pan(sine.range(0.4,0.6).slow(7)).nudge(-0.005)'));
    if (ctx.percBars.some(Boolean)) dl.push('  ' + drumLayer(ctx.percBars, '.postgain(' + gain(0.45 * d.gain) + ').pan(perlin.range(0.25,0.75)).room(' + room(0.3) + ')'));
    layers.push('  // ударные — ' + d.bank + '\n  stack(\n  ' + dl.join(',\n  ') + '\n  ).bank("' + d.bank + '").lpf(' + Math.round(d.lpf * (0.6 + bright * 0.8)) + ').orbit(1)');
  }

  if (ctx.bassBars.some(Boolean)) {
    layers.push('  // бас\n  ' + catOf(ctx.bassBars, (b) =>
      'note("' + mini(b.n) + '").gain("' + mini(b.g) + '").clip("' + mini(b.c) + '")')
      + '.s("' + sc.bassSound + '").attack(0.012).release(0.14).lpf(' + Math.round(220 + bright * 260)
      + ').postgain(' + gain(sc.bassGain) + ').orbit(2)');
  }

  if (ctx.keyBars.some(Boolean)) {
    layers.push('  // гармония — ' + sc.keySound + '\n  ' + catOf(ctx.keyBars, (b) =>
      'note("' + mini(b.n) + '").gain("' + mini(b.g) + '").clip("' + mini(b.c) + '")')
      + '.s("' + sc.keySound + '")'
      + '.lpf(perlin.range(' + Math.round(cutoff * 0.7) + ',' + Math.round(cutoff * 1.35) + ').slow(17))'
      + '.speed(sine.range(' + (1 - sc.wow).toFixed(4) + ',' + (1 + sc.wow).toFixed(4) + ').slow(9))'
      + '.room(' + room(sc.keyRoom) + ').roomsize(' + f2(2 + space * 4) + ')'
      + '.pan(sine.range(0.42,0.58).slow(23))'
      + '.off(' + (sc.form === 'ambient' ? '1/6' : '1/8') + ', x => x.add(note(12)).mul(gain(0.22)))'
      + '.nudge(rand.range(-0.004,0.012))'
      + '.postgain(' + gain(sc.keyGain) + ').orbit(3)');
  }

  if (ctx.melBars.some(Boolean)) {
    layers.push('  // мелодия — ' + sc.melSound + '\n  ' + catOf(ctx.melBars, (b) =>
      'note("' + mini(b.n) + '").gain("' + mini(b.g) + '").clip("' + mini(b.c) + '")')
      + '.s("' + sc.melSound + '")'
      + '.lpf(' + Math.round(2200 + bright * 5000) + ')'
      + (sc.form === 'ambient' ? '.echo(3, 1/3, 0.45)' : '')
      + '.delay(' + f2(0.22 + space * 0.3) + ').delaytime(' + (60 / bpm * 0.75).toFixed(3) + ').delayfeedback(' + f2(0.28 + space * 0.2) + ')'
      + '.room(' + room(0.55) + ').roomsize(' + f2(3 + space * 4) + ')'
      + '.pan(perlin.range(0.34,0.66).slow(13))'
      + '.nudge(rand.range(-0.006,0.018))'
      + '.postgain(' + gain(sc.melGain) + ').orbit(4)');
  }

  if (ctx.padBars.some(Boolean)) {
    layers.push('  // подкладка\n  ' + catOf(ctx.padBars, (n) => 'note("' + n + '")')
      + '.s("' + sc.padSound + '").attack(' + f2(0.9 + space) + ').release(' + f2(1.4 + space * 2) + ').clip(1.15)'
      + '.lpf(perlin.range(' + Math.round(260 + bright * 200) + ',' + Math.round(700 + bright * 900) + ').slow(29))'
      + '.lpq(1.4)'
      + '.room(' + room(0.9) + ').roomsize(' + f2(5 + space * 5) + ')'
      + '.postgain(' + gain(sc.padGain) + ').orbit(5)');
  }

  // Шумовые слои держим непрерывными: одно событие на 8 тактов вместо
  // перезапуска каждый такт — иначе фон «дышит» в темп.
  const tex = ctx.tex;
  const tg = (v) => f2(v * tex * ctx.master);
  // Плоская огибающая и стык встык: событие длиной ровно в такт, без спада к
  // sustain и без хвоста — иначе шум «дышит» в темп на каждом стыке.
  const hold = '.clip(1).attack(0.05).decay(0).sustain(1).release(0.05)';
  if (tex > 0.01) for (const t of sc.texture) {
    if (t === 'vinyl') layers.push('  // винил\n  s("crackle")' + hold + '.density(' + f2(6 + ctx.intensity * 8) + ').hpf(240).lpf(' + Math.round(3000 + bright * 2500) + ').postgain(' + tg(0.086) + ').orbit(6)');
    if (t === 'hiss') layers.push('  // лента\n  s("pink")' + hold + '.hpf(600).lpf(3800).postgain(' + tg(0.051) + ').orbit(6)');
    if (t === 'air') layers.push('  // воздух\n  s("pink")' + hold + '.hpf(1400).lpf(sine.range(2600,7000).slow(31)).postgain(' + tg(0.034) + ').pan(sine.range(0.3,0.7).slow(19)).orbit(6)');
    if (t === 'rain') layers.push('  // дождь\n  stack(\n    s("brown")' + hold + '.lpf(1100).hpf(180).postgain(' + tg(0.23) + '),\n    s("crackle")' + hold + '.density(70).hpf(900).lpf(6000).postgain(' + tg(0.034) + ')\n  ).pan(sine.range(0.35,0.65).slow(37)).orbit(6)');
  }
  for (const t of sc.texture) {
    if (t === 'pulse') layers.push('  // пульс\n  s("hh").bank("RolandCompurhythm78").struct("t ~ ~ ~ t ~ ~ ~").gain(0.24).lpf(3000).room(' + room(0.5) + ').postgain(' + gain(0.35) + ').orbit(7)');
  }

  L.push(layers.join(',\n'));
  L.push(')');
  const swing = sc.drums ? R.pick(ctx.rnd, [sc.drums.swing[0], (sc.drums.swing[0] + sc.drums.swing[1]) / 2, sc.drums.swing[1]]) : 0;
  if (swing) L.push('.swingBy(' + f2(swing) + ', 8)');
  L.push('.postgain(0.46).analyze(1)');
  return L.join('\n');
}
