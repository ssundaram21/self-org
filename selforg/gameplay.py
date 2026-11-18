"""The Gameplay tool, host side: plays the games the teacher writes.

The teacher's container reaches this over a unix socket in its sandbox (a loopback port on Docker
Desktop), through mcp_play.py (Claude Code) or pi_play.ts (Pi). Each request names a game file, an
optional player_folder and a result file. The game is validated (a PuzzleScript level must compile
and must not be provably unwinnable), its artifacts are frozen as a version, and a fresh player
plays it. The full transcript goes to the result file; the tool call returns the score and the
budgets.

Budgets (`Train.budget`):
    fixed   `plays` games, each with `horizon` turns and `tokens` output tokens
    token   the teacher sets each game's turns, drawn from a pool of plays * horizon
    free    the teacher sets each game's turns and tokens, from pools of plays * horizon turns and
            plays * tokens; a game may take at most MAX_GAME_TOKENS x `tokens`
A game is charged the turns and tokens it asked for, whether or not it used them.
"""

import hashlib
import json
import os
import re
import socket
import tempfile
import threading
from pathlib import Path, PurePosixPath

from selforg import player
from selforg.config import (CONCURRENT_PLAYS, DOCKER_DESKTOP, HOST_FROM_CONTAINER, PLAYER_FOLDER,
                            WORKDIR, Train)
from selforg.games import puzzlescript, python_game


class Reject(Exception):
    """A request the teacher can fix. Answered as an error, and nothing is charged."""


