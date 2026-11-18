"""What a run records:

    plays.jsonl                   one line per play: game, artifact version, score, stop reason
    plays/NNNN_<game>.json        the same play with its full transcript
    library_versions/vNNN/        every distinct state of player_folder, in the order first seen
"""

import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path

from selforg.config import PLAYER_FOLDER


class Ledger:
    def __init__(self, out: Path):
        self.dir = Path(out) / "plays"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index = (Path(out) / "plays.jsonl").open("w")
        self._lock = threading.Lock()
        self._n = 0

    def add(self, play: dict, **fields) -> dict:
        with self._lock:
            self._n += 1
            row = {"n": self._n, **fields, **{k: play[k] for k in ("score", "stop_reason", "crashed")}}
            self._index.write(json.dumps(row) + "\n")
            self._index.flush()
        (self.dir / f"{row['n']:04d}_{fields['game_id']}.json").write_text(
            json.dumps({**row, **play}, indent=1))
        return row


class Versions:
    """Content-addressed snapshots of a player_folder. Each vNNN holds a complete player_folder,
    so any snapshot can be handed to eval or to a play as is."""

    def __init__(self, out: Path):
        self.dir = Path(out) / "library_versions"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._tags: dict[str, str] = {}
        self._lock = threading.Lock()

    def capture(self, folder: Path) -> tuple[str, Path]:
        """Freeze `folder` now; return its version tag and the frozen copy. Copied before hashing,
        so a folder that changes mid-capture still yields one whole state."""
        staging = Path(tempfile.mkdtemp(dir=self.dir, prefix=".staging"))
        try:
            shutil.copytree(folder, staging / PLAYER_FOLDER)
        except OSError:
            shutil.rmtree(staging)
            raise
        h = hashlib.sha256()
        for p in sorted(staging.rglob("*")):
            h.update(str(p.relative_to(staging)).encode() + b"\0" + (p.read_bytes() if p.is_file() else b"/"))
        with self._lock:
            tag = self._tags.setdefault(h.hexdigest(), f"v{len(self._tags) + 1:03d}")
            if (self.dir / tag).exists():
                shutil.rmtree(staging)
            else:
                staging.rename(self.dir / tag)
        return tag, self.dir / tag / PLAYER_FOLDER
