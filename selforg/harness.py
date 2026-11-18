"""Agent sessions: one Claude Code or Pi process in a Singularity or Docker container (see
config.RUNTIME), held open for a whole game (player) or a whole run (teacher). The container sees
only its work dir, bound at WORKDIR, and whatever read-only `binds` it is given. Each `turn` sends
one user message and returns the reply.

`on_event(kind, data)` is called with ("tool_use", {"name", "input"}) as the agent calls a tool and
("tool_result", {}) once the call has finished.
"""

import atexit
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from selforg import proxy
from selforg.config import (DOCKER_DESKTOP, DOCKER_IMAGE, EFFORT, HOST_FROM_CONTAINER,
                            MAX_RESPONSE_TOKENS, ROOT, RUNTIME, WORKDIR, is_pi, model_credential)

_RETRIES, _BACKOFF = 8, 10           # failed turns are re-sent after 10s, 20s, ... capped at 120s
_MAX_PLAYER_TOOL_CALLS = 50          # a player turn making more tool calls than this is a loop
_containers: set[str] = set()        # Docker containers started and not yet stopped


def _stop(names: list[str]) -> None:
    subprocess.run(["docker", "rm", "--force", *names], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    _containers.difference_update(names)


atexit.register(lambda: _containers and _stop(list(_containers)))


def session(model: str, **kw) -> "Session":
    return (Pi if is_pi(model) else ClaudeCode)(model, **kw)


class Session:
    def __init__(self, model: str, *, workdir: Path, tools: list[str], system_prompt: str,
                 log: Path, teacher: bool = False, binds: tuple[str, ...] = (), on_event=None):
        self.model, self.tools, self.system_prompt = model, tools, system_prompt
        self.workdir, self.teacher, self.binds = Path(workdir), teacher, binds
        self.on_event = on_event or (lambda kind, data: None)
        self.state = Path(tempfile.mkdtemp(prefix="agent_state_"))   # the container's HOME
        self._prepare_state()
        log.parent.mkdir(parents=True, exist_ok=True)
        self.log = log.open("a")
        self._write({"system_prompt": system_prompt, "tools": tools})
        self.stderr = log.with_suffix(".stderr")
        self.proc = subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.stderr.open("w"), text=True, bufsize=1)

    def _prepare_state(self) -> None:
        pass

    def _command(self) -> list[str]:
        env = [a for k, v in self._env().items() for a in ("--env", f"{k}={v}")]
        if RUNTIME == "docker":
            # Named so close() can stop it: killing the `docker run` client leaves it running.
            self.container = f"selforg-{uuid.uuid4().hex[:12]}"
            _containers.add(self.container)
            return ["docker", "run", "--rm", "-i", "--init", "--name", self.container,
                    "--label", "selforg", "--user", f"{os.getuid()}:{os.getgid()}",
                    *([] if DOCKER_DESKTOP else ["--network", "host"]), "--workdir", WORKDIR,
                    "--env", "HOME=/state", "--volume", f"{self.state}:/state",
                    "--volume", f"{self.workdir}:{WORKDIR}",
                    *[a for b in self.binds for a in ("--volume", b)], *env,
                    DOCKER_IMAGE.format(self.image), *self._inner()]
        return ["singularity", "exec", "--cleanenv", "--contain", "--pwd", WORKDIR,
                "--home", f"{self.state}:/state", "--bind", f"{self.workdir}:{WORKDIR}",
                *[a for b in self.binds for a in ("--bind", b)], *env,
                str(ROOT / "containers" / self.image), *self._inner()]

    def _write(self, obj: dict) -> None:
        self.log.write(json.dumps(obj) + "\n")
        self.log.flush()

    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            self.proc.wait()
            raise RuntimeError(f"{self.image} exited: {self.stderr.read_text()[-2000:]}")
        event = json.loads(line)
        self._write(event)
        return event

    def turn(self, text: str) -> dict:
        """Returns {"text", "tool_uses", "thinking", "output_tokens"}, plus "tool_loop" when a
        player turn was cut off for calling tools without end."""
        self._write({"prompt": text})
        for attempt in range(_RETRIES + 1):
            reply, error = self._turn(text)
            if error is None:
                return reply
            if self.proc.poll() is not None or attempt == _RETRIES:
                raise RuntimeError(error)
            time.sleep(min(_BACKOFF * 2 ** attempt, 120))

    def cap_output(self, max_tokens: int) -> None:
        """Limit the output tokens the next turn may spend."""

    def close(self) -> None:
        self.proc.kill()
        self.proc.wait()
        if RUNTIME == "docker":
            _stop([self.container])
        self.log.close()
        shutil.rmtree(self.state, ignore_errors=True)


