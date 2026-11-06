(() => {
  const root = document.getElementById('tl');
  let timer = null, anim = null, T = 0, model = 0;

  function mount(D) {
  clearInterval(timer);
  cancelAnimationFrame(anim);
  T = Math.round(T);
  const WIN = '#00A878', LOSS = '#BB4430', EDIT = '#009DE0';
  const NS = 'http://www.w3.org/2000/svg';
  const MIN_U = 5;   // smallest on-screen width of one play slot; narrower screens scroll
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const ver = v => v && v !== '-' ? 'v' + parseInt(v.slice(1)) : '';
  const color = it => it.score === 1 ? WIN : LOSS;
  const fname = f => f.split('/').pop();
  let sel = -1;

  // Events launched with nothing in between form one segment.
  const groups = [];
  D.items.forEach(it => {
    if (!it.ctx.length && groups.length) groups[groups.length - 1].items.push(it);
    else groups.push({ctx: it.ctx, items: [it]});
  });

  root.innerHTML = `
    <div class="tl-top">
      <div class="tl-title"><div class="tl-heading">Timeline</div>
        <div class="tl-hint">Click anywhere on the timeline to see what the teacher was doing. Use ← → to step through.</div>
        <div class="tl-models">${window.TIMELINES.map((m, i) => `<button class="${i === model ? 'on' : ''}" data-i="${i}" style="--c:${m.color}"><i style="background:${m.color}"></i>${esc(m.name)}</button>`).join('')}</div>
        <button class="tl-expand">${T ? 'Collapse games' : 'Expand by game'}</button></div>
      <div class="tl-legend">
        <div class="g"><span>Condition</span><div class="row">
          <span><i style="background:#6b7280;border-radius:50%"></i>Default</span>
          <span><i style="background:#6b7280"></i>Learned</span></div></div>
        <div class="g"><span>Result</span><div class="row">
          <span><i style="background:${WIN}"></i>Win</span><span><i style="background:${LOSS}"></i>Loss</span></div></div>
        <div class="g"><span>&nbsp;</span><div class="row">
          <span><i style="background:${EDIT};width:2px;height:12px;vertical-align:-2px"></i>Update</span></div></div>
      </div>
    </div>
    <div class="tl-line"><svg class="tl-svg"></svg></div>
    <div class="tl-panel"></div>`;

  // Timeline, in the notebook's data units (y flipped). Collapsed it is one row; expanded, every exact game
  // (name + file) gets its own row, in order of first play, as in self_play_effort_simple.ipynb.
  const svg = root.querySelector('svg'), line = root.querySelector('.tl-line');
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return parent.appendChild(e);
  };
  const bounds = groups.slice(1).map((g, k) => (groups[k].items[groups[k].items.length - 1].x + g.items[0].x) / 2);
  const rows = [], rowOf = new Map();
  for (const it of D.items) {
    if (it.type !== 'play') continue;
    const key = it.game + ':' + D.replays[it.replay].game;
    if (!rowOf.has(key)) { rowOf.set(key, rows.length); rows.push({name: it.game, wins: 0, n: 0}); }
    it.row = rowOf.get(key);
    rows[it.row].n++;
    rows[it.row].wins += it.score === 1;
  }
  rows.forEach(r => {
    const same = rows.filter(q => q.name === r.name);
    r.label = same.length > 1 ? `${r.name} (v${same.indexOf(r) + 1})` : r.name;
  });
  const PAD = 1.2;
  let RH = 1, GUTTER = 0, DROP = 0;
  let U = 1, E = T, parts = null;

  function draw() {
    const W = D.width;
    U = Math.max(MIN_U, line.clientWidth / (W + 1.2 + PAD));
    RH = Math.max(1.6, 18 / U); GUTTER = 175 / U; DROP = (rows.length - 1) * RH;
    const fs = 13 / U, top = -1.5 - 15 / U;
    svg.innerHTML = '';
    const bands = rows.map((r, k) => el('rect', {x: -0.6, width: W + 1.2, fill: k % 2 ? 'none' : '#f1f2f4'}, svg));
    const hits = groups.map((g, k) => {
      const l = k ? bounds[k - 1] : -0.6, r = k < bounds.length ? bounds[k] : W + 0.6;
      const h = el('rect', {class: 'tl-hit' + (k === sel ? ' sel' : ''), 'data-k': k, x: l, y: top, width: r - l}, svg);
      h.addEventListener('click', () => { select(k); root.focus({preventScroll: true}); });
      return h;
    });
    const m = el('g', {'pointer-events': 'none'}, svg);
    const labels = el('g', {}, m);
    el('text', {x: -62 / U, y: top + 11 / U, 'font-size': 12 / U, 'text-anchor': 'end', fill: '#444'}, labels).textContent = 'Game';
    el('text', {x: -10 / U, y: top + 11 / U, 'font-size': 12 / U, 'text-anchor': 'end', fill: '#444'}, labels).textContent = 'Win rate';
    const rowText = rows.map(r => {
      const g = el('g', {}, labels);
      el('text', {x: -62 / U, y: 12 / U * 0.35, 'font-size': 12 / U, 'text-anchor': 'end'}, g).textContent = r.label;
      el('text', {x: -10 / U, y: 12 / U * 0.35, 'font-size': 12 / U, 'text-anchor': 'end', fill: '#666'}, g).textContent = Math.round(100 * r.wins / r.n) + '%';
      return g;
    });
    const edits = [], marks = [];
    let run = [];
    D.items.forEach((it, i) => {
      if (it.type === 'edit') {
        edits.push(el('line', {x1: it.x, x2: it.x, y1: -1.5, stroke: EDIT, 'stroke-width': 0.25, opacity: 0.85}, m));
        run.push(it);
        if (D.items[i + 1]?.type !== 'edit') {
          const a = ver(run[0].version), b = ver(run[run.length - 1].version), end = run[run.length - 1].x > W - 3;
          el('text', {x: end ? run[run.length - 1].x + 0.15 : (run[0].x + run[run.length - 1].x) / 2, y: -1.5 - 3 / U,
                      'font-size': 11 / U, 'text-anchor': end ? 'end' : 'middle', fill: EDIT}, m).textContent = a === b ? a : `${a}–${b.slice(1)}`;
          run = [];
        }
        return;
      }
      const mk = it.learned ? el('rect', {x: it.x - 0.4485, y: -0.4485, width: 0.897, height: 0.897, fill: color(it)}, m)
                            : el('circle', {cx: it.x, cy: 0, r: 0.4485, fill: color(it)}, m);
      marks.push([mk, it.row]);
    });
    const axis = el('g', {}, m);
    el('line', {x1: -0.6, x2: W + 0.6, y1: 0.95, y2: 0.95, stroke: '#ccc', 'stroke-width': 1 / U}, axis);
    for (const [x, n] of D.ticks.filter(([, n]) => U >= 8 || n % 10 === 0)) {
      el('line', {x1: x, x2: x, y1: 0.95, y2: 0.95 + 4 / U, stroke: '#000', 'stroke-width': 1 / U}, axis);
      el('text', {x, y: 1.6 + fs * 0.85, 'font-size': fs, 'text-anchor': 'middle'}, axis).textContent = n;
    }
    el('text', {x: W / 2, y: 1.6 + fs * 2.3, 'font-size': fs, 'text-anchor': 'middle', fill: '#444'}, axis).textContent = 'Gameplay';
    parts = {W, top, bottom: 1.6 + fs * 2.6, bands, hits, labels, rowText, edits, marks, axis};
    layout();
  }

  function layout() {
    const {W, top, bottom, bands, hits, labels, rowText, edits, marks, axis} = parts, e = E;
    const L = GUTTER * e, drop = DROP * e, h = 1 + (RH - 1) * e;
    const u = Math.max(MIN_U, line.clientWidth / (W + 1.2 + PAD + L));
    svg.setAttribute('viewBox', `${-0.6 - L} ${top} ${W + 1.2 + PAD + L} ${bottom - top + drop}`);
    svg.style.width = (W + 1.2 + PAD + L) * u + 'px';
    svg.style.height = (bottom - top + drop) * u + 'px';
    bands.forEach((b, k) => { b.setAttribute('y', k * RH * e - h / 2); b.setAttribute('height', h); });
    hits.forEach(r => r.setAttribute('height', 0.95 - top + drop));
    edits.forEach(l => l.setAttribute('y2', 0.9 + drop));
    marks.forEach(([mk, r]) => mk.setAttribute('transform', `translate(0 ${r * RH * e})`));
    rowText.forEach((g, k) => g.setAttribute('transform', `translate(0 ${k * RH * e})`));
    labels.setAttribute('opacity', e * e);
    axis.setAttribute('transform', `translate(0 ${drop})`);
    U = u;
  }

  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  function expand(on) {
    const from = T, to = on ? 1 : 0, t0 = performance.now(), dur = 700 * Math.abs(to - from);
    cancelAnimationFrame(anim);
    root.querySelector('.tl-expand').textContent = on ? 'Collapse games' : 'Expand by game';
    line.classList.toggle('open', on);
    const step = now => {
      T = dur ? from + (to - from) * Math.min(1, (now - t0) / dur) : to;
      E = ease(T);
      layout();
      if (T !== to) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  }

  // Board rendering, from the game's own sprites. Games that define none (only a color per object) get a stand-in
  // sprite per object, chosen from its name and drawn in its own color.
  const LOOKS = [
    [/player|pilot|walker|hero|avatar/, ['.000.', '.101.', '00000', '.000.', '.0.0.']],
    [/wall|grate|mesh/, ['00010', '00010', '11111', '01000', '01000']],
    [/crate|box|block|boulder|rock|large|small/, ['11111', '10001', '10101', '10001', '11111']],
    [/target|goal|switch|plate|spot|plinth|socket/, ['.000.', '0...0', '0...0', '0...0', '.000.']],
    [/exit|door|stair|portal|flag/, ['.000.', '01110', '01110', '01110', '01110']],
    [/key/, ['.00..', '0..0.', '.00..', '..0..', '..00.']],
    [/gem|coin|crystal|idol|star|ammo|charge|orb|dot/, ['..0..', '.010.', '01110', '.010.', '..0..']],
    [/monster|enemy|guard|ghost|wisp|drone/, ['.000.', '01010', '00000', '00000', '0.0.0']],
    [/lamp|light/, ['.000.', '01110', '01110', '.000.', '..1..']],
    [/mirror/, ['0....', '.0...', '..0..', '...0.', '....0']],
    [/water|lava|ice/, ['00000', '01100', '10011', '00000', '01100']],
    [/background|floor|ground/, ['00000', '00000', '00000', '00000', '00010']],
  ];
  function shade(c) {
    const m = /^#?([0-9a-f]{6}|[0-9a-f]{3})$/i.exec(c);
    if (!m) return c;
    const h = m[1].length === 3 ? [...m[1]].map(x => x + x).join('') : m[1];
    const v = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)), lum = (v[0] * 299 + v[1] * 587 + v[2] * 114) / 1000;
    const out = v.map(x => Math.round(lum < 60 ? x + (255 - x) * 0.25 : x * 0.65));
    return '#' + out.map(x => x.toString(16).padStart(2, '0')).join('');
  }
  function look(game, obj) {
    if (!game.synth || !obj.colors[0] || obj.colors[0] === 'transparent') return obj;
    return obj.look ||= {name: obj.name, colors: [obj.colors[0], shade(obj.colors[0])],
                         sprite: (LOOKS.find(([re]) => re.test(obj.name.toLowerCase())) || [0, ['.000.', '00000', '00100', '00000', '.000.']])[1]};
  }
  function tile(ctx, obj, x, y, s) {
    const sp = obj.sprite || [];
    if (!sp.length) { if (obj.colors[0]) { ctx.fillStyle = obj.colors[0]; ctx.fillRect(x, y, s, s); } return; }
    const n = sp.length, m = sp[0].length, px = s / m, py = s / n;
    for (let r = 0; r < n; r++) for (let c = 0; c < m; c++) {
      const col = sp[r][c] === '.' ? null : obj.colors[+sp[r][c]];
      if (col) { ctx.fillStyle = col; ctx.fillRect(x + c * px, y + r * py, Math.ceil(px), Math.ceil(py)); }
    }
  }
  function board(canvas, rp, f, maxPx) {
    const game = D.games[rp.game], legend = rp.legends[f.l];
    game.synth ??= !Object.values(game.objects).some(o => o.sprite.length);
    const grid = f.g.map(row => row.split('|').map(c => c === '.' ? [] : [...c]));
    const rows = grid.length, cols = grid[0].length, cell = Math.max(2, Math.floor(maxPx / Math.max(rows, cols)));
    const dpr = window.devicePixelRatio || 1;
    canvas.width = cols * cell * dpr; canvas.height = rows * cell * dpr;
    canvas.style.width = cols * cell + 'px'; canvas.style.height = rows * cell + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, cols * cell, rows * cell);
    const bg = game.objects[game.background], obj = ch => game.objects[String(legend[ch] || ch).toLowerCase()];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      if (bg) tile(ctx, look(game, bg), c * cell, r * cell, cell);
      grid[r][c].map(obj).filter(Boolean)
        .sort((a, b) => game.layers.indexOf(a.name.toLowerCase()) - game.layers.indexOf(b.name.toLowerCase()))
        .forEach(o => tile(ctx, look(game, o), c * cell, r * cell, cell));
    }
  }

  // Detail panel.
  const panel = root.querySelector('.tl-panel');
  const short = p => p.replace(/^\/workspace\//, '');

  function stepHTML(s) {
    if (s.k === 'think') return `<div class="tl-think"><div>${esc(s.text).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</div></div>`;
    const tag = {bash: 'BASH', read: 'READ', write: 'WRITE', fail: 'PLAY'}[s.k];
    const head = s.k === 'fail' ? `${s.text} — failed to run` : short(s.text.replace(/\s+/g, ' '));
    const thumb = s.game && D.first_replay[s.game] !== undefined ? `<canvas data-r="${D.first_replay[s.game]}"></canvas>` : '';
    return `<div class="tl-tool"><div><span class="tl-tag ${s.k === 'read' || s.k === 'fail' ? 'gray' : ''}">${tag}</span>${thumb}<code>${esc(head)}</code></div>
      <pre>${s.k === 'fail' ? '' : esc(s.text)}${s.out ? `<span class="o">${s.k === 'fail' ? '' : '\n\n→ '}${esc(s.out)}</span>` : ''}</pre></div>`;
  }

  function actionHTML(it, j) {
    if (it.type === 'play') return `<div class="tl-act" data-j="${j}"><span class="tl-tag">PLAY</span><canvas data-r="${it.replay}"></canvas>
      <span class="g">${it.game}</span><span class="chip score ${it.score === 1 ? '' : 'loss'}">score ${Number(it.score).toFixed(1)}</span>
      <span class="num">#${it.n}</span><span class="chip ${it.learned ? 'ver' : ''}">${it.learned ? ver(it.version) : 'baseline'}</span></div>`;
    return `<div class="tl-act" data-j="${j}"><span class="tl-tag edit">UPDATE</span>
      ${it.diff.map(f => `<span class="g">${esc(fname(f.file))}</span><span class="chip"><span class="a">+${f.added}</span> <span class="r">−${f.removed}</span></span>`).join('')}
      <span class="chip ver">→ ${ver(it.version)}</span></div>`;
  }

  function playHTML(it) {
    const rp = D.replays[it.replay];
    return `<div class="tl-label">Gameplay ${it.n}</div><div class="tl-rp">
      <div class="tl-who">${it.learned ? `Player with learned artifacts <span class="chip ver">${ver(it.version)}</span>` : 'Player with default prompt'}</div>
      <div class="tl-board" style="border-color:${color(it)}"><canvas></canvas></div>
      <div class="tl-score" style="color:${color(it)}">score = ${Number(it.score).toFixed(1)}</div>
      <div class="tl-ctrl"><button>▶</button><input type="range" min="0" max="${rp.frames.length - 1}" value="0"><span class="n"></span></div>
      <div class="tl-say"></div></div>`;
  }

  function editHTML(it) {
    const files = it.diff.map(f => `<div class="tl-file">${esc(fname(f.file))} <span class="a">+${f.added}</span> <span class="r">−${f.removed}</span></div>
      <div class="tl-diff">${f.diff.split('\n').map(l => {
        const c = l.startsWith('@@') ? 'h' : l[0] === '+' ? 'p' : l[0] === '-' ? 'm' : 'c';
        return `<div class="${c}">${c === 'h' ? '⋯' : esc(l) || ' '}</div>`;
      }).join('')}</div>`).join('');
    return `<div class="tl-label">Artifact update → ${ver(it.version)}</div>${files || '<div class="tl-empty">No file changes.</div>'}`;
  }

  function title(g) {
    const plays = g.items.filter(it => it.type === 'play'), edits = g.items.length - plays.length;
    const parts = [];
    if (plays.length) parts.push(plays.length > 1 ? `Gameplays ${plays[0].n}–${plays[plays.length - 1].n}` : `Gameplay ${plays[0].n}`);
    if (edits) parts.push(edits > 1 ? `${edits} updates` : 'Update');
    return parts.join(' + ');
  }

  function show(g, j) {
    clearInterval(timer);
    const it = g.items[j], side = panel.querySelector('.tl-side');
    panel.querySelectorAll('.tl-act').forEach(a => a.classList.toggle('on', +a.dataset.j === j));
    side.innerHTML = it.type === 'play' ? playHTML(it) : editHTML(it);
    if (it.type === 'play') replay(D.replays[it.replay]);
  }

  function select(k) {
    if (k < 0 || k >= groups.length || k === sel) return;
    sel = k;
    svg.querySelectorAll('.tl-hit').forEach(h => h.classList.toggle('sel', +h.dataset.k === k));
    const h = svg.querySelector('.tl-hit.sel');
    const l = (+h.getAttribute('x') + 0.6 + GUTTER * E) * U, r = l + +h.getAttribute('width') * U;
    if (l < line.scrollLeft || r > line.scrollLeft + line.clientWidth) line.scrollLeft = l - line.clientWidth / 3;
    const g = groups[k];
    panel.innerHTML = `
      <div class="tl-head"><button class="tl-nav" ${k ? '' : 'disabled'}>‹</button><div class="t">${title(g)}</div>
        <button class="tl-nav" ${k < groups.length - 1 ? '' : 'disabled'}>›</button></div>
      <div class="tl-body">
        <div><div class="tl-label">Teacher</div><div class="tl-ctx">${g.ctx.map(stepHTML).join('')}${g.items.map(actionHTML).join('')}</div></div>
        <div class="tl-side"></div>
      </div>`;
    const [prev, next] = panel.querySelectorAll('.tl-nav');
    prev.onclick = () => select(sel - 1);
    next.onclick = () => select(sel + 1);
    panel.querySelectorAll('.tl-think').forEach(t => {
      if (t.firstChild.scrollHeight > t.firstChild.clientHeight + 2) { t.classList.add('more'); t.onclick = () => t.classList.toggle('open'); }
    });
    panel.querySelectorAll('.tl-tool > div').forEach(h => h.onclick = () => h.parentNode.classList.toggle('open'));
    panel.querySelectorAll('.tl-ctx canvas').forEach(c => { const rp = D.replays[+c.dataset.r]; board(c, rp, rp.frames[0], 30); });
    panel.querySelectorAll('.tl-act').forEach(a => a.onclick = () => show(g, +a.dataset.j));
    show(g, 0);
  }

  function replay(rp) {
    const canvas = panel.querySelector('.tl-board canvas'), range = panel.querySelector('.tl-ctrl input');
    const btn = panel.querySelector('.tl-ctrl button'), n = panel.querySelector('.tl-ctrl .n'), say = panel.querySelector('.tl-say');
    const last = rp.frames.length - 1;
    const frame = k => {
      const f = rp.frames[k];
      range.value = k;
      board(canvas, rp, f, Math.min(260, panel.querySelector('.tl-rp').clientWidth - 18));
      n.textContent = k ? `move ${k}/${last} · ${f.a}` : `start · ${last} moves`;
      say.innerHTML = k && f.r ? `<b>Player:</b> ${esc(f.r)}${f.m ? `<br><i>${esc(f.m)}</i>` : ''}` : '';
    };
    const stop = () => { clearInterval(timer); timer = null; btn.textContent = '▶'; };
    const play = () => {
      if (+range.value >= last) frame(0);
      btn.textContent = '❚❚';
      timer = setInterval(() => { +range.value >= last ? stop() : frame(+range.value + 1); }, 650);
    };
    btn.onclick = () => timer ? stop() : play();
    range.oninput = () => { stop(); frame(+range.value); };
    frame(0);
    play();
  }

  root.onkeydown = e => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { select(sel - 1); e.preventDefault(); }
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { select(sel + 1); e.preventDefault(); }
  };
  root.querySelector('.tl-expand').onclick = () => expand(T < 0.5);
  root.querySelectorAll('.tl-models button').forEach(b => b.onclick = () => { model = +b.dataset.i; mount(window.TIMELINES[model]); });
  line.classList.toggle('open', T === 1);
  window.onresize = draw;
  draw();
  select(groups.findIndex(g => g.items.includes(D.items[D.start ?? 0])));
  }

  mount(window.TIMELINES[0]);
})();
