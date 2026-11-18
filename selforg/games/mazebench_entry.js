// maze-bridge.js with an entry start. The session begins in the neighbouring room with the player
// on the border cell facing --level, then takes the one step into it, so the play opens in the
// state the world benchmark produces on arrival. Every other argument and the stdin protocol are
// maze-bridge.js's.
//   node maze_bridge_entry.js --repo <MazeBenchEngine> --level level_IxI --entry 8,0,D [bridge args]
// --entry x,y,D: the player arrives on cell (x, y) of --level travelling D (U/D/L/R). The entry
// side is then sealed: pushing back out through it is blocked (the response carries
// blocked_entry: true), and the arrival cannot be undone.
const path = require("node:path");
const readline = require("node:readline");

const STEP = { U: [0, -1], D: [0, 1], L: [-1, 0], R: [1, 0] };
const DIRECTION = { U: "up", D: "down", L: "left", R: "right" };

function shift(levelId, dx, dy) {
  const [, x, y] = levelId.match(/^level_([A-Z])x([A-Z])$/);
  const code = (c, d) => String.fromCharCode(c.charCodeAt(0) + d);
  return `level_${code(x, dx)}x${code(y, dy)}`;
}

// Start a session in the room the entry comes from, put the player on the border cell across from
// (x, y), and step into levelId. Returns the session, or null if the game refuses the crossing.
function arrive(bridge, options, levelId, entry) {
  const [x, y, dir] = entry.split(",");
  const [dx, dy] = STEP[dir];
  const from = shift(levelId, -dx, -dy);
  const session = bridge.createSession({ ...options, levelId: from });
  const context = session.context;
  const playData = context.playData;
  const player = playData.actors.find((a) => a.type === "player")
    || playData.actors[playData.actors.push({ type: "player", label: "Player", removed: false }) - 1];
  player.x = dx === 0 ? Number(x) : dx > 0 ? playData.width - 1 : 0;
  player.y = dy === 0 ? Number(y) : dy > 0 ? playData.height - 1 : 0;
  player.elevation = 0;
  context.engine = session.mazeEngine.createEngine(playData);
  context.state = context.engine.cloneState(context.engine.initialState);
  bridge.handleCommand(session, { command: "move", direction: DIRECTION[dir] });
  if (context.level.id !== levelId) return null;
  session.actionCount = 0;
  context.history = [];
  return session;
}

// True when the move would push the player off the entry side.
function backsOut(session, entry, message) {
  const [, , dir] = entry.split(",");
  const [dx, dy] = STEP[dir];
  if (message.command !== "move" || message.direction !== DIRECTION[{ U: "D", D: "U", L: "R", R: "L" }[dir]]) return false;
  const { playData, state } = session.context;
  const i = playData.actors.findIndex((a) => a.type === "player");
  return dx !== 0 ? state.actorX[i] === (dx > 0 ? 0 : playData.width - 1)
                  : state.actorY[i] === (dy > 0 ? 0 : playData.height - 1);
}

function main() {
  const argv = process.argv.slice(2);
  const take = (flag) => { const i = argv.indexOf(flag); return argv.splice(i, 2)[1]; };
  const repo = path.resolve(take("--repo"));
  const entry = take("--entry");
  const bridge = require(path.join(repo, "scripts", "maze-bridge"));
  const options = bridge.parseArgs(argv);
  const session = arrive(bridge, options, options.levelId, entry);
  if (!session) throw new Error(`no entry into ${options.levelId} at ${entry}`);
  const write = (payload) => process.stdout.write(`${JSON.stringify(payload)}\n`);
  readline.createInterface({ input: process.stdin, terminal: false }).on("line", (line) => {
    try {
      const message = JSON.parse(line);
      const blocked = backsOut(session, entry, message);
      if (blocked) message.command = "observe";
      write({ ...bridge.handleCommand(session, message), blocked_entry: blocked });
      if (message.command === "close") process.exit(0);
    } catch (error) {
      write({ ok: false, error: error instanceof Error ? error.message : String(error) });
    }
  });
}

if (require.main === module) main();

module.exports = { arrive, backsOut, shift, STEP };
