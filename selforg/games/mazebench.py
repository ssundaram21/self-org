"""One MazeBench room, run by MazeBench's own engine in a node subprocess (mazebench_entry.js).

The player starts as if it had just walked in through one edge and wins by leaving through
another. Views are isometric-style ASCII projections; one `action_sequence` costs a turn per action.
"""

import json
import subprocess
from pathlib import Path

from selforg.config import ROOT

ENGINE = ROOT / "third_party" / "MazeBenchEngine"
_INSTRUCTIONS = (ROOT / "data" / "mazebench_player.md").read_text().strip()
_MOVES = ("up", "down", "left", "right")
_ROTATES = {f"rotate camera {d}": d for d in _MOVES}
_SEQUENCE = "action_sequence <action> <action> ..."
_ALIVE = [*_MOVES, *_ROTATES, "undo", "reset", _SEQUENCE]
_DEAD = ["undo", "reset", _SEQUENCE]
_ENTRY_SIDE = {"D": "top", "U": "bottom", "R": "left", "L": "right"}


class Game:
    def __init__(self, level_id: str, entry: str, max_steps: int):
        self.level_id, self.max_steps = level_id, max_steps
        self.done = self.won = False
        self.steps, self.turn_cost = 0, 1
        self._instructions = _INSTRUCTIONS.replace("{side}", _ENTRY_SIDE[entry.split(",")[2]])
        self._proc = subprocess.Popen(
            ["node", str(Path(__file__).with_name("mazebench_entry.js")), "--repo", str(ENGINE),
             "--entry", entry, "--level", level_id, "--view", "top-diagonal", "--yaw", "0"],
            cwd=ENGINE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True)
        self._state = self._rpc("observe")
        self._start = set(self._state["visited_levels"])

    def _rpc(self, command: str, **kw) -> dict:
        self._proc.stdin.write(json.dumps({"command": command, **kw}) + "\n")
        self._proc.stdin.flush()
        r = json.loads(self._proc.stdout.readline() or '{"error": "the maze engine exited"}')
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "maze engine command failed")
        return r

    def available_actions(self) -> list[str]:
        return _DEAD if self._state["player_dead"] else _ALIVE

    def initial_observation(self) -> str:
        return self._instructions + "\n\n" + self._view()

    def _accepts(self, action: str) -> bool:
        return action in self.available_actions() and action != _SEQUENCE

    def step(self, action: str) -> str:
        action = action.strip().lower()
        if action.startswith("action_sequence") and _SEQUENCE in self.available_actions():
            actions = _split(action[len("action_sequence"):])
        elif self._accepts(action):
            actions = [action]
        else:
            return (f"Your action {action!r} is not one of the available actions "
                    f"({', '.join(self.available_actions())}); nothing happened.\n\n{self._view()}")
        applied, note = 0, ""
        for a in actions:                    # a sequence stops at the first refused action
            if not self._accepts(a):
                note = f"Stopped before {a!r}: not an available action then.\n"
                break
            self._apply(a)
            applied += 1
            if self._state.get("blocked_entry"):
                note = "You cannot exit through the entrance.\n"
            if self.done:
                break
        self.turn_cost = max(applied, 1)
        if len(actions) > 1:
            note = f"Applied {applied} of {len(actions)} actions.\n" + note
        prefix = "You win!\n" if self.won else "The episode ended.\n" if self.done else ""
        return prefix + note + self._view()

    def _apply(self, action: str) -> None:
        if action in _MOVES:
            self._state = self._rpc("move", direction=action)
        elif action in _ROTATES:
            self._state = self._rpc("rotate_camera", direction=_ROTATES[action])
        else:
            self._state = self._rpc("undo" if action == "undo" else "reset_level")
        self.steps += 1
        self.won = self._state["current_room"] not in self._start
        self.done = self.won or self.steps >= self.max_steps

    def score(self) -> float:
        return float(self.won)

    def info(self) -> dict:
        return {"level_id": self.level_id, "won": self.won, "steps": self.steps}

    def _view(self) -> str:
        s = self._state
        lines = [f"Current view: {s['current_view']}", f"Yaw: {s['yaw']}",
                 f"Player dead: {str(s['player_dead']).lower()}"]
        if s.get("ascii_legend"):
            lines.append(f"Legend: {json.dumps(s['ascii_legend'])}")
        if s["player_dead"]:
            lines.append("The player died: only undo or reset are accepted.")
        return "\n".join(lines) + "\n\n" + s["level"]

    def close(self) -> None:
        self._proc.kill()
        self._proc.wait()


def _split(text: str) -> list[str]:
    """`up up rotate camera left undo` -> the actions, multi-word ones rejoined."""
    words, out, i = text.replace(",", " ").split(), [], 0
    while i < len(words):
        n = 3 if words[i] == "rotate" and i + 2 < len(words) else 1
        out.append(" ".join(words[i:i + n]))
        i += n
    return out
