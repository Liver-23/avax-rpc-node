#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import sys
from urllib.parse import urlparse


GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# C-Chain JSON-RPC collections in AVAXspec may use "", "/C/rpc", or "/ext/bc/C/rpc"
C_CHAIN_SPEC_PATHS = frozenset({"", "/C/rpc", "/ext/bc/C/rpc"})


def enabled_ws_methods(spec_path: str) -> set[str]:
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    methods = set()
    for collection in spec["Spec"]["api_collections"]:
        if not collection.get("enabled", False):
            continue
        path = collection["collection_data"].get("internal_path", "")
        if path not in C_CHAIN_SPEC_PATHS:
            continue
        for api in collection.get("apis", []):
            if api.get("enabled", False) and api.get("name") in ("eth_subscribe", "eth_unsubscribe"):
                methods.add(api["name"])
    return methods


class WebSocketClient:
    def __init__(self, ws_url: str, timeout: float = 8.0):
        self.ws_url = ws_url
        self.timeout = timeout
        self.sock = None

    def connect(self) -> None:
        parsed = urlparse(self.ws_url)
        if parsed.scheme not in ("ws", "wss"):
            raise ValueError(f"Unsupported scheme: {parsed.scheme}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        raw = socket.create_connection((host, port), timeout=self.timeout)
        if parsed.scheme == "wss":
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=host)
        raw.settimeout(self.timeout)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        raw.sendall(req.encode("ascii"))
        resp = self._recv_http_headers(raw)
        status = resp.split("\r\n", 1)[0]
        if "101" not in status:
            raise RuntimeError(f"Handshake failed: {status}")

        accept_expected = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
        if f"sec-websocket-accept: {accept_expected.lower()}" not in resp.lower():
            raise RuntimeError("Invalid Sec-WebSocket-Accept in handshake response")
        self.sock = raw

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self._send_frame(opcode=0x8, payload=b"")
        except Exception:
            pass
        try:
            self.sock.close()
        finally:
            self.sock = None

    def send_json(self, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        self._send_frame(opcode=0x1, payload=data)

    def recv_json(self) -> dict:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))
            if opcode == 0x9:  # ping
                self._send_frame(opcode=0xA, payload=payload)  # pong
            elif opcode == 0x8:  # close
                raise RuntimeError("Server closed connection")

    def _recv_http_headers(self, sock_obj: socket.socket) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock_obj.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("latin-1", errors="replace")

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self.sock is None:
            raise RuntimeError("WebSocket is not connected")
        fin_opcode = 0x80 | (opcode & 0x0F)
        mask_bit = 0x80
        n = len(payload)
        header = bytearray([fin_opcode])
        if n < 126:
            header.append(mask_bit | n)
        elif n < (1 << 16):
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", n))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", n))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n: int) -> bytes:
        if self.sock is None:
            raise RuntimeError("WebSocket is not connected")
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise RuntimeError("Unexpected EOF while reading frame")
            out += chunk
        return out

    def _recv_frame(self) -> tuple[int, bytes]:
        b1, b2 = self._recv_exact(2)
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else None
        payload = self._recv_exact(length) if length else b""
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload


def ws_candidates(base_url: str) -> list[str]:
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base = f"{scheme}://{parsed.netloc}"
    # AvalancheGo serves WS on /ext/bc/C/ws (bare /C/ws is not valid on stock nodes)
    return [
        f"{base}/ext/bc/C/ws",
        f"{base}/ext/bc/C/rpc/ws",
    ]


def rpc_ok(resp: dict) -> tuple[bool, str]:
    if "error" not in resp:
        return True, "ok"
    err = resp.get("error", {})
    code = err.get("code")
    msg = str(err.get("message", "")).lower()
    if code == -32601 or "method not found" in msg:
        return False, "method-not-found"
    return True, f"error-code-{code}"


def run_check(ws_url: str, timeout: float, methods: set[str]) -> tuple[bool, str]:
    ws = WebSocketClient(ws_url, timeout=timeout)
    ws.connect()
    try:
        if "eth_subscribe" in methods:
            ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]})
            sub_resp = ws.recv_json()
            ok, reason = rpc_ok(sub_resp)
            if not ok:
                return False, f"eth_subscribe:{reason}"
            sub_id = sub_resp.get("result")
        else:
            sub_id = None

        if "eth_unsubscribe" in methods and sub_id:
            ws.send_json({"jsonrpc": "2.0", "id": 2, "method": "eth_unsubscribe", "params": [sub_id]})
            unsub_resp = ws.recv_json()
            ok, reason = rpc_ok(unsub_resp)
            if not ok:
                return False, f"eth_unsubscribe:{reason}"

        return True, "ok"
    finally:
        ws.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AVAX WebSocket RPC methods from AVAXspec.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:9650", help="Base HTTP URL of AvalancheGo")
    parser.add_argument("--spec", default="AVAXspec.json", help="Path to AVAXspec.json")
    parser.add_argument("--timeout", type=float, default=60.0, help="WebSocket timeout in seconds")
    args = parser.parse_args()

    methods = enabled_ws_methods(args.spec)
    if not methods:
        print("No enabled WebSocket methods (eth_subscribe/eth_unsubscribe) found in spec.")
        return 1

    print(f"Checking WebSocket methods from spec: {', '.join(sorted(methods))}")
    attempts = []
    for url in ws_candidates(args.base_url):
        try:
            ok, reason = run_check(url, args.timeout, methods)
            if ok:
                print(f"PASS: {url}")
                return 0
            attempts.append((url, reason))
        except Exception as e:
            attempts.append((url, f"request-failed:{type(e).__name__}:{e}"))

    print("FAIL: no candidate WebSocket endpoint passed")
    for url, reason in attempts:
        print(f"- {url} -> {reason}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
