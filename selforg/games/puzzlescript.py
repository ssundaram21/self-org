"""One level of a PuzzleScript game, run by the reference JavaScript engine in a node subprocess.

The player sees an ASCII grid with a legend naming each object. `score()` is 1 once the level is won.
"""

import json
import subprocess
from pathlib import Path

from selforg.config import ROOT

ENGINE = ROOT / "third_party" / "script-doctor"
_HERE = Path(__file__).parent
_ACTIONS = {"up": 0, "left": 1, "down": 2, "right": 3, "action": 4}
_EXTRA = ["undo", "restart"]
# One char per object; glyphs easy to confuse (0/O, 1/l/I) and the grid's own `|` `.` are left out.
_CHARS = "PCTWABDEFGHJKLMNQRSUVXYZabcdefghijkmnopqrstuvwxyz23456789+*=~^&%$@!?/<>"
_INSTRUCTIONS = """\
You are playing a grid puzzle game. Its rules are not given to you: work them out by acting and
watching what changes.

# Objective
Reach the game's win condition.

# Actions
{actions}

`action` is the game's generic action button; in some games it does nothing.

# Reading the grid
Cells are separated by `|`. Within a cell each character is one object, and `.` is an empty slot.
Every cell has the same number of slots, so the columns line up. The legend below names what each
character is.

{message}{legend}
{grid}"""


class Game:
    def __init__(self, source: str, level: int):
        self.level, self.done = level, False
        self._chars: dict[int, str] = {}
        self._depth = 1
        self._proc = subprocess.Popen(["node", "--stack-size=8000", str(_HERE / "puzzlescript_worker.js"),
                                       str(ENGINE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True)
        r = self._rpc("load", source=source, level=level)
        if r["errors"]:
            self.close()
            raise ValueError("game did not compile:\n" + "\n".join(r["errors"]))
        self._ids, self._grid, self._message = r["ids"], r["grid"], r["message"]
        if not self._grid or not self._grid[0]:
            self.close()
            raise ValueError(f"level {level} loaded an empty grid")
        if r["win"]:
            self.close()
            raise ValueError(f"level {level} is already won before any move")

    def _rpc(self, op: str, **kw) -> dict:
        self._proc.stdin.write(json.dumps({"op": op, **kw}) + "\n")
        self._proc.stdin.flush()
        r = json.loads(self._proc.stdout.readline() or '{"error": "the engine exited"}')
        if not r.get("ok"):
            raise RuntimeError(f"engine error: {r.get('error')}")
        return r

    def _char(self, obj: int) -> str:
        """An object's grid char, assigned on first sight: its name's initial if still free."""
        if obj not in self._chars:
            used = set(self._chars.values())
            initial = self._ids[obj][:1].upper()
            self._chars[obj] = (initial if initial.isalpha() and initial not in used
                                else next((c for c in _CHARS if c not in used), "#"))
        return self._chars[obj]

    def _render(self) -> str:
        """Cells padded with `.` to the deepest stack seen so far, so columns stay aligned."""
        self._depth = max(self._depth, *(len(c) for row in self._grid for c in row))
        return "\n".join("|".join("".join(self._char(o) for o in sorted(c)).ljust(self._depth, ".")
                                  for c in row) for row in self._grid)

    def _legend(self) -> str:
        rows = [f"  {ch} = {self._ids[i]}" for i, ch in sorted(self._chars.items(), key=lambda kv: kv[1])]
        return "Legend:\n" + "\n".join(rows) if rows else "Legend: (empty grid)"

    def _view(self) -> str:
        grid = self._render()                      # rendering assigns chars the legend lists
        message = f"{self._message}\n\n" if self._message else ""
        return f"{message}{self._legend()}\n{grid}"

    def initial_observation(self) -> str:
        grid = self._render()
        return _INSTRUCTIONS.format(actions=", ".join(f"`{a}`" for a in self.available_actions()),
                                    message=f"{self._message}\n\n" if self._message else "",
                                    legend=self._legend(), grid=grid)

    def available_actions(self) -> list[str]:
        return [*_ACTIONS, *_EXTRA]

    def step(self, action: str) -> str:
        action = action.strip().lower()
        if action in _ACTIONS:
            r = self._rpc("step", action=_ACTIONS[action])
        elif action in _EXTRA:
            r = self._rpc(action)
        else:
            return (f"Your action {action!r} is not one of the available actions "
                    f"({', '.join(self.available_actions())}); nothing happened.")
        self._grid, self._message = r["grid"], r["message"]
        self.done = r["win"]
        return ("You win!\n" if self.done else "") + self._view()

    def score(self) -> float:
        return float(self.done)

    def info(self) -> dict:
        return {"level": self.level, "won": self.done}

    def close(self) -> None:
        self._proc.kill()
        self._proc.wait()


def solvable(game_file: Path, level: int) -> tuple[bool | None, int]:
    """Whether a breadth-first search (60s) finds a win: False only if it exhausted every reachable
    state without one, None if it ran out of time. Also returns the states searched."""
    try:
        out = subprocess.run(["node", "--max-old-space-size=1024", "--stack-size=8000",
                              str(_HERE / "puzzlescript_solver.js"), str(ENGINE), str(game_file),
                              str(level), "60000"], capture_output=True, text=True, timeout=75).stdout
        r = json.loads(out.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, IndexError, ValueError):
        return None, 0
    return (True if r["solved"] else None if r["budget_hit"] else False), r["iters"]
