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
    drums: { kits: ['mpc', 'crate', 'crate', 'sp12'], gain: 0.79, lpf: 7000 },
    grooves: ['mpc', 'hard', 'dilla', 'laidback'],
    counterSound: 'kalimba', counterGain: 0.34,
    crush: 11, drumShape: 0.24,
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
    drums: { kits: ['linn', 'mpc', 'crate'], gain: 0.63, lpf: 9000 },
    grooves: ['mpc', 'hard', 'light'],
    counterSound: 'vibraphone_soft', counterGain: 0.3,
    crush: 14, drumShape: 0.14,
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
    grooves: ['straight', 'light'],
    counterSound: 'kalimba', counterGain: 0.26,
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
    grooves: ['straight'],
    counterSound: 'handbells', counterGain: 0.22,
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
    grooves: ['straight'],
    counterSound: null,
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

/* ---------- наборы барабанов ---------- */

const KITS = {
  mpc:   { trim: 1.0,  pre: 'AkaiMPC60_',           n: { bd: 2,  sd: 3,  hh: 1,  oh: 1,  rim: 1, perc: 5  } },
  linn:  { trim: 1.05, pre: 'LinnDrum_',            n: { bd: 1,  sd: 3,  hh: 3,  oh: 1,  rim: 3, perc: 6  } },
  sp12:  { trim: 1.0,  pre: 'EmuSP12_',             n: { bd: 14, sd: 21, hh: 2,  oh: 1,  rim: 2, perc: 1  } },
  cr78:  { trim: 1.1,  pre: 'RolandCompurhythm78_', n: { bd: 1,  sd: 1,  hh: 2,  oh: 2,  rim: 0, perc: 8  } },
  tr808: { trim: 0.9,  pre: 'RolandTR808_',         n: { bd: 25, sd: 25, hh: 1,  oh: 5,  rim: 1, perc: 16 } },
  crate: { trim: 1.3,  pre: 'crate_',               n: { bd: 53, sd: 54, hh: 49, oh: 34, rim: 3, perc: 40 } },
};

/* Набор выбирается один раз на трек, вместе с конкретным экземпляром каждого
   инструмента — у крейта их полсотни, поэтому у каждого трека своя бочка. */
function pickKit(rnd, names) {
  const name = R.pick(rnd, names);
  const kit = KITS[name];
  const idx = {};
  for (const slot of Object.keys(kit.n)) idx[slot] = kit.n[slot] > 0 ? R.int(rnd, 0, kit.n[slot] - 1) : 0;
  return { name, kit, idx };
}
const drumToken = (sel, slot) => {
  if (!sel.kit.n[slot]) slot = 'perc';
  return sel.kit.pre + slot + ':' + (sel.idx[slot] || 0);
};

/* ---------- фразы ----------
   Единица не такт, а фраза в два или четыре такта: вариации закреплены за
   позицией в фразе и повторяются, а не бросаются заново каждый такт. */

function makeDrumPhrase(rnd, len, intensity) {
  const kick = R.pick(rnd, KICKS);
  const snare = R.pick(rnd, SNARES);
  const ghost = R.pick(rnd, GHOSTS);
  const hat = R.chance(rnd, 0.3)
    ? euclidSteps(R.pick(rnd, [7, 9, 11]), 16, R.int(rnd, 0, 3)).map((on, i) => (on ? i : -1)).filter((i) => i >= 0)
    : R.pick(rnd, HATS);
  // решения принимаются один раз — дальше повторяются в каждой фразе
  const pickup = R.pick(rnd, [14, 15, 11]);
  const dropLast = R.chance(rnd, 0.5);
  const extraKick = R.pick(rnd, [3, 6, 11, 14]);
  const openHatAt = R.chance(rnd, 0.6) ? 14 : -1;
  const ghostBars = [];
  for (let i = 0; i < len; i++) ghostBars.push(R.chance(rnd, 0.6));

  const out = [];
  for (let i = 0; i < len; i++) {
    const last = i === len - 1;
    let k = kick.slice();
    if (i % 2 === 1) {
      if (dropLast && k.length > 2) k = k.slice(0, -1);
      k = k.concat([pickup]);
    }
    if (last && intensity > 0.5) k = k.concat([extraKick]);
    const s = snare.slice();
    const g = ghostBars[i] ? ghost : [];
    const h = hat.slice();
    out.push({ kick: [...new Set(k)].sort((a, b) => a - b), snare: s, ghost: g, hat: h, openHat: last ? openHatAt : -1, fill: last });
  }
  return out;
}