class ClaudeCode(Session):
    image = "claude_code"

    def __init__(self, model: str, **kw):
        self.id = uuid.uuid4().hex                  # tags this session's requests to the proxy
        super().__init__(model, **kw)

    def _env(self) -> dict:
        credential = dict([model_credential(self.model)])
        return {"CLAUDE_CODE_MAX_OUTPUT_TOKENS": MAX_RESPONSE_TOKENS,
                "ANTHROPIC_BASE_URL": proxy.url(HOST_FROM_CONTAINER),
                "ANTHROPIC_CUSTOM_HEADERS": f"{proxy.SESSION_HEADER}: {self.id}",
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": 1, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": 1,
                "BASH_DEFAULT_TIMEOUT_MS": 1_800_000, "BASH_MAX_TIMEOUT_MS": 1_800_000,
                **credential}

    def _inner(self) -> list[str]:
        mcp = ["--mcp-config", "/opt/play/mcp.json"] if self.binds else []
        return ["claude", "-p", "--model", self.model, "--effort", EFFORT,
                "--thinking-display", "summarized",
                "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--permission-mode", "bypassPermissions" if self.teacher else "acceptEdits",
                "--tools", ",".join(self.tools), "--system-prompt", self.system_prompt,
                "--strict-mcp-config", "--disallowed-tools",
                "DesignSync,Monitor,PushNotification,RemoteTrigger,example_complex_tool", *mcp]

    def cap_output(self, max_tokens: int) -> None:
        proxy.set_cap(self.id, max_tokens)

    def _turn(self, text: str) -> tuple[dict | None, str | None]:
        self._send({"type": "user", "message": {"role": "user",
                                                "content": [{"type": "text", "text": text}]}})
        blocks = []
        while (event := self._read())["type"] != "result":
            content = event.get("message", {}).get("content", [])
            if event["type"] == "assistant":
                blocks += content
                for b in content:
                    if b["type"] == "tool_use":
                        self.on_event("tool_use", {"name": b["name"], "input": b["input"]})
            elif event["type"] == "user" and any(b.get("type") == "tool_result" for b in content):
                self.on_event("tool_result", {})
        if event.get("is_error"):
            return None, f"claude reported an error: {event.get('result')}"
        return {"text": event.get("result") or "",
                "tool_uses": [{"name": b["name"], "input": b["input"]}
                              for b in blocks if b["type"] == "tool_use"],
                "thinking": [b.get("thinking", "") for b in blocks if b["type"] == "thinking"],
                "output_tokens": (event.get("usage") or {}).get("output_tokens", 0)}, None