class Gameplay:
    def __init__(self, cfg: Train, sandbox: Path, out: Path, versions, ledger, timeline,
                 revisions_left):
        self.cfg, self.sandbox, self.out = cfg, sandbox, out
        self.versions, self.ledger, self.timeline = versions, ledger, timeline
        self.revisions_left = revisions_left
        self.max_plays = cfg.plays if cfg.budget == "fixed" else 0
        self.turn_pool = 0 if cfg.budget == "fixed" else cfg.plays * cfg.horizon
        self.token_pool = cfg.plays * cfg.tokens if cfg.budget == "free" else 0
        self.plays = self.turns_used = self.tokens_used = 0
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(CONCURRENT_PLAYS)
        self._verdicts: dict[tuple[str, int], tuple[bool | None, int]] = {}

    @property
    def spent(self) -> bool:
        if self.max_plays:
            return self.plays >= self.max_plays
        return (self.turns_used >= self.turn_pool
                or bool(self.token_pool) and self.tokens_used >= self.token_pool)

    def serve(self) -> dict:
        """Starts the play server; returns its address as the container reaches it: a unix socket
        in the sandbox, or, on Docker Desktop, which cannot reach host sockets, a loopback port."""
        if DOCKER_DESKTOP:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            address = {"host": HOST_FROM_CONTAINER, "port": sock.getsockname()[1]}
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            cwd = os.getcwd()
            os.chdir(self.sandbox)          # bind a short relative path: sun_path is ~108 chars
            try:
                sock.bind(".play.sock")
            finally:
                os.chdir(cwd)
            address = {"path": f"{WORKDIR}/.play.sock"}
        sock.listen(socket.SOMAXCONN)
        threading.Thread(target=self._accept, args=(sock,), daemon=True).start()
        return address

    def _accept(self, sock: socket.socket) -> None:
        while True:
            conn, _ = sock.accept()
            threading.Thread(target=self._answer, args=(conn,), daemon=True).start()

    def _answer(self, conn: socket.socket) -> None:
        with conn:
            buf = b""
            while not buf.endswith(b"\n") and (chunk := conn.recv(65536)):
                buf += chunk
            try:
                reply = self.play(json.loads(buf))
            except Reject as e:
                reply = {"error": str(e)}
            except Exception as e:
                reply = {"error": f"play server error: {e!r}"}
            conn.sendall((json.dumps(reply) + "\n").encode())

    def _path(self, arg, outside_player: bool = True) -> Path:
        """A path as the teacher sees it (relative to, or under, WORKDIR) -> the host path."""
        p = PurePosixPath(WORKDIR, str(arg or ""))
        p = (self.sandbox / p.relative_to(WORKDIR)).resolve() if p.is_relative_to(WORKDIR) else None
        if p is None or (p != self.sandbox and self.sandbox not in p.parents):
            raise Reject(f"path {arg!r} must be inside the sandbox")
        player_folder = self.sandbox / PLAYER_FOLDER
        if outside_player and (p == player_folder or player_folder in p.parents):
            raise Reject(f"path {arg!r} must be outside {PLAYER_FOLDER}/")
        return p

    def _int(self, req: dict, key: str, default: int | None = None) -> int:
        if key not in req and default is None:
            raise Reject(f"{key} is required: it is how many {key} the player gets in this game")
        try:
            return int(req.get(key, default))
        except (TypeError, ValueError):
            raise Reject(f"{key} must be an integer, got {req[key]!r}")

    def _game(self, req: dict):
        """The requested game's id, factory and solvability verdict, once it has validated."""
        src = self._path(req.get("game_file"))
        if not src.is_file():
            raise Reject(f"game file {req.get('game_file')!r} not found")
        code, gid = src.read_text(), "gen_" + re.sub(r"[^A-Za-z0-9_.-]", "_", src.stem)
        if self.cfg.games == "python":
            if reason := python_game.validate(code):
                raise Reject(f"game did not validate: {reason}")
            return gid, lambda: python_game.Game(code), None
        level = self._int(req, "level", 0)
        try:
            puzzlescript.Game(code, level).close()
        except Exception as e:
            raise Reject(f"game did not validate: {e}")
        key = (hashlib.sha256(code.encode()).hexdigest(), level)
        if key not in self._verdicts:
            with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
                f.write(code)
                f.flush()
                self._verdicts[key] = puzzlescript.solvable(Path(f.name), level)
        solved, states = self._verdicts[key]
        if solved is False:
            raise Reject(f"verified unsolvable: searched {states} states, none of them wins.")
        verdict = "verified solvable" if solved else "could not verify solvability"
        return f"{gid}_L{level}", lambda: puzzlescript.Game(code, level), verdict

    def play(self, req: dict) -> dict:
        gid, make_game, solvability = self._game(req)
        if not req.get("out"):
            raise Reject("out is required: name the file this play's result goes to")
        out = self._path(req["out"])
        folder = self._path(req[PLAYER_FOLDER], outside_player=False) \
            if req.get(PLAYER_FOLDER) else None
        if folder and not folder.is_dir():
            raise Reject(f"{PLAYER_FOLDER} {req[PLAYER_FOLDER]!r} is not a directory")
        turns = self._int(req, "turns") if self.turn_pool else self.cfg.horizon
        tokens = self._int(req, "tokens") if self.token_pool else self.cfg.tokens
        if turns < 1 or not 1 <= tokens <= self.cfg.max_game_tokens:
            raise Reject(f"turns must be at least 1, and tokens between 1 and {self.cfg.max_game_tokens}")
        version, frozen = self.versions.capture(folder) if folder else (None, None)
        with self._lock:
            if self.max_plays and self.plays >= self.max_plays:
                raise Reject(f"play budget exhausted ({self.max_plays} plays)")
            if self.turn_pool and self.turns_used + turns > self.turn_pool:
                raise Reject(f"turn budget exhausted: {self.turn_pool - self.turns_used} of "
                             f"{self.turn_pool} turns left, and this play asks for {turns}")
            if self.token_pool and self.tokens_used + tokens > self.token_pool:
                raise Reject(f"token budget exhausted: {self.token_pool - self.tokens_used} of "
                             f"{self.token_pool} tokens left, and this play asks for {tokens}")
            self.plays += 1
            self.turns_used += turns if self.turn_pool else 0
            self.tokens_used += tokens if self.token_pool else 0
            n = self.plays
        result = self._run(n, gid, make_game, frozen, turns, tokens)
        if result is None:
            with self._lock:
                self.plays -= 1
                self.turns_used -= turns if self.turn_pool else 0
                self.tokens_used -= tokens if self.token_pool else 0
            raise Reject(f"play {gid!r} failed after 3 attempts")
        row = self.ledger.add(result, game_id=gid, version=version, turn_budget=turns, token_budget=tokens)
        self.timeline("playserver", f"play #{row['n']} {gid} (gen) artifacts="
                                    f"{'player' if version else 'baseline'} version={version or '-'} "
                                    f"score={result['score']}")
        return self._report(req["out"], out, result, solvability)

    def _run(self, n: int, gid: str, make_game, frozen: Path | None, turns: int, tokens: int):
        with self._slots:
            for attempt in range(3):
                try:
                    return player.play(make_game, model=self.cfg.model, turns=turns, tokens=tokens,
                                       artifacts=frozen,
                                       log=self.out / "logs" / f"play{n:03d}_{gid}_{attempt}.jsonl")
                except Exception as e:
                    print(f"[gameplay] play #{n} {gid} attempt {attempt + 1} failed: {e!r}", flush=True)

    def _report(self, out_arg: str, out: Path, result: dict, solvability: str | None) -> dict:
        """Write the full result to the teacher's `out` file; return it without the transcript."""
        report = {k: result[k] for k in ("score", "stop_reason", "crashed")} | {"plays_used": self.plays}
        if self.max_plays:
            report["plays_budget"] = self.max_plays
        if result["crashed"]:
            report["crash_error"] = result["error"]
        full = report | {"turns": result["turns"]}
        tail = {}
        if self.turn_pool:
            tail |= {"turns_used": self.turns_used, "turns_budget": self.turn_pool}
        if self.token_pool:
            tail |= {"tokens_used": self.tokens_used, "tokens_budget": self.token_pool}
        if solvability:
            tail["solvability"] = solvability
        tail["revisions_left"] = self.revisions_left()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(full | tail, indent=2))
        return report | tail | {"out": out_arg, "transcript": out_arg}