/* Бас сцеплен с бочкой: либо бьёт вместе с ней, либо намеренно уходит в
   промежутки. Независимые друг от друга бас и бочка — главная причина, по
   которой генеративный бит звучит рыхло. */
function makeBassPhrase(rnd, drums, style, len) {
  const out = [];
  for (let i = 0; i < len; i++) {
    const kicks = drums[i].kick;
    const shape = [];
    if (style === 'walk') {
      const kinds = ['r', 's', 'f', 'a'];
      for (let q = 0; q < 4; q++) shape.push([q * 4, kinds[q], 4]);
    } else if (style === 'lock') {
      kicks.slice(0, 4).forEach((st, j) => {
        const next = kicks[j + 1] !== undefined ? kicks[j + 1] : 16;
        shape.push([st, j === 0 ? 'r' : R.pick(rnd, ['r', 'o', 'f']), Math.max(2, next - st)]);
      });
    } else if (style === 'drone') {
      shape.push([0, 'r', 30]);
    } else {
      // complement: корень на первой доле, остальное в дырах между бочками
      shape.push([0, 'r', Math.max(3, (kicks[1] || 8) - 0)]);
      const holes = [2, 6, 10, 14].filter((st) => !kicks.includes(st) && !kicks.includes(st - 1));
      const take = R.shuffle(rnd, holes).slice(0, R.int(rnd, 1, 2)).sort((a, b) => a - b);
      take.forEach((st) => shape.push([st, R.pick(rnd, ['f', 'o', 'r']), 3]));
    }
    if (i === len - 1 && style !== 'drone' && R.chance(rnd, 0.6)) shape.push([14, 'a', 2]);
    out.push(shape.sort((a, b) => a[0] - b[0]));
  }
  return out;
}

function makeCompPhrase(rnd, form, len) {
  const base = R.pick(rnd, COMPS[form] || COMPS.beat);
  const push = R.chance(rnd, 0.5);
  const out = [];
  for (let i = 0; i < len; i++) {
    let shape = base.map(([st, l]) => [st, l]);
    if (i % 2 === 1 && push && shape.length) shape = shape.map(([st, l], j) => (j === 0 ? [Math.max(0, st === 0 ? 0 : st - 1), l] : [st, l]));
    if (i === len - 1 && shape.length > 1) shape = shape.slice(0, -1);   // к концу фразы разрежаем
    out.push(shape);
  }
  return out;
}

/* ---------- генератор ---------- */