class Pi(Session):
    image = "pi"
    _TOOLS = {"Bash": "bash", "Read": "read", "Write": "write", "Edit": "edit", "Glob": "find",
              "Grep": "grep", "play_own_game": "play_own_game"}

    def __init__(self, model: str, **kw):
        self.provider, _, self.model_id = model.partition("/")
        self._cap = 0
        super().__init__(model, **kw)
        state = self._command_reply({"type": "get_state"})
        if (state["model"]["id"], state["thinkingLevel"]) != (self.model_id, EFFORT):
            raise RuntimeError(f"pi launched {state['model']['id']} at {state['thinkingLevel']}")

    def _env(self) -> dict:
        return {"PI_OFFLINE": 1, "PI_SKIP_VERSION_CHECK": 1, "PI_TELEMETRY": 0,
                **dict([model_credential(self.model)])}

    def _inner(self) -> list[str]:
        ext = ["-e", "/opt/play/pi_play.ts"] if self.binds else []
        return ["pi", "--mode", "rpc", "--model", self.model, "--thinking", EFFORT,
                "--tools", ",".join(self._TOOLS[t] for t in self.tools),
                "--system-prompt", self.system_prompt, "--no-extensions", "--no-skills",
                "--no-prompt-templates", "--no-themes", "--no-context-files", *ext]

    def _prepare_state(self) -> None:
        models = {"providers": {self.provider: {"modelOverrides": {
            self.model_id: {"maxTokens": MAX_RESPONSE_TOKENS}}}}}
        (self.state / ".pi" / "agent").mkdir(parents=True)
        (self.state / ".pi" / "agent" / "models.json").write_text(json.dumps(models))

    def _command_reply(self, cmd: dict) -> dict:
        self._send(cmd)
        while not ((r := self._read())["type"] == "response" and r["command"] == cmd["type"]):
            pass
        if not r.get("success"):
            raise RuntimeError(f"pi refused {cmd['type']}: {r.get('error')}")
        return r.get("data") or {}

    def cap_output(self, max_tokens: int) -> None:
        self._cap = max_tokens

    def _turn(self, text: str) -> tuple[dict | None, str | None]:
        start = len(self._command_reply({"type": "get_entries"})["entries"])
        self._send({"type": "prompt", "message": text})
        messages, calls, aborted, looped, settled, answered = [], 0, False, False, False, False
        while not (settled and (answered or not aborted)):
            event = self._read()
            kind = event["type"]
            if kind == "response" and not event.get("success"):
                return None, f"pi rejected the prompt: {event.get('error')}"
            if kind == "message_end" and event["message"]["role"] == "assistant":
                messages.append(event["message"])
                for b in event["message"].get("content", []):
                    if b["type"] == "toolCall":
                        self.on_event("tool_use", {"name": b["name"], "input": b.get("arguments", {})})
                spent = sum(m.get("usage", {}).get("output", 0) for m in messages)
                if self._cap and spent >= self._cap and not aborted:
                    self._send({"type": "abort"})
                    aborted = True
            elif kind == "tool_execution_start":
                calls += 1
                if not self.teacher and calls >= _MAX_PLAYER_TOOL_CALLS and not aborted:
                    self._send({"type": "abort"})
                    aborted = looped = True
            elif kind == "tool_execution_end":
                self.on_event("tool_result", {})
            answered |= kind == "response" and event.get("command") == "abort"
            settled |= kind == "agent_settled"
        if aborted and messages and messages[-1].get("stopReason") == "error":
            messages.pop()                  # the abort's own error message, not the reply
        if not messages or messages[-1].get("stopReason") == "error":
            error = messages[-1].get("errorMessage") if messages else "no reply"
            if "400" in str(error):          # the provider rejects the history: drop this turn
                entries = self._command_reply({"type": "get_entries"})["entries"][start:]
                first = next((e for e in entries if e.get("type") == "message"
                              and e["message"].get("role") == "user"), None)
                if first:
                    self._command_reply({"type": "fork", "entryId": first["id"]})
            return None, f"pi reported an error: {error}"
        blocks = [b for m in messages for b in m.get("content", [])]
        output = sum(m.get("usage", {}).get("output", 0) for m in messages)
        over = bool(self._cap) and output > self._cap      # a reply over the cap has no action
        return {"text": "" if over else "\n".join(b["text"] for b in blocks if b["type"] == "text"),
                "tool_uses": [{"name": b["name"], "input": b.get("arguments", {})}
                              for b in blocks if b["type"] == "toolCall"],
                "thinking": [b.get("thinking", "") for b in blocks if b["type"] == "thinking"],
                "output_tokens": output, "tool_loop": looped}, None
