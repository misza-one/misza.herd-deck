"""Mirror Omaherd's live inbox onto StreamController.

Polls `omarchy-shell io.github.salemsayed.omaherd status` so remote hosts (and the same
sort/filter the bar uses) stay in lockstep. Falls back to omaherd-status.py
only when the widget IPC is down. Actions render on GTK's main loop.
"""

from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import threading
import time
import weakref
from dataclasses import dataclass, field


STATUS_CMD = ["omarchy-shell", "io.github.salemsayed.omaherd", "status"]
STATUS_HELPERS = [
    os.path.expanduser("~/.config/omarchy/plugins/io.github.salemsayed.omaherd/omaherd-status.py"),
]

REFRESH_SEC = 2.0
BRANCH_TTL_SEC = 30.0
BRANCH_TIMEOUT_SEC = 3.0
MAX_BRANCH_CHARS = 48
_BRANCH_CACHE: dict[tuple[str, str], tuple[float, str]] = {}

@dataclass(frozen=True)
class HerdAgent:
    workspace: str = ""
    kind: str = ""
    status: str = "unknown"
    pane_id: str = ""
    session: str = "default"
    host: str = "local"
    hostname: str = ""
    key: str = ""
    workspace_number: int = 0
    tab_number: int = 0
    branch: str = ""

@dataclass
class HerdSnapshot:
    agents: list = field(default_factory=list)
    ok: bool = True


def _finite(value) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return number

def _clean_branch(value) -> str:
    text = " ".join(str(value or "").split())
    if text in ("", "HEAD"):
        return ""
    return text[:MAX_BRANCH_CHARS]


def _local_branch(cwd: str) -> str:
    if not cwd or not os.path.isabs(cwd) or shutil.which("git") is None:
        return ""
    commands = [
        ["git", "-C", cwd, "symbolic-ref", "--quiet", "--short", "HEAD"],
        ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=BRANCH_TIMEOUT_SEC,
            )
        except Exception:
            return ""
        branch = _clean_branch(result.stdout)
        if result.returncode == 0 and branch:
            return branch
    return ""


def _remote_branch(host: str, cwd: str) -> str:
    if not host or not cwd or not os.path.isabs(cwd):
        return ""
    quoted = shlex.quote(cwd)
    script = (
        f"git -C {quoted} symbolic-ref --quiet --short HEAD "
        f"|| git -C {quoted} rev-parse --short HEAD"
    )
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", "--", host, script],
            capture_output=True, text=True, timeout=BRANCH_TIMEOUT_SEC,
        )
    except Exception:
        return ""
    return _clean_branch(result.stdout) if result.returncode == 0 else ""


def _branch_for(host: str, cwd: str, entry: dict) -> str:
    reported = _clean_branch(entry.get("branch") or entry.get("gitBranch"))
    if reported:
        return reported
    if not cwd:
        return ""
    key = (host or "local", cwd)
    now = time.monotonic()
    cached = _BRANCH_CACHE.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]
    branch = _local_branch(cwd) if key[0] == "local" else _remote_branch(key[0], cwd)
    _BRANCH_CACHE[key] = (now + BRANCH_TTL_SEC, branch)
    return branch


def _parse_payload(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    if isinstance(value, dict) and isinstance(value.get("result"), dict):
        value = value["result"]
    return value if isinstance(value, dict) else None


def _agents_from(data: dict) -> list[HerdAgent]:
    agents = []
    raw = data.get("agents")
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("agent") or entry.get("displayAgent")
                   or entry.get("name") or "").lower()
        cwd = str(entry.get("cwd") or "")
        branch = _branch_for(str(entry.get("host") or "local"), cwd, entry)
        agents.append(HerdAgent(
            workspace=str(entry.get("workspaceLabel") or "Workspace"),
            kind=kind,
            status=str(entry.get("status") or "unknown").lower(),
            pane_id=str(entry.get("paneId") or ""),
            session=str(entry.get("session") or "default"),
            host=str(entry.get("host") or "local"),
            hostname=str(entry.get("hostname") or ""),
            key=str(entry.get("key") or ""),
            workspace_number=_finite(entry.get("workspaceNumber")),
            tab_number=_finite(entry.get("tabNumber")),
            branch=branch,
        ))
    return agents


class HerdClient:
    def __init__(self) -> None:
        self.snapshot = HerdSnapshot()
        self._subscribers = weakref.WeakSet()
        self._stop = threading.Event()
        self._helper = next((p for p in STATUS_HELPERS if os.path.isfile(p)), None)
        self._thread = threading.Thread(target=self._loop, name="MiszaHerdPoll", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()

    def subscribe(self, action) -> None:
        self._subscribers.add(action)

    def unsubscribe(self, action) -> None:
        self._subscribers.discard(action)

    def refresh_now(self) -> None:
        snapshot = self._poll()
        self.snapshot = snapshot
        for action in list(self._subscribers):
            notify = getattr(action, "on_herd_snapshot", None)
            if notify is not None:
                notify(snapshot)

    def _loop(self) -> None:
        while not self._stop.wait(REFRESH_SEC):
            try:
                self.refresh_now()
            except Exception:
                pass

    def _poll(self) -> HerdSnapshot:
        data = self._from_omaherd() or self._from_helper()
        if data is None:
            return HerdSnapshot(agents=[], ok=False)
        return HerdSnapshot(agents=_agents_from(data), ok=True)

    def _from_omaherd(self) -> dict | None:
        if shutil.which(STATUS_CMD[0]) is None:
            return None
        try:
            out = subprocess.run(
                STATUS_CMD, capture_output=True, text=True, timeout=8,
            )
        except Exception:
            return None
        data = _parse_payload(out.stdout)
        if data is None or not isinstance(data.get("agents"), list):
            return None
        return data

    def _from_helper(self) -> dict | None:
        if self._helper is None:
            return None
        try:
            out = subprocess.run(
                ["python3", self._helper, "--skip-discovery"],
                capture_output=True, text=True, timeout=15,
            )
        except Exception:
            return None
        return _parse_payload(out.stdout)
