#!/usr/bin/env python3
"""Drives a test installation in a QEMU VM through the installer's API (GitHub Actions only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def call(base: str, token: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Token": token, "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--pid", type=int, help="QEMU process; stop if it exits")
    a = ap.parse_args()

    deadline = time.time() + a.timeout
    seen: list[str] = []
    started = False
    while time.time() < deadline:
        if a.pid:
            try:
                os.kill(a.pid, 0)
            except OSError:
                print("QEMU exited before the installation finished", flush=True)
                return 1
        try:
            s = call(a.url, a.token, "/api/state")
        except (urllib.error.URLError, OSError, ValueError):
            if started:
                print("menu server gone (VM powered off?)", flush=True)
                return 1
            time.sleep(10)
            continue
        for line in s.get("log", []):
            if line not in seen:
                print(line, flush=True)
                seen.append(line)
        seen = seen[-200:]
        phase = s["phase"]
        if phase == "error":
            print(f"ERROR: {s.get('error')} {s.get('detail')}", flush=True)
            return 1
        if phase == "ready" and not started:
            if s.get("error"):
                print(f"ERROR: {s['error']} {s.get('detail')}", flush=True)
                return 1
            r = call(a.url, a.token, "/api/install", {"profile": a.profile, "lang": "en"})
            print(f"install started: {r}", flush=True)
            started = True
        elif phase == "ready" and started and s.get("error"):
            print(f"ERROR: {s['error']} {s.get('detail')}", flush=True)
            return 1
        elif phase == "failed":
            print(f"FAILED: {s.get('detail')}", flush=True)
            return 1
        elif phase == "done":
            print("installation finished", flush=True)
            return 0
        time.sleep(5)
    print("timeout", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
