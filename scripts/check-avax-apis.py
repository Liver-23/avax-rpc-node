#!/usr/bin/env python3
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict


def candidate_paths(internal_path: str) -> list[str]:
    # Only /ext/bc/... paths are valid on AvalancheGo; bare /C/rpc, /P return 404 and break checks.
    mapping = {
        "": ["/ext/bc/C/rpc"],
        "/C/rpc": ["/ext/bc/C/rpc"],
        "/C/avax": ["/ext/bc/C/avax"],
        "/P": ["/ext/bc/P"],
        "/X": ["/ext/bc/X"],
    }
    return mapping.get(internal_path, [internal_path])


# Some RPCs return very large payloads (e.g. full validator sets).
METHOD_TIMEOUT_OVERRIDES: dict[str, float] = {
    "platform.getValidatorsAt": 120.0,
}


def rpc_call(url: str, method: str, timeout: float) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": [],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def classify_response(resp: dict) -> tuple[bool, str]:
    if "error" not in resp:
        return True, "ok"
    err = resp.get("error", {})
    code = err.get("code")
    msg = str(err.get("message", "")).lower()
    if code == -32601 or "method not found" in msg:
        return False, "method-not-found"
    return True, f"error-code-{code}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check enabled AVAX APIs from AVAXspec.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:9650", help="AvalancheGo base URL")
    parser.add_argument("--spec", default="AVAXspec.json", help="Path to AVAXspec.json")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout per call in seconds (default 60; some methods use overrides)",
    )
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    collections = spec["Spec"]["api_collections"]
    checks = []
    for collection in collections:
        if not collection.get("enabled", False):
            continue
        internal_path = collection["collection_data"]["internal_path"]
        for api in collection.get("apis", []):
            if api.get("enabled", False):
                checks.append((internal_path, api["name"]))

    total = len(checks)
    if total == 0:
        print("No enabled APIs found in spec.")
        return 1

    ok = 0
    failed = []
    failures_by_path = defaultdict(int)

    started = time.time()
    for internal_path, method in checks:
        path_ok = False
        last_reason = "request-failed"
        for p in candidate_paths(internal_path):
            url = args.base_url.rstrip("/") + p
            timeout = METHOD_TIMEOUT_OVERRIDES.get(method, args.timeout)
            try:
                resp = rpc_call(url, method, timeout=timeout)
                method_ok, reason = classify_response(resp)
                if method_ok:
                    path_ok = True
                    break
                last_reason = reason
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
                last_reason = f"request-failed:{type(e).__name__}"
        if path_ok:
            ok += 1
        else:
            failed.append((internal_path, method, last_reason))
            failures_by_path[internal_path] += 1

    elapsed = time.time() - started
    print(f"Checked {total} enabled APIs in {elapsed:.1f}s")
    print(f"PASS {ok}/{total}")
    print(f"FAIL {len(failed)}/{total}")

    if failed:
        print("\nFailures by path:")
        for p, count in sorted(failures_by_path.items(), key=lambda x: (-x[1], x[0])):
            print(f"- {p or '/'}: {count}")
        print("\nFirst 50 failures:")
        for internal_path, method, reason in failed[:50]:
            print(f"- [{internal_path or '/'}] {method} -> {reason}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
