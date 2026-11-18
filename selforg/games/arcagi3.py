"""Level 1 of an ARC-AGI-3 game, played live over the official API (needs ARC_API_KEY).

The opening screen is the full 64x64 grid as hex digits; later turns list only the changed cells.
`score()` is 1 once level 1 is cleared.
"""

import re
import time

import requests

from selforg.config import credential

_API = "https://three.arcprize.org"
_RESET, _CLICK = 0, 6
_NAMES = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "INTERACT", 6: "CLICK", 7: "UNDO"}
_HEX = "0123456789abcdef"
_INSTRUCTIONS = (
    "The opening screen below is the full game grid: each row is a dense string of hex digits, "
    "one per cell, where the digit 0-f is the cell's color (0-15). The two lines above the grid "
    "mark column numbers and the number at the start of each row is its row index (both 0-63). "
    "After this first screen, each turn tells you only which cells CHANGED since the previous "
    "screen (as `row R, col C: old->new`); every other cell stays exactly as it was, so track the "
    "grid yourself. To click a cell, reply `ACTION: CLICK at (x, y)` where x is the column and y "
    "is the row (both 0-63); for any other action just give its name, e.g. `ACTION: UP`."
)


class Game:
    def __init__(self, game_id: str):
        self.game_id, self.steps = game_id, 0
        self._s = requests.Session()
        self._s.headers.update({"X-API-Key": credential("ARC_API_KEY")[1], "Accept": "application/json"})
        self.card = self._post("/api/scorecard/open", {"tags": ["selforg", game_id], "source_url": "",
                                                       "opaque": {}})["card_id"]
        self._frame = self._post("/api/cmd/RESET", {"game_id": game_id, "guid": None, "card_id": self.card})
        self.guid = self._frame["guid"]
        self.done = self._over()

    def _post(self, path: str, payload: dict) -> dict:
        for attempt in range(2):                     # one retry on a 5xx or dropped connection
            try:
                r = self._s.post(_API + path, json=payload, timeout=60)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if attempt or (status is not None and status < 500):
                    raise
                time.sleep(2)

    def _over(self) -> bool:
        return self._frame["state"] == "GAME_OVER" or self._frame["levels_completed"] >= 1

    def _status(self) -> str:
        return ("GAME_OVER" if self._frame["state"] == "GAME_OVER"
                else "FINISHED" if self._frame["levels_completed"] >= 1 else "NOT_FINISHED")

    def _allowed(self) -> list[int]:
        if self._frame["state"] == "GAME_OVER":
            return [_RESET]
        return list(dict.fromkeys([*self._frame["available_actions"], _RESET]))

    def _render(self) -> str:
        grid = self._frame["frame"][-1]
        tens = "   " + "".join(str(c // 10) if c % 10 == 0 else " " for c in range(len(grid[0])))
        ones = "   " + "".join(str(c % 10) for c in range(len(grid[0])))
        rows = [f"{r:>2} " + "".join(_HEX[v] for v in row) for r, row in enumerate(grid)]
        return f"[status={self._status()}]\n" + "\n".join([tens, ones, *rows])

    def _delta(self, prev: list[list[int]]) -> str:
        cur = self._frame["frame"][-1]
        changes = [f"row {r}, col {c}: {_HEX[prev[r][c]]}->{_HEX[cur[r][c]]}"
                   for r in range(len(cur)) for c in range(len(cur[r])) if prev[r][c] != cur[r][c]]
        head = f"[status={self._status()}]"
        if not changes:
            return head + "\nScreen unchanged."
        return "\n".join([f"{head} {len(changes)} cell(s) changed since last screen "
                          f"(all others unchanged):", *changes])

    def available_actions(self) -> list[str]:
        return ["RESET" if i == _RESET else f"{_NAMES[i]} at (x, y)" if i == _CLICK else _NAMES[i]
                for i in self._allowed()]

    def initial_observation(self) -> str:
        return _INSTRUCTIONS + "\n\n" + self._render()

    def step(self, action: str) -> str:
        token = action.strip().upper()
        name = "CLICK" if token.startswith("CLICK") else re.split(r"[\s.,;:]", token, 1)[0]
        xy = re.search(r"\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", action) if name == "CLICK" else None
        aid = _RESET if name == "RESET" else next((i for i, n in _NAMES.items() if n == name), None)
        if aid not in self._allowed() or (aid == _CLICK and not (xy and all(0 <= int(v) <= 63 for v in xy.groups()))):
            return (f"Your action {action!r} is not one of the available actions "
                    f"({', '.join(self.available_actions())}); nothing happened.")
        prev = self._frame["frame"][-1]
        payload = {"game_id": self.game_id, "guid": self.guid, "card_id": self.card}
        if aid == _RESET:
            self._frame = self._post("/api/cmd/RESET", payload)
        else:
            if aid == _CLICK:
                payload["x"], payload["y"] = int(xy.group(1)), int(xy.group(2))
            self._frame = self._post(f"/api/cmd/ACTION{aid}", {**payload, "reasoning": {}})
        self.steps += 1
        self.done = self._over()
        return self._render() if aid == _RESET else self._delta(prev)

    def score(self) -> float:
        return float(self._frame["levels_completed"] >= 1)

    def info(self) -> dict:
        return {"state": self._frame["state"], "steps": self.steps,
                "levels_completed": self._frame["levels_completed"]}

    def close(self) -> None:
        self._post("/api/scorecard/close", {"card_id": self.card})
