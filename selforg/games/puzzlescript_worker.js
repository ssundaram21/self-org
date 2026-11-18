// One PuzzleScript level, driven over JSON lines on stdin/stdout.
//
//   node puzzlescript_worker.js <script-doctor checkout>
//
// Requests: {"op":"load","source":...,"level":n} | {"op":"step","action":0-4} | {"op":"undo"}
//           | {"op":"restart"}
// Replies:  {"ok":true,"grid":[[[object index,...],...],...],"win":bool,"message":str[,"ids":[...]]}

'use strict';

const path = require('path');
const readline = require('readline');

// The engine logs to stdout, which is this protocol's channel: send every console stream to stderr
// before loading it, and write replies with process.stdout.write.
for (const level of ['log', 'info', 'warn', 'error', 'debug']) {
    console[level] = (...a) => process.stderr.write(a.map(String).join(' ') + '\n');
}
const engine = require(path.join(process.argv[2], 'puzzlescript_nodejs/puzzlescript/engine.js'));
// A message screen is modal and nothing here can dismiss it; its text still arrives via takeMessage().
engine.setSuppressMessageScreens(true);

let source = '', levelIndex = 0, ids = [], hidden = new Set(), history = [];

function load() {
    engine.compile(['loadLevel', levelIndex], source);
    const { count, strings } = engine.getErrors();
    if (count) return strings.map((s) => String(s).replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim());
    const state = engine.getState();
    ids = Array.from(state.idDict);
    hidden = new Set(ids.flatMap((name, i) => String(name).toLowerCase() === 'background' ? [i] : []));
    if (typeof state.backgroundid === 'number') hidden.add(state.backgroundid);
    history = [];
    return [];
}

function grid() {
    const level = engine.getLevel();
    const stride = Math.ceil(ids.length / 32);
    const rows = [];
    for (let y = 0; y < level.height; y++) {
        const row = [];
        for (let x = 0; x < level.width; x++) {
            const base = (x * level.height + y) * stride;          // cells are stored column-major
            row.push(ids.flatMap((_, i) => !hidden.has(i)
                && (level.objects[base + (i >> 5)] >> (i & 31)) & 1 ? [i] : []));
        }
        rows.push(row);
    }
    return rows;
}

function view() {
    return { ok: true, grid: grid(), win: engine.getWinning(), message: engine.takeMessage() };
}

readline.createInterface({ input: process.stdin }).on('line', (line) => {
    let res;
    try {
        const req = JSON.parse(line);
        if (req.op === 'load') {
            source = req.source;
            levelIndex = req.level;
            const errors = load();
            res = errors.length ? { ok: true, errors } : { ...view(), errors, ids };
        } else if (req.op === 'step') {
            history.push(engine.backupLevel());
            engine.processInput(req.action);
            for (let k = 0; engine.getAgaining() && k < 100; k++) engine.processInput(-1);
            res = view();
        } else if (req.op === 'undo') {
            if (history.length) engine.restoreLevel(history.pop());
            res = view();
        } else if (req.op === 'restart') {
            load();
            res = view();
        } else {
            res = { ok: false, error: `unknown op ${req.op}` };
        }
    } catch (e) {
        res = { ok: false, error: String((e && e.stack) || e).slice(0, 400) };
    }
    process.stdout.write(JSON.stringify(res) + '\n');
});
