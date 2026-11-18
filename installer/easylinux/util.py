"""Running commands with logging, and language settings."""

from __future__ import annotations

import collections
import os
import shlex
import subprocess
import threading
import time
from pathlib import Path

LANGUAGES = {
    "en": {"locale": "en_US.UTF-8", "keyboard": "us", "console": "us"},
    "de": {"locale": "de_DE.UTF-8", "keyboard": "de", "console": "de"},
}


class CommandError(Exception):
    pass


class Log:
    """Writes to a log file and keeps the last lines for the progress screen."""

    def __init__(self, path: Path | None = None, keep: int = 200):
        self.path = path
        self.lines: collections.deque[str] = collections.deque(maxlen=keep)
        self._lock = threading.Lock()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        with self._lock:
            for line in str(text).splitlines() or [""]:
                self.lines.append(f"{stamp} {line}")
                if self.path:
                    with self.path.open("a", encoding="utf-8", errors="replace") as fh:
                        fh.write(f"{stamp} {line}\n")

    def tail(self, n: int = 30) -> list[str]:
        with self._lock:
            return list(self.lines)[-n:]


def run(cmd: list[str], log: Log, *, input: str | None = None, env: dict | None = None,
        check: bool = True, quiet: bool = False) -> str:
    log(f"$ {shlex.join(cmd)}" if not quiet else f"$ {cmd[0]} …")
    full_env = dict(os.environ, **(env or {}))
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=full_env, errors="replace",
    )
    if input is not None:
        proc.stdin.write(input)
        proc.stdin.close()
    output: list[str] = []
    for line in proc.stdout:
        line = line.rstrip("\n")
        output.append(line)
        if not quiet:
            log(line)
    code = proc.wait()
    if check and code != 0:
        tail = "\n".join(output[-20:])
        if quiet:
            log(tail)
        raise CommandError(f"command failed ({code}): {cmd[0]}")
    return "\n".join(output)


def write_file(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)