function generateTrack(seed, sceneId, opts = {}) {
  const rnd = RNG(seed);
  const sc = SCENES[sceneId] || SCENES.lofi;
  const bars = opts.bars || 32;
  const intensity = opts.intensity ?? 0.6;

  const inh = opts.inherit && (opts.inherit.hard || R.chance(rnd, 0.72)) ? opts.inherit : null;
  const bpm = inh ? inh.bpm : R.int(rnd, sc.bpm[0], sc.bpm[1]);
  const tonicPc = inh ? inh.tonic : R.int(rnd, 0, 11);
  const family = inh ? inh.family : R.weighted(rnd, sc.tonality);
  const modeList = sc.modes[family] || sc.modes.minor || ['dorian'];
  const progSet = PROGRESSIONS[family] || PROGRESSIONS.minor;
  const progDef = inh && inh.progDef ? inh.progDef : R.pick(rnd, progSet);
  const prog = inh && inh.prog ? inh.prog : reharmonize(progDef.bars, rnd, sc.reharm);
  const loop = prog.length;

  const tonicChord = prog.find((c) => c.r === 0) || prog[0];
  const wantThird = chordThird(tonicChord.t);
  const fitting = modeList.filter((m) => modeThird(m) === wantThird);
  const mode = inh ? inh.mode
    : R.pick(rnd, fitting.length ? fitting : [wantThird === 4 ? 'ionian' : 'aeolian']);

  const groove = makeGroove(rnd, bpm, R.pick(rnd, sc.grooves));
  const kitSel = sc.drums ? pickKit(rnd, sc.drums.kits) : null;

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
  const sections = buildForm(bars, sc.form, rnd);

  const phraseLen = sc.form === 'beat' ? R.pick(rnd, [2, 2, 4]) : 2;
  const drumPhrase = sc.drums ? makeDrumPhrase(rnd, phraseLen, intensity) : null;
  const bassStyle = sc.form === 'ambient' ? 'drone'
    : sceneId === 'jazz' && R.chance(rnd, 0.45) ? 'walk'
    : R.pick(rnd, ['lock', 'complement', 'lock']);
  const bassPhrase = makeBassPhrase(rnd, drumPhrase || new Array(phraseLen).fill({ kick: [0, 10] }), bassStyle, phraseLen);
  const compPhrase = makeCompPhrase(rnd, sc.form, phraseLen);
  const percVoice = R.pick(rnd, ['rim', 'perc']);
  const percK = R.pick(rnd, [3, 5, 7]);
  const percRot = R.int(rnd, -3, 3);

  const gr = (st, base) => f2(base * groove.a[st]);
  const nud = (st) => f2(groove.t[st]);

  /* --- ударные --- */
  const kickBars = [], snareBars = [], hatBars = [], percBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sc.drums || !sec.drums) { kickBars.push(null); snareBars.push(null); hatBars.push(null); percBars.push(null); continue; }
    const ph = drumPhrase[b % phraseLen];
    const bigFill = (b % 8 === 7) && ph.fill;

    const k = grid(), kg = grid(), kn = grid();
    for (const st of ph.kick) { k[st] = drumToken(kitSel, 'bd'); kg[st] = gr(st, st === 0 ? 1 : 0.82); kn[st] = nud(st); }
    kickBars.push({ s: k, g: kg, n: kn });

    const s = grid(), sg = grid(), sn = grid();
    for (const st of ph.snare) { s[st] = drumToken(kitSel, 'sd'); sg[st] = gr(st, 0.92); sn[st] = nud(st); }
    for (const st of ph.ghost) if (!s[st]) { s[st] = drumToken(kitSel, 'sd'); sg[st] = gr(st, 0.2); sn[st] = nud(st); }
    if (bigFill) for (const st of [13, 14, 15]) { s[st] = drumToken(kitSel, 'sd'); sg[st] = gr(st, 0.32 + (st - 12) * 0.18); sn[st] = nud(st); }
    snareBars.push({ s, g: sg, n: sn });

    const h = grid(), hg = grid(), hn = grid();
    for (const st of ph.hat) { h[st] = drumToken(kitSel, 'hh'); hg[st] = gr(st, 0.6); hn[st] = nud(st); }
    if (ph.openHat >= 0) { h[ph.openHat] = drumToken(kitSel, 'oh'); hg[ph.openHat] = gr(ph.openHat, 0.5); hn[ph.openHat] = nud(ph.openHat); }
    hatBars.push({ s: h, g: hg, n: hn });

    const p = grid(), pg = grid(), pn = grid();
    if (sec.perc) {
      const voice = drumToken(kitSel, percVoice);
      euclidSteps(percK, 16, percRot).forEach((on, st) => {
        if (!on || st % 4 === 0) return;
        p[st] = voice; pg[st] = gr(st, 0.34); pn[st] = nud(st);
      });
    }
    percBars.push(isEmpty(p) ? null : { s: p, g: pg, n: pn });
  }

  /* --- бас --- */
  const bassBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.bass) { bassBars.push(null); continue; }
    const ci = b % loop;
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const nextPc = (tonicPc + prog[(ci + 1) % loop].r) % 12;
    const tones = chordTones(rootPc, prog[ci].t);
    const root = nearestPc(rootPc, 40);
    const n = grid(), g = grid(), c = grid(), nn = grid();
    for (const [st, kind, len] of bassPhrase[b % phraseLen]) {
      let note = root;
      if (kind === 'f') note = nearestPc((rootPc + 7) % 12, root + 3);
      else if (kind === 'o') note = root + 12;
      else if (kind === 's') note = nearestPc(tones[1], root + 4);
      else if (kind === 'a') note = nearestPc((nextPc + 11) % 12, root + 5);
      n[st] = note; g[st] = gr(st, 0.9); c[st] = f2(len); nn[st] = nud(st);
    }
    bassBars.push({ n, g, c, nu: nn });
  }

  /* --- аккорды --- */
  const keyBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.keys) { keyBars.push(null); continue; }
    const v = voicings[b % loop];
    const kicksHere = drumPhrase && sec.drums ? drumPhrase[b % phraseLen].kick : [];
    const n = grid(), g = grid(), c = grid(), nn = grid();
    compPhrase[b % phraseLen].forEach(([st, len], idx) => {
      let voice = v;
      if (sc.form === 'beat' && idx > 0) voice = v.slice(1);
      if (sc.form === 'ambient' && idx > 0) voice = v.slice(0, 3);
      // мягкая подкачка: аккорд уступает бочке
      const duckAmt = kicksHere.includes(st) ? 0.68 : kicksHere.includes(st - 1) ? 0.84 : 1;
      n[st] = '[' + voice.join(',') + ']';
      g[st] = gr(st, (idx === 0 ? 0.95 : 0.66) * duckAmt);
      c[st] = f2(len); nn[st] = nud(st);
    });
    keyBars.push({ n, g, c, nu: nn });
  }

  /* --- мелодия: вопрос — ответ, с кульминацией --- */
  const motifA = R.pick(rnd, MOTIFS);
  const motifB = varyMotif(motifA, rnd);
  const thin = (m) => m.filter((_, i) => i % 2 === 0);
  const cadence = (m) => m.slice(-2);
  const melPlan = [motifA, thin(motifA), motifA, cadence(motifB)];   // фраза на 4 такта

  const melBars = [];
  let lastNote = R.pick(rnd, scaleSet.filter((x) => x >= sc.melReg[0] && x <= sc.melReg[1]));
  const climaxBar = sections.findIndex((s) => s.name === 'C');
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.melody) { melBars.push(null); continue; }
    const pos = b % 4;
    const motif = melPlan[pos];
    if (!motif.length) { melBars.push(null); continue; }

    const ci = b % loop;
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const chordSet = chordNotesInRange(rootPc, prog[ci].t, sc.melReg[0] - 2, sc.melReg[1]);
    const cs = chordScaleNotes(rootPc, prog[ci].t, sc.melReg[0] - 2, sc.melReg[1], sc.chordScales);
    const weakPool = cs && cs.length > 4 ? cs : scaleSet;
    const n = grid(), g = grid(), c = grid(), nn = grid();
    const arch = Math.sin(((b % 8) / 8) * Math.PI);
    const isClimax = climaxBar >= 0 && b === climaxBar;
    const lift = isClimax ? 0.3 : 0;
    motif.forEach(([st, len], idx) => {
      const dens = sc.melDensity + intensity * 0.2 + (sec.name === 'C' ? 0.15 : 0);
      if (idx > 0 && rnd() > dens) return;
      const strong = st % 4 === 0;
      const target = sc.melReg[0] + (sc.melReg[1] - sc.melReg[0]) * (0.3 + 0.45 * arch + lift);
      const step = R.weighted(rnd, [[-4, 1], [-3, 2], [-2, 4], [-1, 6], [0, 2], [1, 6], [2, 4], [3, 2], [4, 1]]);
      const pool = strong || idx === 0 ? chordSet : weakPool;
      let cand = (lastNote + step * 2) * 0.72 + target * 0.28;
      // ответ фразы приходит к аккордовому тону — это и делает её ответом
      if (pos === 3 && idx === motif.length - 1) cand = target - 3;
      let note = snapToSet(cand, pool.filter((x) => x >= sc.melReg[0] - 2 && x <= sc.melReg[1]));
      if (isClimax && idx === 0) note = Math.max(note, sc.melReg[1] - 3);
      if (note === lastNote && R.chance(rnd, 0.6)) {
        const alt = pool.filter((x) => Math.abs(x - lastNote) > 0 && Math.abs(x - lastNote) <= 5);
        if (alt.length) note = R.pick(rnd, alt);
      }
      lastNote = note;
      n[st] = note; g[st] = gr(st, strong ? 0.95 : 0.72); c[st] = f2(len); nn[st] = nud(st);
    });
    melBars.push(isEmpty(n) ? null : { n, g, c, nu: nn });
  }

  /* --- второй голос: отвечает в паузах мелодии --- */
  const counterBars = [];
  if (sc.counterSound) {
    for (let b = 0; b < bars; b++) {
      const sec = sections[b];
      const melEmpty = !melBars[b];
      if (!sec.melody || (!melEmpty && !R.chance(rnd, 0.25))) { counterBars.push(null); continue; }
      const v = voicings[b % loop];
      const n = grid(), g = grid(), c = grid(), nn = grid();
      const taken = melBars[b] ? melBars[b].n.map((x, i) => (x === null ? -1 : i)).filter((i) => i >= 0) : [];
      const spots = [2, 6, 10, 14].filter((st) => !taken.includes(st));
      R.shuffle(rnd, spots).slice(0, R.int(rnd, 1, 2)).forEach((st, j) => {
        const note = v[Math.min(v.length - 1, v.length - 1 - j)] + (sc.form === 'beat' ? 12 : 0);
        n[st] = note; g[st] = gr(st, 0.7); c[st] = f2(4); nn[st] = nud(st);
      });
      counterBars.push(isEmpty(n) ? null : { n, g, c, nu: nn });
    }
  } else for (let b = 0; b < bars; b++) counterBars.push(null);

  /* --- подкладка --- */
  const padBars = [];
  for (let b = 0; b < bars; b++) {
    const sec = sections[b];
    if (!sec.pad) { padBars.push(null); continue; }
    const ci = b % loop;
    const v = voicings[ci];
    const rootPc = (tonicPc + prog[ci].r) % 12;
    const low = nearestPc(rootPc, 41);
    padBars.push('[' + [...new Set([low, low + 12, v[v.length - 1]])].join(',') + ']');
  }

  const meta = {
    seed, sceneId, scene: sc.label, bpm, bars,
    key: pcName(tonicPc) + ' ' + MODE_LABEL[mode],
    tonic: tonicPc, mode, family, progression: progDef.name, progDef, prog, voicedBy,
    groove: groove.name, kit: kitSel ? kitSel.name : null, phraseLen, bassStyle,
    chords: prog.map((_, i) => chordName(i)),
    sections,
  };

  const code = renderCode({
    sc, sceneId, rnd, bpm, bars, intensity, sections, kitSel,
    kickBars, snareBars, hatBars, percBars, bassBars, keyBars, melBars, counterBars, padBars,
    meta, master: opts.master ?? 1, brightness: opts.brightness ?? 0.5, space: opts.space ?? 0.5,
    tex: opts.texture ?? 0.35,
  });

  return { code, meta, notesUsed: collectNotes({ bassBars, keyBars, melBars, counterBars, padBars }) };
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

