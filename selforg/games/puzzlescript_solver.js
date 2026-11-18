// Breadth-first search for a win on one PuzzleScript level; prints one JSON line.
//
//   node puzzlescript_solver.js <script-doctor checkout> <game file> <level> <budget ms>

const fs = require('fs');
const path = require('path');

const [repo, file, level, budget] = process.argv.slice(2);
const engine = require(path.join(repo, 'puzzlescript_nodejs/puzzlescript/engine.js'));
const solver = require(path.join(repo, 'puzzlescript_nodejs/puzzlescript/solver.js'));
engine.compile(['loadLevel', parseInt(level)], fs.readFileSync(file, 'utf8'));
const res = solver.solveBFS(engine, 100000000, parseInt(budget));
console.log(JSON.stringify({ solved: !!res[0], iters: Number(res[2]), budget_hit: !!res[6] }));
