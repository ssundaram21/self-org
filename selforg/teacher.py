"""Training: one teacher session optimizes the player's context.

The teacher works in a sandbox holding player_folder/ (seeded with the default player prompt) and,
with the Gameplay tool, the PuzzleScript reference or the Python game interface. One update is one
tool call that leaves player_folder/ in a new state; every state is kept as library_versions/vNNN,
v001 being the seed. The run ends on the update that reaches `updates`, or when the teacher stops
with the gameplay budget spent; stopping earlier gets it sent back to work.

Writes to `out`: config.json, player_folder/ (the final state), library_versions/, plays.jsonl and
plays/ (every game the teacher played), actions.log (a timeline) and logs/ (every session's events).
"""

import json
import shutil
import threading
import time
from dataclasses import asdict
from pathlib import Path

from selforg import harness, prompts
from selforg.config import PLAYER_FOLDER, PLAYER_PROMPT, ROOT, Train, is_pi
from selforg.gameplay import Gameplay
from selforg.records import Ledger, Versions

TOOLS = {"read_write": ["Read", "Write", "Edit", "Glob", "Grep"],
         "bash": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
         "gameplay": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "play_own_game"]}
_GAME_FILES = {"puzzlescript": "puzzlescript_docs", "python": "game_interface.md"}


class UpdatesSpent(Exception):
    pass


def train(cfg: Train) -> None:
    out = Path(cfg.out).resolve()
    if out.exists():
        raise SystemExit(f"{out} already exists: remove it, or choose another out=")
    sandbox = out / "sandbox"
    (sandbox / PLAYER_FOLDER).mkdir(parents=True)
    (sandbox / PLAYER_FOLDER / PLAYER_PROMPT).write_text(prompts.PLAYER)
    (out / "config.json").write_text(json.dumps(asdict(cfg), indent=2))

    started, timeline_lock = time.time(), threading.Lock()
    timeline_file = (out / "actions.log").open("a")

    def timeline(actor: str, text: str) -> None:
        with timeline_lock:
            timeline_file.write(f"[{time.time() - started:8.1f}s] {actor}: {text}\n")
            timeline_file.flush()

    versions = Versions(out)
    current = versions.capture(sandbox / PLAYER_FOLDER)[0]
    updates = 0

    def on_event(kind: str, data: dict) -> None:
        nonlocal current, updates
        if kind == "tool_use":
            timeline("teacher", f"{data['name']}: {json.dumps(data['input'])[:300]}")
            return
        try:
            tag = versions.capture(sandbox / PLAYER_FOLDER)[0]
        except OSError:                     # caught mid-write; the next tool result captures it
            return
        if tag != current:
            current, updates = tag, updates + 1
            timeline("versions", f"artifacts now {tag}")
            if updates >= cfg.updates:
                raise UpdatesSpent

    binds, gameplay = (), None
    if cfg.tools == "gameplay":
        reference = ROOT / "data" / _GAME_FILES[cfg.games]
        if reference.is_dir():
            shutil.copytree(reference, sandbox / reference.name)
        else:
            shutil.copy(reference, sandbox)
        gameplay = Gameplay(cfg, sandbox, out, versions, Ledger(out), timeline,
                            revisions_left=lambda: cfg.updates - updates)
        bridge = out / "bridge"
        bridge.mkdir()
        tool = prompts.gameplay_tool(cfg, gameplay.turn_pool, gameplay.token_pool)
        (bridge / "tools.json").write_text(json.dumps([tool]))
        (bridge / "mcp.json").write_text(json.dumps({"mcpServers": {"play": {
            "type": "stdio", "command": "python3", "args": ["/opt/play/mcp_play.py"],
            "alwaysLoad": True, "timeout": 3_600_000}}}))
        for f in ("mcp_play.py", "pi_play.ts"):
            shutil.copy(Path(__file__).with_name(f), bridge / f)
        (bridge / "play.json").write_text(json.dumps(gameplay.serve()))
        binds = (f"{bridge}:/opt/play:ro",)

    tools = TOOLS[cfg.tools]
    if not is_pi(cfg.model):
        tools = [f"mcp__play__{t}" if t == "play_own_game" else t for t in tools]
    session = harness.session(cfg.model, workdir=sandbox, tools=tools,
                              system_prompt=prompts.teacher_system(cfg), log=out / "logs" / "teacher.jsonl",
                              teacher=True, binds=binds, on_event=on_event)
    try:
        message = prompts.BEGIN
        while True:
            session.turn(message)
            if gameplay and gameplay.spent:
                break
            message = prompts.keep_working(cfg.updates - updates)
    except UpdatesSpent:
        pass
    finally:
        session.close()
        timeline_file.close()
    shutil.copytree(versions.dir / current / PLAYER_FOLDER, out / PLAYER_FOLDER)
    print(f"done: {updates} updates, {gameplay.plays if gameplay else 0} plays; artifacts in "
          f"{out / PLAYER_FOLDER}")