function collectNotes({ bassBars, keyBars, melBars, counterBars, padBars }) {
  const set = new Set();
  const add = (x) => { if (typeof x === 'number') set.add(x); };
  for (const arr of [bassBars, keyBars, melBars, counterBars]) {
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
  const crush = sc.crush ? '.crush(' + sc.crush + ')' : '';

  L.push('// ' + meta.scene + ' · ' + meta.key + ' · ' + bpm + ' BPM · seed ' + meta.seed);
  L.push('// ' + meta.progression + ': ' + meta.chords.join(' | '));
  L.push('// вольтовки: ' + meta.voicedBy + (meta.voicedBy === 'ireal' ? ' (словарь iReal из @strudel/tonal)' : ''));
  L.push('// грув: ' + meta.groove + ' · фраза ' + meta.phraseLen + ' такта · бас ' + meta.bassStyle
    + (meta.kit ? ' · барабаны ' + meta.kit : ''));
  L.push('setcps(' + (bpm / 60 / 4).toFixed(5) + ')');
  L.push('');
  L.push('stack(');

  const layers = [];
  // сдвиги грува идут отдельным паттерном на 16 шагов — позиции совпадают с нотами
  const drumBar = (b) => 's("' + mini(b.s) + '").gain("' + mini(b.g) + '").nudge("' + mini(b.n) + '")';
  const noteBar = (b) => 'note("' + mini(b.n) + '").gain("' + mini(b.g) + '").clip("' + mini(b.c) + '").nudge("' + mini(b.nu) + '")';

  if (sc.drums) {
    const d = sc.drums;
    const trim = (ctx.kitSel && ctx.kitSel.kit.trim) || 1;
    const dl = [];
    if (ctx.kickBars.some(Boolean)) dl.push('  ' + catOf(ctx.kickBars, drumBar) + '.postgain(' + gain(1.1 * d.gain * trim) + ').shape(' + f2(sc.drumShape || 0.16) + ')');
    if (ctx.snareBars.some(Boolean)) dl.push('  ' + catOf(ctx.snareBars, drumBar) + '.postgain(' + gain(0.8 * d.gain * trim) + ').room(' + room(0.28) + ').roomsize(2)');
    if (ctx.hatBars.some(Boolean)) dl.push('  ' + catOf(ctx.hatBars, drumBar) + '.postgain(' + gain(0.5 * d.gain * trim) + ').pan(sine.range(0.4,0.6).slow(7))');
    if (ctx.percBars.some(Boolean)) dl.push('  ' + catOf(ctx.percBars, drumBar) + '.postgain(' + gain(0.45 * d.gain * trim) + ').pan(perlin.range(0.25,0.75)).room(' + room(0.3) + ')');
    layers.push('  // ударные — ' + meta.kit + '\n  stack(\n  ' + dl.join(',\n  ') + '\n  ).lpf(' + Math.round(d.lpf * (0.6 + bright * 0.8)) + ').orbit(1)');
  }

  if (ctx.bassBars.some(Boolean)) {
    layers.push('  // бас — ' + meta.bassStyle + '\n  ' + catOf(ctx.bassBars, noteBar)
      + '.s("' + sc.bassSound + '").attack(0.012).release(0.14).lpf(' + Math.round(220 + bright * 260) + ')'
      + (sc.form === 'beat' ? '.shape(0.12)' : '')
      + '.postgain(' + gain(sc.bassGain) + ').orbit(2)');
  }

  if (ctx.keyBars.some(Boolean)) {
    layers.push('  // гармония — ' + sc.keySound + '\n  ' + catOf(ctx.keyBars, noteBar)
      + '.s("' + sc.keySound + '")'
      + '.lpf(perlin.range(' + Math.round(cutoff * 0.7) + ',' + Math.round(cutoff * 1.35) + ').slow(17))'
      + '.speed(sine.range(' + (1 - sc.wow).toFixed(4) + ',' + (1 + sc.wow).toFixed(4) + ').slow(9))'
      + crush
      + '.room(' + room(sc.keyRoom) + ').roomsize(' + f2(2 + space * 4) + ')'
      + '.pan(sine.range(0.42,0.58).slow(23))'
      + '.off(' + (sc.form === 'ambient' ? '1/6' : '1/8') + ', x => x.add(note(12)).mul(gain(0.22)))'
      + '.postgain(' + gain(sc.keyGain) + ').orbit(3)');
  }

  if (ctx.melBars.some(Boolean)) {
    layers.push('  // мелодия — ' + sc.melSound + '\n  ' + catOf(ctx.melBars, noteBar)
      + '.s("' + sc.melSound + '")'
      + '.lpf(' + Math.round(2200 + bright * 5000) + ')'
      + (sc.crush ? '.crush(' + (sc.crush + 1) + ')' : '')
      + (sc.form === 'ambient' ? '.echo(3, 1/3, 0.45)' : '')
      + '.delay(' + f2(0.22 + space * 0.3) + ').delaytime(' + (60 / bpm * 0.75).toFixed(3) + ').delayfeedback(' + f2(0.28 + space * 0.2) + ')'
      + '.room(' + room(0.55) + ').roomsize(' + f2(3 + space * 4) + ')'
      + '.pan(perlin.range(0.34,0.66).slow(13))'
      + '.postgain(' + gain(sc.melGain) + ').orbit(4)');
  }

  if (ctx.counterBars.some(Boolean)) {
    layers.push('  // второй голос — ' + sc.counterSound + '\n  ' + catOf(ctx.counterBars, noteBar)
      + '.s("' + sc.counterSound + '")'
      + '.lpf(' + Math.round(2000 + bright * 3500) + ')'
      + '.room(' + room(0.6) + ').roomsize(' + f2(3 + space * 3) + ')'
      + '.pan(' + (sc.form === 'beat' ? '0.68' : 'perlin.range(0.2,0.8).slow(17)') + ')'
      + '.delay(0.2).delaytime(' + (60 / bpm * 0.5).toFixed(3) + ').delayfeedback(0.3)'
      + '.postgain(' + gain(sc.counterGain || 0.3) + ').orbit(8)');
  }

  if (ctx.padBars.some(Boolean)) {
    layers.push('  // подкладка\n  ' + catOf(ctx.padBars, (n) => 'note("' + n + '")')
      + '.s("' + sc.padSound + '").attack(' + f2(0.9 + space) + ').release(' + f2(1.4 + space * 2) + ').clip(1.15)'
      + '.lpf(perlin.range(' + Math.round(260 + bright * 200) + ',' + Math.round(700 + bright * 900) + ').slow(29))'
      + '.lpq(1.4)'
      + (sc.drums ? '.duck(0.5).duckorbit(1).duckattack(0.02).duckdepth(0.55)' : '')
      + '.room(' + room(0.9) + ').roomsize(' + f2(5 + space * 5) + ')'
      + '.postgain(' + gain(sc.padGain * 0.5) + ').orbit(5)');
  }

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
    if (t === 'pulse') layers.push('  // пульс\n  s("RolandCompurhythm78_hh:0").struct("t ~ ~ ~ t ~ ~ ~").gain(0.24).lpf(3000).room(' + room(0.5) + ').postgain(' + gain(0.35) + ').orbit(7)');
  }

  L.push(layers.join(',\n'));
  L.push(')');
  L.push('.postgain(0.46).analyze(1)');
  return L.join('\n');
}
