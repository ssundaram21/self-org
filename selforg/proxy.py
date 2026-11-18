"""A loopback proxy between Claude Code and the API, for two things Claude Code cannot do itself:

- Lower one session's per-response output cap as its game's token budget runs down.
- Close a response that hits that cap as a finished, actionless reply ("Thinking limit reached; no
  move issued."), so the game spends the turn instead of Claude Code retrying it.
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SESSION_HEADER = "x-selforg-session"
UPSTREAM = "https://api.anthropic.com"
_MIN_CAP = 1024                                   # the API's floor for max_tokens with thinking
_NO_ACTION = "Thinking limit reached; no move issued."
_DROP = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding",
         "content-encoding"}
_caps: dict[str, int] = {}
_port = 0


def set_cap(session: str, max_tokens: int) -> None:
    _caps[session] = max_tokens


def _parse(raw: bytes) -> tuple[str | None, list[dict], str, dict]:
    """A streamed reply's stop reason, its signed thinking blocks, its message id and usage."""
    stop, msg_id, usage, blocks = None, "", {}, {}
    for line in raw.decode(errors="replace").splitlines():
        if not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        if ev["type"] == "message_start":
            msg_id = ev["message"].get("id", "")
            usage.update(ev["message"].get("usage") or {})
        elif ev["type"] == "content_block_start":
            blocks[ev["index"]] = dict(ev["content_block"])
        elif ev["type"] == "content_block_delta":
            b, d = blocks[ev["index"]], ev["delta"]
            for k in ("thinking", "signature"):
                b[k] = b.get(k, "") + d.get(k, "")
        elif ev["type"] == "message_delta":
            stop = ev.get("delta", {}).get("stop_reason") or stop
            usage.update(ev.get("usage") or {})
    thinking = [{"thinking": b["thinking"], "signature": b["signature"]}
                for _, b in sorted(blocks.items()) if b["type"] == "thinking" and b.get("signature")]
    return stop, thinking, msg_id, usage


def _emit(w, model: str, msg_id: str, thinking: list[dict], usage: dict) -> None:
    def sse(data: dict) -> None:
        w.write(f"event: {data['type']}\ndata: {json.dumps(data)}\n\n".encode())

    sse({"type": "message_start", "message": {
        "id": "msg_salvage_" + msg_id, "type": "message", "role": "assistant", "model": model,
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {k: v for k, v in usage.items() if k != "output_tokens"}}})
    for i, b in enumerate(thinking):
        sse({"type": "content_block_start", "index": i,
             "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
        sse({"type": "content_block_delta", "index": i,
             "delta": {"type": "thinking_delta", "thinking": b["thinking"]}})
        sse({"type": "content_block_delta", "index": i,
             "delta": {"type": "signature_delta", "signature": b["signature"]}})
        sse({"type": "content_block_stop", "index": i})
    i = len(thinking)
    sse({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
    sse({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": _NO_ACTION}})
    sse({"type": "content_block_stop", "index": i})
    sse({"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": usage})
    sse({"type": "message_stop"})
    w.flush()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _headers(self) -> dict:
        return {k: v for k, v in self.headers.items() if k.lower() not in _DROP}

    def do_HEAD(self):
        req = urllib.request.Request(UPSTREAM + self.path, headers=self._headers(), method="HEAD")
        try:
            self.send_response(urllib.request.urlopen(req, timeout=30).status)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
        self.send_header("content-length", "0")
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        cap = _caps.get(self.headers.get(SESSION_HEADER, ""))
        if cap is not None and "/v1/messages" in self.path:
            request = json.loads(body)
            request["max_tokens"] = min(request.get("max_tokens", cap), max(cap, _MIN_CAP))
            body = json.dumps(request).encode()
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=self._headers(),
                                     method="POST")
        try:
            up = urllib.request.urlopen(req, timeout=900)
            raw, status, headers = up.read(), up.status, up.headers
        except urllib.error.HTTPError as e:
            raw, status, headers = e.read(), e.code, e.headers
        stop, thinking, msg_id, usage = _parse(raw) if status == 200 else (None, [], "", {})
        if stop == "max_tokens":
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("connection", "close")
            self.end_headers()
            _emit(self.wfile, json.loads(body).get("model", ""), msg_id, thinking, usage)
            self.close_connection = True
            return
        self.send_response(status)
        for k, v in headers.items():
            if k.lower() not in _DROP:
                self.send_header(k, v)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass                                      # a session killed mid-request


def url(host: str = "127.0.0.1") -> str:
    """The proxy's base URL as seen from `host`'s name for the loopback, starting it on first use.
    It only ever listens on 127.0.0.1."""
    global _port
    if not _port:
        server = _Server(("127.0.0.1", 0), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _port = server.server_port
    return f"http://{host}:{_port}"
