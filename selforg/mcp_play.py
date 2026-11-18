"""The Gameplay tool inside the teacher's Claude Code container: an MCP stdio server whose every
tool call is forwarded to the host's play server at the address in play.json. Mounted read-only
at /opt/play beside tools.json; standard library only."""

import json
import socket
import sys
import threading

_lock = threading.Lock()
_TOOLS = json.load(open("/opt/play/tools.json"))
_ADDRESS = json.load(open("/opt/play/play.json"))      # {"path"} or, on Docker Desktop, {"host", "port"}


def _send(msg: dict) -> None:
    with _lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def _play(args: dict) -> dict:
    if "path" in _ADDRESS:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(_ADDRESS["path"])
    else:
        s = socket.create_connection((_ADDRESS["host"], _ADDRESS["port"]))
    s.sendall((json.dumps({k: v for k, v in args.items() if v is not None}) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n") and (chunk := s.recv(65536)):
        buf += chunk
    s.close()
    reply = json.loads(buf or b'{"error": "the play server closed the connection"}')
    return {"content": [{"type": "text", "text": json.dumps(reply, indent=2)}], "isError": "error" in reply}


def _handle(req: dict) -> None:
    method, rid = req.get("method"), req.get("id")
    if method == "initialize":
        _send({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}}, "serverInfo": {"name": "play", "version": "1"}}})
    elif method == "tools/list":
        _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": _TOOLS}})
    elif method == "tools/call":
        try:
            result = _play(req["params"].get("arguments") or {})
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"play bridge error: {e!r}"}], "isError": True}
        _send({"jsonrpc": "2.0", "id": rid, "result": result})
    elif rid is not None:
        _send({"jsonrpc": "2.0", "id": rid, "result": {}})


for line in sys.stdin:                  # a thread per call, so several plays run at once
    if line.strip():
        threading.Thread(target=_handle, args=(json.loads(line),), daemon=True).start()
